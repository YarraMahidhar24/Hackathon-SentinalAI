"""
SENTINEL-AI DuckDB helper.

Provides a singleton connection to the project DuckDB database and
convenience methods for event storage and retrieval.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import duckdb

from sentinel import config

logger = logging.getLogger(__name__)


class DuckDBStore:
    """Singleton wrapper around the project DuckDB file."""

    _instance: Optional["DuckDBStore"] = None

    def __new__(cls) -> "DuckDBStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self) -> None:
        self._con = duckdb.connect(config.SENTINEL_DB_PATH)
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id   VARCHAR PRIMARY KEY,
                timestamp  TIMESTAMP,
                event_type VARCHAR,
                source_ip  VARCHAR,
                dest_ip    VARCHAR,
                user_name  VARCHAR,
                hostname   VARCHAR,
                raw_json   VARCHAR
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS enrichment_cache (
                indicator  VARCHAR PRIMARY KEY,
                source     VARCHAR,
                data_json  VARCHAR,
                cached_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id VARCHAR PRIMARY KEY,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                severity    VARCHAR,
                conclusion  VARCHAR,
                evidence_json VARCHAR
            )
            """
        )

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    # ── Events ───────────────────────────────────────────────────────────

    def insert_event(self, event: Dict[str, Any]) -> None:
        """Insert or ignore a raw event dict."""
        import json as _json

        self._con.execute(
            """
            INSERT OR IGNORE INTO events
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event.get("event_id", ""),
                event.get("timestamp", datetime.utcnow().isoformat()),
                event.get("event_type", ""),
                event.get("source_ip", ""),
                event.get("dest_ip", ""),
                event.get("user", ""),
                event.get("hostname", ""),
                _json.dumps(event),
            ],
        )

    def get_related_events(
        self,
        *,
        source_ip: str = "",
        user_name: str = "",
        hostname: str = "",
        center_time: Optional[str] = None,
        window_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """Return events matching any of the provided filters within a time window."""
        import json as _json

        if center_time:
            try:
                center = datetime.fromisoformat(center_time.replace("Z", "+00:00"))
            except ValueError:
                center = datetime.utcnow()
        else:
            center = datetime.utcnow()

        lo = (center - timedelta(minutes=window_minutes)).isoformat()
        hi = (center + timedelta(minutes=window_minutes)).isoformat()

        conditions: list[str] = []
        params: list[Any] = []

        if source_ip:
            conditions.append("(source_ip = ? OR dest_ip = ?)")
            params.extend([source_ip, source_ip])
        if user_name:
            conditions.append("user_name = ?")
            params.append(user_name)
        if hostname:
            conditions.append("hostname = ?")
            params.append(hostname)

        if not conditions:
            return []

        where = " OR ".join(conditions)
        query = (
            f"SELECT raw_json FROM events "
            f"WHERE ({where}) AND timestamp BETWEEN ? AND ? "
            f"ORDER BY timestamp"
        )
        params.extend([lo, hi])

        try:
            rows = self._con.execute(query, params).fetchall()
            valid_rows = []
            for row in rows:
                if row and isinstance(row[0], (str, bytes, bytearray)):
                    valid_rows.append(_json.loads(row[0]))
            return valid_rows
        except Exception as exc:
            logger.warning("DuckDB query failed: %s", exc)
            return []

    # ── Enrichment cache ─────────────────────────────────────────────────

    def get_cached_enrichment(self, indicator: str, source: str) -> Optional[Dict[str, Any]]:
        import json as _json

        try:
            rows = self._con.execute(
                "SELECT data_json FROM enrichment_cache WHERE indicator = ? AND source = ?",
                [indicator, source],
            ).fetchall()
            if rows:
                return _json.loads(rows[0][0])
        except Exception:
            pass
        return None

    def cache_enrichment(self, indicator: str, source: str, data: Dict[str, Any]) -> None:
        import json as _json

        self._con.execute(
            "INSERT OR REPLACE INTO enrichment_cache VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            [indicator, source, _json.dumps(data)],
        )

    # ── Incidents ────────────────────────────────────────────────────────

    def save_incident(self, incident_id: str, severity: str, conclusion: str, evidence_json: str) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO incidents VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)",
            [incident_id, severity, conclusion, evidence_json],
        )

    @classmethod
    def reset(cls) -> None:
        if cls._instance is not None:
            try:
                cls._instance._con.close()
            except Exception:
                pass
        cls._instance = None


def get_store() -> DuckDBStore:
    """Module-level accessor for the DuckDB singleton."""
    return DuckDBStore()

def init_db():
    get_store()._init_db()

def insert_event(event: Dict[str, Any]):
    get_store().insert_event(event)

def insert_incident(incident_record: Dict[str, Any]):
    get_store().save_incident(
        incident_id=incident_record.get('incident_id', ''),
        severity=incident_record.get('severity', 'medium'),
        conclusion=incident_record.get('conclusion', ''),
        evidence_json=incident_record.get('evidence_json', '[]')
    )

def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    con = get_store().connection
    rows = con.execute("SELECT incident_id, severity, conclusion, evidence_json FROM incidents WHERE incident_id = ?", [incident_id]).fetchall()
    if rows:
        row = rows[0]
        return {
            "incident_id": row[0],
            "severity": row[1],
            "conclusion": row[2],
            "evidence_json": row[3]
        }
    return None

def get_events_in_window(ts: str, minutes: int, user: str = "", host: str = "", src_ip: str = "") -> List[Dict[str, Any]]:
    return get_store().get_related_events(
        center_time=ts,
        window_minutes=minutes,
        user_name=user,
        hostname=host,
        source_ip=src_ip
    )

def insert_feedback(incident_id: str, label: str, notes: str):
    con = get_store().connection
    con.execute("CREATE TABLE IF NOT EXISTS feedback (incident_id VARCHAR, label VARCHAR, notes VARCHAR, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    con.execute("INSERT INTO feedback VALUES (?, ?, ?, CURRENT_TIMESTAMP)", [incident_id, label, notes])

def log_llm_call(**kwargs):
    # Optional stub for logging LLM calls if needed
    pass
