"""
SENTINEL-AI AbuseIPDB enrichment module.

Queries the AbuseIPDB v2 API for IP reputation data.
Falls back to deterministic demo data when in demo mode or if the API key
is missing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from sentinel import config

logger = logging.getLogger(__name__)

_DEMO_DATA: Dict[str, Any] = {
    "ip": "unknown",
    "abuse_confidence_score": 85,
    "total_reports": 142,
    "country_code": "RU",
    "isp": "DemoISP Ltd.",
    "domain": "demo-malicious.example.com",
    "is_tor": False,
    "is_whitelisted": False,
    "last_reported_at": "2025-12-01T00:00:00Z",
    "usage_type": "Data Center/Web Hosting/Transit",
    "demo": True,
}


def abuseipdb_lookup(ip: str) -> Dict[str, Any]:
    """Look up an IP address against AbuseIPDB.

    Returns a dict with abuse confidence score, report count, ISP, etc.
    In demo mode or on API failure, returns deterministic stub data.
    """
    if config.SENTINEL_DEMO_MODE or not config.ABUSEIPDB_API_KEY:
        result = dict(_DEMO_DATA)
        result["ip"] = ip
        return result

    url = "https://api.abuseipdb.com/api/v2/check"
    headers = {
        "Key": config.ABUSEIPDB_API_KEY,
        "Accept": "application/json",
    }
    params = {"ipAddress": ip, "maxAgeInDays": "90"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "ip": data.get("ipAddress", ip),
                "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                "total_reports": data.get("totalReports", 0),
                "country_code": data.get("countryCode", ""),
                "isp": data.get("isp", ""),
                "domain": data.get("domain", ""),
                "is_tor": data.get("isTor", False),
                "is_whitelisted": data.get("isWhitelisted", False),
                "last_reported_at": data.get("lastReportedAt", ""),
                "usage_type": data.get("usageType", ""),
                "demo": False,
            }
    except Exception as exc:
        logger.error("AbuseIPDB lookup failed for %s: %s", ip, exc)
        result = dict(_DEMO_DATA)
        result["ip"] = ip
        return result
