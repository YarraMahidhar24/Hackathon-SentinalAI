from typing import Dict, Any

def lookup(ip: str) -> Dict[str, Any]:
    """Offline GeoIP fallback for DEMO_MODE or when API key is missing."""
    if ip.startswith("10.") or ip.startswith("192.168."):
        return {"ip": ip, "country": "Internal Network", "city": "Internal", "latitude": 0.0, "longitude": 0.0}
    elif ip.startswith("45.33.32."):
        return {"ip": ip, "country": "US", "city": "San Francisco", "latitude": 37.7749, "longitude": -122.4194}
    elif ip.startswith("185.220.101."):
        return {"ip": ip, "country": "DE", "city": "Berlin", "latitude": 52.5200, "longitude": 13.4050, "note": "Known Tor exit node"}
    elif ip.startswith("41.") or ip.startswith("156."):
        return {"ip": ip, "country": "NG", "city": "Lagos", "latitude": 6.5244, "longitude": 3.3792}
    else:
        return {"ip": ip, "country": "Unknown", "city": "Unknown", "latitude": 0.0, "longitude": 0.0}
