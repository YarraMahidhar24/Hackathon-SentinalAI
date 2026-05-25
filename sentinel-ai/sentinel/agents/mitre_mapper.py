from typing import Dict, Any, Optional
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import MITRE_MAPPER_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain

class MitreMapperAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="MitreMapperAgent", system_prompt=MITRE_MAPPER_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        self.publish("thought", "Analyzing event behavior to map against MITRE ATT&CK techniques...")
        
        prompt = (
            f"Event Data: {event}\n\n"
            "Analyze the event and map any observed behaviors to the appropriate MITRE ATT&CK techniques."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self.llm_chat(messages, response_model=EvidenceChain)
        if isinstance(result, EvidenceChain):
            result.agent = self.name
        return result
