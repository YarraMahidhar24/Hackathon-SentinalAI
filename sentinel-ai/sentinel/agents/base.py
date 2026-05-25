"""
SENTINEL-AI base agent class.

Every specialist agent inherits from ``BaseAgent``, which provides:
- A ``name`` identifier
- A system prompt injected into every LLM call
- ``publish()`` to send :class:`AgentMessage` events to the bus
- ``llm_chat()`` to call the Cerebras LLM with retries
- An abstract ``analyze()`` method that subclasses must implement
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from rich.console import Console

from sentinel.llm.cerebras_client import get_client
from sentinel.orchestration.message_bus import (
    AgentMessage,
    EvidenceChain,
    MessageBus,
    bus,
)

logger = logging.getLogger(__name__)
console = Console()


class BaseAgent(ABC):
    """Abstract base for every SENTINEL-AI specialist agent."""

    def __init__(self, name: str, system_prompt: str) -> None:
        self._name = name
        self._system_prompt = system_prompt
        self._bus: MessageBus = bus
        self._client = get_client()

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Human-readable agent identifier (e.g. ``'ThreatIntelAgent'``)."""
        return self._name

    @property
    def system_prompt(self) -> str:
        """System prompt used for every LLM call made by this agent."""
        return self._system_prompt

    # ── Message bus ──────────────────────────────────────────────────────

    def publish(
        self,
        kind: str,
        content: str,
        to_agent: str = "broadcast",
        payload: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Create and publish an :class:`AgentMessage` on the shared bus.

        Parameters
        ----------
        kind : one of thought / question / answer / critique / decision / tool_call / tool_result
        content : human-readable summary of the message
        to_agent : recipient agent name, or ``'broadcast'``
        payload : optional structured data dict
        """
        msg = AgentMessage(
            from_agent=self._name,
            to_agent=to_agent,
            kind=kind,  # type: ignore[arg-type]
            content=content,
            payload=payload,
        )
        self._bus.publish(msg)
        console.print(
            f"[bold cyan]\\[{self._name}][/bold cyan] "
            f"[dim]{kind}[/dim] → {content[:120]}"
        )
        return msg

    # ── LLM wrapper ──────────────────────────────────────────────────────

    def llm_chat(
        self,
        messages: List[Dict[str, str]],
        response_model: Optional[Type[BaseModel]] = None,
    ) -> str:
        """Send a chat completion via the Cerebras client.

        The agent's ``system_prompt`` is **automatically prepended** as the
        first message if the caller hasn't already included a system message.

        Parameters
        ----------
        messages : list of ``{"role": ..., "content": ...}`` dicts.
        response_model : optional Pydantic model for response validation
                         (caller is responsible for parsing the returned string).

        Returns
        -------
        str – the raw assistant reply text.
        """
        # Prepend system prompt if not already present
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self._system_prompt}] + messages

        self.publish("thought", f"Calling LLM ({len(messages)} messages)")
        reply = self._client.chat(messages, response_model=response_model, agent_name=self.name)
        return reply

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def safe_parse_json(text: str) -> Dict[str, Any]:
        """Best-effort JSON parse: strips markdown fences and recovers."""
        cleaned = text.strip()
        # Remove ```json ... ``` fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Drop first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find first { ... } block
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return {"raw": text}

    # ── Abstract interface ───────────────────────────────────────────────

    @abstractmethod
    def analyze(
        self, event: dict, context: Optional[dict] = None
    ) -> Union[EvidenceChain, dict]:
        """Run the agent's analysis on *event* and return structured output.

        Parameters
        ----------
        event : the normalised security event dict.
        context : optional additional context from prior agents.

        Returns
        -------
        EvidenceChain or dict, depending on the agent.
        """
        ...
