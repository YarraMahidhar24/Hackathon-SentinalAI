"""
SENTINEL-AI Sanitizer Agent.

Runs FIRST in the pipeline to detect and neutralise prompt-injection
attacks embedded inside log / event data before they reach downstream
LLM-powered agents.

Strategy
--------
1. **Heuristic regex pass** – fast, zero-LLM-cost scan for known injection
   patterns (role tokens, jailbreak phrases, base64 blobs, zero-width
   characters, HTML comments, etc.).
2. **Optional LLM verification** – in non-demo mode the agent can call the
   LLM to double-check suspicious fields (disabled by default for speed).
3. **Neutralisation** – dangerous content is escaped or stripped; the
   cleaned event plus an injection report are returned.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from sentinel.agents.base import BaseAgent
from sentinel.llm import prompts
from sentinel.orchestration.message_bus import EvidenceChain, EvidenceItem

logger = logging.getLogger(__name__)

# ── Compiled injection-detection patterns ────────────────────────────────────

INJECTION_PATTERNS: List[re.Pattern[str]] = [
    # Direct instruction overrides
    re.compile(r"ignore\s+(previous|prior|above|all)\s+(instructions?|prompts?|context)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|prior|above|all)", re.IGNORECASE),
    # Role token injection
    re.compile(r"(?:^|\n)\s*(system|assistant|user)\s*:", re.IGNORECASE),
    # Identity hijack
    re.compile(r"you\s+are\s+now", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an|if)\b", re.IGNORECASE),
    re.compile(r"pretend\s+to\s+be", re.IGNORECASE),
    # Base64 blobs (≥ 40 chars of base64 alphabet)
    re.compile(r"[A-Za-z0-9+/=]{40,}"),
    # Zero-width / invisible characters
    re.compile(r"[\u200b\u200c\u200d\ufeff]"),
    # HTML comment injection
    re.compile(r"<!--[\s\S]*?-->"),
    # Common jailbreak phrases
    re.compile(r"DAN\s*mode", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+(enabled|on|output)", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"ignore\s+(safety|content)\s+(filter|policy|guidelines?)", re.IGNORECASE),
    # Prompt leaking attempts
    re.compile(r"(print|reveal|show|repeat)\s+(your|the|system)\s+(prompt|instructions?)", re.IGNORECASE),
]

# Fields in an event dict that could carry injected content
_INSPECTABLE_FIELDS = (
    "description",
    "message",
    "raw",
    "payload",
    "command",
    "query",
    "url",
    "user_agent",
    "subject",
    "body",
    "details",
    "alert_name",
    "summary",
)


class SanitizerAgent(BaseAgent):
    """Prompt-injection detection and neutralisation agent."""

    def __init__(self) -> None:
        super().__init__(name="SanitizerAgent", system_prompt=prompts.SANITIZER_SYSTEM_PROMPT)

    # ── Core API ─────────────────────────────────────────────────────────

    def sanitize(self, event: dict) -> Tuple[dict, dict]:
        """Scan *event* for prompt-injection patterns.

        Returns
        -------
        tuple of (cleaned_event, injection_report)
            ``injection_report`` has keys ``detected``, ``patterns``, and
            ``neutralized_fields``.
        """
        cleaned = copy.deepcopy(event)
        detected_patterns: List[str] = []
        neutralized_fields: List[str] = []

        for field_name in _INSPECTABLE_FIELDS:
            value = self._deep_get(cleaned, field_name)
            if not isinstance(value, str) or not value:
                continue

            field_hits = self._scan_value(value)
            if field_hits:
                detected_patterns.extend(field_hits)
                neutralized_value = self._neutralize(value, field_hits)
                self._deep_set(cleaned, field_name, neutralized_value)
                neutralized_fields.append(field_name)

        detected = bool(detected_patterns)

        report: Dict[str, Any] = {
            "detected": detected,
            "patterns": detected_patterns,
            "neutralized_fields": neutralized_fields,
        }

        if detected:
            self.publish(
                kind="thought",
                content=(
                    f"🔴 Injection detected!  "
                    f"Patterns: {detected_patterns[:5]}  |  "
                    f"Fields neutralised: {neutralized_fields}"
                ),
                payload=report,
            )
        else:
            self.publish(
                kind="thought",
                content="✅ No injection patterns detected – event is clean.",
            )

        return cleaned, report

    def analyze(
        self, event: dict, context: Optional[dict] = None
    ) -> Union[EvidenceChain, dict]:
        """Run sanitisation and return an EvidenceChain summarising the result."""
        cleaned, report = self.sanitize(event)

        evidence_items: List[EvidenceItem] = []
        if report["detected"]:
            evidence_items.append(
                EvidenceItem(
                    log_id=event.get("event_id", "unknown"),
                    timestamp=event.get("timestamp", ""),
                    excerpt="; ".join(report["patterns"][:5]),
                    why_relevant="Prompt-injection pattern matched in event fields.",
                )
            )

        chain = EvidenceChain(
            agent=self.name,
            conclusion=(
                f"Injection {'DETECTED and neutralised' if report['detected'] else 'not detected'}. "
                f"{len(report['patterns'])} pattern(s) matched across {len(report['neutralized_fields'])} field(s)."
            ),
            confidence=0.95 if report["detected"] else 0.99,
            evidence=evidence_items,
            mitre_techniques=["T1059.007"] if report["detected"] else [],
            next_actions=(
                ["Flag event for manual review", "Alert SOC on injection attempt"]
                if report["detected"]
                else []
            ),
        )
        return chain

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _scan_value(value: str) -> List[str]:
        """Return list of pattern descriptions that matched in *value*."""
        hits: List[str] = []
        for pat in INJECTION_PATTERNS:
            if pat.search(value):
                hits.append(pat.pattern[:80])
        return hits

    @staticmethod
    def _neutralize(value: str, _hits: List[str]) -> str:
        """Strip or escape dangerous content from *value*."""
        result = value
        # Remove zero-width characters
        result = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", result)
        # Escape HTML comments
        result = re.sub(r"<!--", "&lt;!--", result)
        result = re.sub(r"-->", "--&gt;", result)
        # Neutralise role tokens by wrapping in brackets
        result = re.sub(
            r"(?:^|\n)\s*(system|assistant|user)\s*:",
            r"[\1_token]:",
            result,
            flags=re.IGNORECASE,
        )
        # Prefix known jailbreak phrases
        for phrase in ("ignore previous", "ignore prior", "ignore above",
                       "disregard", "you are now", "act as", "pretend to be",
                       "DAN mode", "developer mode", "do anything now",
                       "jailbreak"):
            escaped = re.sub(
                re.escape(phrase),
                f"[BLOCKED:{phrase}]",
                result,
                flags=re.IGNORECASE,
            )
            result = escaped
        return result

    @staticmethod
    def _deep_get(d: dict, key: str) -> Any:
        """Get *key* from dict, checking top-level and one level of nesting."""
        if key in d:
            return d[key]
        for v in d.values():
            if isinstance(v, dict) and key in v:
                return v[key]
        return None

    @staticmethod
    def _deep_set(d: dict, key: str, value: Any) -> None:
        """Set *key* in dict at the level where it was found."""
        if key in d:
            d[key] = value
            return
        for v in d.values():
            if isinstance(v, dict) and key in v:
                v[key] = value
                return
