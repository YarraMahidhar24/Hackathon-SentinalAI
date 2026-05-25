"""
SENTINEL-AI VirusTotal enrichment module.

Queries the VirusTotal v3 API for hash, domain, and IP reputation.
Falls back to deterministic demo data when in demo mode.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from sentinel import config

logger = logging.getLogger(__name__)

_DEMO_DATA: Dict[str, Any] = {
    "indicator": "unknown",
    "indicator_type": "unknown",
    "malicious": 12,
    "suspicious": 3,
    "undetected": 55,
    "harmless": 2,
    "reputation": -45,
    "tags": ["trojan", "botnet"],
    "last_analysis_date": "2025-11-28T00:00:00Z",
    "demo": True,
}


def virustotal_lookup(indicator: str) -> Dict[str, Any]:
    """Look up a hash, domain, or IP address against VirusTotal.

    Automatically detects the indicator type based on format.
    Returns a dict with detection stats, reputation, and tags.
    """
    indicator_type = _classify_indicator(indicator)

    if config.SENTINEL_DEMO_MODE or not config.VIRUSTOTAL_API_KEY:
        result = dict(_DEMO_DATA)
        result["indicator"] = indicator
        result["indicator_type"] = indicator_type
        return result

    path_map = {
        "hash": f"https://www.virustotal.com/api/v3/files/{indicator}",
        "domain": f"https://www.virustotal.com/api/v3/domains/{indicator}",
        "ip": f"https://www.virustotal.com/api/v3/ip_addresses/{indicator}",
    }
    url = path_map.get(indicator_type, path_map["hash"])
    headers = {"x-apikey": config.VIRUSTOTAL_API_KEY}

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            attrs = resp.json().get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            return {
                "indicator": indicator,
                "indicator_type": indicator_type,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
                "reputation": attrs.get("reputation", 0),
                "tags": attrs.get("tags", []),
                "last_analysis_date": attrs.get("last_analysis_date", ""),
                "demo": False,
            }
    except Exception as exc:
        logger.error("VirusTotal lookup failed for %s: %s", indicator, exc)
        result = dict(_DEMO_DATA)
        result["indicator"] = indicator
        result["indicator_type"] = indicator_type
        return result


def _classify_indicator(value: str) -> str:
    """Heuristic to classify an indicator as hash, domain, or ip."""
    stripped = value.strip()
    # MD5 (32), SHA1 (40), SHA256 (64)
    if stripped.isalnum() and len(stripped) in (32, 40, 64):
        return "hash"
    # Simple IP check
    parts = stripped.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return "ip"
    return "domain"
