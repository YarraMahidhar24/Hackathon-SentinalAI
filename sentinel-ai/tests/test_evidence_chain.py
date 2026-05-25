import pytest
from pydantic import ValidationError
from sentinel.orchestration.message_bus import EvidenceChain, EvidenceItem

def test_valid_chain():
    chain = EvidenceChain(
        agent="TestAgent",
        conclusion="Looks bad",
        confidence=0.8,
        evidence=[
            EvidenceItem(log_id="1", timestamp="now", excerpt="foo", why_relevant="bar")
        ]
    )
    assert chain.confidence == 0.8

def test_confidence_bounds():
    with pytest.raises(ValidationError):
        EvidenceChain(agent="Test", conclusion="Bad", confidence=1.5)

def test_empty_evidence():
    chain = EvidenceChain(agent="Test", conclusion="Bad", confidence=0.5)
    assert len(chain.evidence) == 0

def test_serialization():
    chain = EvidenceChain(agent="Test", conclusion="Bad", confidence=0.5)
    dumped = chain.model_dump()
    assert dumped["agent"] == "Test"
