from typing import Dict, Any, Optional
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import ADVERSARY_EMULATOR_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain

class AdversaryEmulatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="AdversaryEmulatorAgent", system_prompt=ADVERSARY_EMULATOR_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        self.publish("thought", "Putting on my attacker hat. Predicting likely next moves...")
        
        prompt = (
            f"Current Event Data: {event}\n\n"
            f"Context / Other Findings: {context}\n\n"
            "If you were the attacker, what are your 2-3 most likely next actions? "
            "Put your predictions in the 'next_actions' array."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self.llm_chat(messages, response_model=EvidenceChain)
        if isinstance(result, EvidenceChain):
            result.agent = self.name
        return result
