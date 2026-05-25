"""
SENTINEL-AI Triage Agent.

Sits after the Sanitizer in the pipeline and makes a fast
drop / monitor / investigate decision for every incoming event.

Strategy
--------
1. **Deterministic whitelist** – configurable set of safe IPs / usernames
   that are always dropped.
2. **Deduplication window** – if the same ``(event_type, source_ip)`` was
   seen within the last N seconds, suppress the duplicate.
3. **Few-shot similarity** – queries ChromaDB for top-3 similar past
   incidents and injects them as context.
4. **LLM decision** – for uncertain events, asks the LLM to classify as
   drop / monitor / investigate.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from sentinel import config
from sentinel.agents.base import BaseAgent
from sentinel.llm import prompts
from sentinel.orchestration.message_bus import EvidenceChain, EvidenceItem
from sentinel.storage.chroma_store import search_similar_incidents

logger = logging.getLogger(__name__)

# ── Configurable whitelist ───────────────────────────────────────────────────

_DEFAULT_WHITELIST_IPS = {
    "127.0.0.1",
    "::1",
    "10.0.0.1",       # default gateway
    "192.168.1.1",     # default gateway
}

_DEFAULT_WHITELIST_USERS = {
    "SYSTEM",
    "LOCAL SERVICE",
    "NETWORK SERVICE",
}


class TriageAgent(BaseAgent):
    """Fast triage agent – drop, monitor, or escalate."""

    def __init__(
        self,
        whitelist_ips: Optional[set[str]] = None,
        whitelist_users: Optional[set[str]] = None,
    ) -> None:
        super().__init__(name="TriageAgent", system_prompt=prompts.TRIAGE_SYSTEM_PROMPT)
        self._whitelist_ips = whitelist_ips or _DEFAULT_WHITELIST_IPS
        self._whitelist_users = whitelist_users or _DEFAULT_WHITELIST_USERS
        # Dedup window: key → last-seen epoch
        self._seen: Dict[str, float] = {}
        self._dedup_seconds = config.TRIAGE_DEDUP_WINDOW_SECONDS

    # ── Core API ─────────────────────────────────────────────────────────

    def analyze(
        self, event: dict, context: Optional[dict] = None
    ) -> Union[EvidenceChain, dict]:
        """Triage *event* and return a decision dict.

        Returns
        -------
        dict with ``decision`` (drop / monitor / investigate),
        ``reasoning``, and ``confidence``.
        """
        # 1. Whitelist check
        src_ip = event.get("source_ip", "")
        user = event.get("user", "")
        if src_ip in self._whitelist_ips or user.upper() in self._whitelist_users:
            self.publish(
                kind="decision",
                content=f"DROPPED – whitelisted (ip={src_ip}, user={user})",
                payload={"decision": "drop", "reason": "whitelist"},
            )
            return {
                "decision": "drop",
                "reasoning": f"Source {src_ip or user} is whitelisted.",
                "confidence": 1.0,
            }

        # 2. Dedup window
        dedup_key = f"{event.get('event_type', '')}::{src_ip}"
        now = time.time()
        last_seen = self._seen.get(dedup_key, 0.0)
        if now - last_seen < self._dedup_seconds:
            self.publish(
                kind="decision",
                content=f"DROPPED – duplicate within {self._dedup_seconds}s window",
                payload={"decision": "drop", "reason": "dedup"},
            )
            return {
                "decision": "drop",
                "reasoning": "Duplicate event within dedup window.",
                "confidence": 0.95,
            }
        self._seen[dedup_key] = now

        # 3. Few-shot similarity search
        similar = self._find_similar_incidents(event)

        # 4. LLM decision
        decision_data = self._llm_triage(event, similar)

        decision = decision_data.get("decision", "investigate")
        reasoning = decision_data.get("reasoning", "LLM analysis")
        confidence = float(decision_data.get("confidence", 0.5))

        self.publish(
            kind="decision",
            content=f"Triage → {decision.upper()} (conf={confidence:.2f}): {reasoning[:120]}",
            payload=decision_data,
        )

        return {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "similar_incidents": similar,
        }

    # ── Private helpers ──────────────────────────────────────────────────

    def _find_similar_incidents(self, event: dict) -> List[Dict[str, Any]]:
        """Query ChromaDB for similar past incidents."""
        summary_parts = [
            event.get("event_type", ""),
            event.get("description", ""),
            event.get("alert_name", ""),
            event.get("message", ""),
        ]
        query_text = " ".join(p for p in summary_parts if p).strip()
        if not query_text:
            query_text = json.dumps(event)[:500]

        try:
            return search_similar_incidents(query_text, n=3)
        except Exception as exc:
            logger.warning("ChromaDB similarity search failed: %s", exc)
            return []

    def _llm_triage(self, event: dict, similar: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ask the LLM to triage the event, with optional few-shot context."""
        few_shot_block = ""
        if similar:
            examples = []
            for hit in similar:
                examples.append(f"- Past incident: {hit.get('document', '')[:200]}")
            few_shot_block = (
                "\n\nSimilar past incidents for reference:\n" + "\n".join(examples)
            )

        user_content = (
            f"Security event to triage:\n```json\n{json.dumps(event, default=str)[:2000]}\n```"
            f"{few_shot_block}"
        )

        messages = [{"role": "user", "content": user_content}]
        reply = self.llm_chat(messages)
        return self.safe_parse_json(reply)
