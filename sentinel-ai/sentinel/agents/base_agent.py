"""
SENTINEL-AI base agent class.

Provides the abstract base that all specialist agents extend.
Handles message-bus wiring, LLM calls, and evidence-chain construction.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sentinel.models import AgentMessage, EvidenceChain, EvidenceItem
from sentinel.config import SENTINEL_DEMO_MODE


class BaseAgent(ABC):
    """Abstract base for every SENTINEL-AI agent."""

    name: str = "base_agent"

    def __init__(self, bus: Any = None) -> None:
        self.bus = bus

    # ── Abstract contract ────────────────────────────────────────────────────

    @abstractmethod
    def analyze(self, event: Dict[str, Any], context: Dict[str, Any]) -> EvidenceChain:
        """Run this agent's analysis on the event. Must return an EvidenceChain."""
        ...

    # ── Message helpers ──────────────────────────────────────────────────────

    def publish(
        self,
        kind: str,
        content: str,
        to_agent: str = "broadcast",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish a message on the bus if available."""
        if self.bus is not None:
            self.bus.send(
                from_agent=self.name,
                kind=kind,
                content=content,
                to_agent=to_agent,
                payload=payload,
            )

    # ── Evidence helpers ─────────────────────────────────────────────────────

    @staticmethod
    def make_evidence_item(
        log_id: str, excerpt: str, why_relevant: str
    ) -> EvidenceItem:
        """Create an EvidenceItem with current timestamp."""
        return EvidenceItem(
            log_id=log_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            excerpt=excerpt,
            why_relevant=why_relevant,
        )

    def build_chain(
        self,
        conclusion: str,
        confidence: float,
        evidence: Optional[List[EvidenceItem]] = None,
        mitre_techniques: Optional[List[str]] = None,
        next_actions: Optional[List[str]] = None,
    ) -> EvidenceChain:
        """Build an EvidenceChain from this agent."""
        return EvidenceChain(
            agent=self.name,
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence or [],
            mitre_techniques=mitre_techniques or [],
            next_actions=next_actions or [],
        )

    # ── LLM interaction ──────────────────────────────────────────────────────

    def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM backend. Falls back to demo mode if needed."""
        if SENTINEL_DEMO_MODE:
            return self._demo_llm_response(system_prompt, user_prompt)
        try:
            from sentinel.llm.cerebras_client import call_cerebras

            return call_cerebras(system_prompt, user_prompt)
        except Exception as exc:
            self.publish("thought", f"LLM call failed ({exc}), using demo fallback")
            return self._demo_llm_response(system_prompt, user_prompt)

    def _demo_llm_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a deterministic demo response based on agent name."""
        return json.dumps(
            {
                "conclusion": f"[DEMO] {self.name} analysis complete. "
                "Suspicious activity detected; recommend further investigation.",
                "confidence": 0.72,
                "mitre_techniques": ["T1059.001", "T1071.001"],
                "next_actions": ["Isolate host", "Collect memory dump"],
                "evidence_notes": "Demo mode – no real LLM inference performed.",
            }
        )
