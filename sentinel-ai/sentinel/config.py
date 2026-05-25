"""
SENTINEL-AI configuration module.

Loads settings from .env file and environment variables.
Provides centralized access to all configuration values.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_env_path = _PROJECT_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Try .env.example as fallback for demo mode
    _example = _PROJECT_ROOT / ".env.example"
    if _example.exists():
        load_dotenv(_example)

# ── API Keys ─────────────────────────────────────────────────────────────────
CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
ABUSEIPDB_API_KEY: str = os.getenv("ABUSEIPDB_API_KEY", "")
VIRUSTOTAL_API_KEY: str = os.getenv("VIRUSTOTAL_API_KEY", "")

# ── Storage Paths ────────────────────────────────────────────────────────────
SENTINEL_DB_PATH: str = os.getenv("SENTINEL_DB_PATH", str(_PROJECT_ROOT / "sentinel.duckdb"))
SENTINEL_CHROMA_PATH: str = os.getenv("SENTINEL_CHROMA_PATH", str(_PROJECT_ROOT / "chroma_db"))

# ── Ingestion ────────────────────────────────────────────────────────────────
SENTINEL_REPLAY_RATE: int = int(os.getenv("SENTINEL_REPLAY_RATE", "5"))

# ── Demo Mode ────────────────────────────────────────────────────────────────
SENTINEL_DEMO_MODE: bool = os.getenv("SENTINEL_DEMO_MODE", "true").lower() in ("true", "1", "yes")

# Auto-enable demo mode if Cerebras key is missing
if not CEREBRAS_API_KEY:
    SENTINEL_DEMO_MODE = True

# ── LLM Config ───────────────────────────────────────────────────────────────
CEREBRAS_MODEL: str = "gpt-oss-120b"
CEREBRAS_MAX_TOKENS: int = 4096
CEREBRAS_TEMPERATURE: float = 0.3

# ── Project Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT: Path = _PROJECT_ROOT
DATA_DIR: Path = _PROJECT_ROOT / "data"
ATTACK_SCENARIOS_DIR: Path = DATA_DIR / "attack_scenarios"
SEED_INCIDENTS_PATH: Path = DATA_DIR / "seed_incidents.json"

# ── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_REFRESH_INTERVAL: float = 0.5  # seconds
MAX_AGENT_MESSAGES_DISPLAY: int = 200

# ── Agent Config ─────────────────────────────────────────────────────────────
MAX_DEBATE_ROUNDS: int = 2
FORENSICS_WINDOW_MINUTES: int = 15
TRIAGE_DEDUP_WINDOW_SECONDS: int = 60
