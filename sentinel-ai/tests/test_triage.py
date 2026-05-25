import pytest
from sentinel.agents.triage import TriageAgent

@pytest.fixture
def triage():
    return TriageAgent()

def test_whitelist_drops(triage):
    # Depending on implementation, assuming 10.0.0.1 is safe
    event = {"src_ip": "10.0.0.1", "event_type": "network"}
    # The actual triage logic might use the LLM if whitelist fails
    # Just a placeholder test
    pass

def test_suspicious_investigates(triage):
    pass

def test_dedup_filters(triage):
    pass
