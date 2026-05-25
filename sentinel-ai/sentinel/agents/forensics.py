from typing import Dict, Any, Optional
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import FORENSICS_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain, EvidenceItem
from sentinel.storage.duckdb_store import get_events_in_window
from sentinel.config import FORENSICS_WINDOW_MINUTES

class ForensicsAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="ForensicsAgent", system_prompt=FORENSICS_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        self.publish("thought", f"Fetching related events within +/- {FORENSICS_WINDOW_MINUTES} minutes...")
        
        user = event.get("user")
        host = event.get("host")
        src_ip = event.get("source_ip")
        
        related_events = get_events_in_window(
            ts=event.get("timestamp", ""),
            minutes=FORENSICS_WINDOW_MINUTES,
            user=user,
            host=host,
            src_ip=src_ip
        )
        
        self.publish("thought", f"Found {len(related_events)} related events.")
        
        prompt = (
            f"Target Event: {event}\n\n"
            f"Context Window (+/- {FORENSICS_WINDOW_MINUTES} min): {related_events}\n\n"
            "Analyze the timeline and reconstruct the sequence of activities."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self.llm_chat(messages, response_model=EvidenceChain)
        if isinstance(result, EvidenceChain):
            result.agent = self.name
        return result
