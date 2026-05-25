"""
SENTINEL-AI in-process message bus.

A lightweight publish/subscribe bus that all agents use to communicate.
Messages are broadcast to subscribers and optionally persisted to DuckDB.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

from sentinel.models import AgentMessage, EvidenceChain, EvidenceItem

_lock = threading.Lock()
_instance: Optional["MessageBus"] = None

# Subscriber callback type
Subscriber = Callable[[AgentMessage], None]


class MessageBus:
    """In-process pub/sub message bus for agent-to-agent communication."""

    def __init__(self, persist: bool = True) -> None:
        self._subscribers: List[Subscriber] = []
        self._history: List[AgentMessage] = []
        self._lock = threading.Lock()
        self._persist = persist

    # ── Subscriptions ────────────────────────────────────────────────────────

    def subscribe(self, callback: Subscriber) -> None:
        """Register a subscriber callback."""
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Subscriber) -> None:
        """Remove a subscriber callback."""
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not callback]

    # ── Publishing ───────────────────────────────────────────────────────────

    def publish(self, message: AgentMessage) -> None:
        """Publish a message to all subscribers and optionally persist it."""
        with self._lock:
            self._history.append(message)
            subscribers = list(self._subscribers)

        # Deliver outside lock to avoid deadlocks
        for sub in subscribers:
            try:
                sub(message)
            except Exception:
                pass  # Don't let one bad subscriber break the bus

        # Persist to DuckDB
        if self._persist:
            try:
                from sentinel.storage.duckdb_store import get_duckdb_store

                store = get_duckdb_store()
                store.store_message(message.model_dump())
            except Exception:
                pass  # Storage failure should not break message flow

    # ── Convenience builders ─────────────────────────────────────────────────

    def send(
        self,
        from_agent: str,
        kind: str,
        content: str,
        to_agent: str = "broadcast",
        payload: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Build and publish a message in one call."""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            kind=kind,  # type: ignore[arg-type]
            content=content,
            payload=payload,
        )
        self.publish(msg)
        return msg

    # ── History access ───────────────────────────────────────────────────────

    def get_history(
        self, limit: int = 100, from_agent: Optional[str] = None
    ) -> List[AgentMessage]:
        """Return recent messages from the in-memory history."""
        with self._lock:
            history = list(self._history)
        if from_agent:
            history = [m for m in history if m.from_agent == from_agent]
        return history[-limit:]

    def clear_history(self) -> None:
        """Clear the in-memory history (does not affect DuckDB)."""
        with self._lock:
            self._history.clear()


def get_message_bus() -> MessageBus:
    """Return the global MessageBus singleton (thread-safe)."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MessageBus()
    return _instance

bus = get_message_bus()
