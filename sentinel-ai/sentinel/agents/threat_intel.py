from typing import Dict, Any, Optional
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import THREAT_INTEL_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain

class ThreatIntelAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="ThreatIntelAgent", system_prompt=THREAT_INTEL_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        self.publish("thought", "Enriching IP addresses against known threat feeds...")
        
        prompt = (
            f"Event Data: {event}\n\n"
            "Analyze the IP addresses in the event data against your internal threat feeds. "
            "Report enrichment results as evidence items."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self.llm_chat(messages, response_model=EvidenceChain)
        if isinstance(result, EvidenceChain):
            result.agent = self.name
        return result
