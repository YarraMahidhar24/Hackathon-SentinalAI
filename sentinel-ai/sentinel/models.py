"""
SENTINEL-AI core data models.

Defines the canonical Pydantic models used across all modules:
- EvidenceItem / EvidenceChain for forensic evidence tracking
- AgentMessage for inter-agent communication on the message bus
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single piece of forensic evidence."""

    log_id: str
    timestamp: str
    excerpt: str
    why_relevant: str


class EvidenceChain(BaseModel):
    """An agent's conclusion backed by evidence."""

    agent: str
    conclusion: str
    confidence: float = Field(ge=0, le=1)
    evidence: List[EvidenceItem] = []
    mitre_techniques: List[str] = []
    next_actions: List[str] = []


class AgentMessage(BaseModel):
    """Message exchanged between agents on the message bus."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    from_agent: str
    to_agent: str = "broadcast"
    kind: Literal[
        "thought",
        "question",
        "answer",
        "critique",
        "decision",
        "tool_call",
        "tool_result",
    ]
    content: str
    payload: Optional[Dict[str, Any]] = None
