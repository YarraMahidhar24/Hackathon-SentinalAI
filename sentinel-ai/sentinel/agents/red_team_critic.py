from typing import Dict, Any, Optional
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import RED_TEAM_CRITIC_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain

class RedTeamCriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="RedTeamCriticAgent", system_prompt=RED_TEAM_CRITIC_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        draft_conclusion = context.get("draft_conclusion", "") if context else ""
        self.publish("thought", "Analyzing Commander's draft. Looking for weaknesses, alternative explanations, or benign hypotheses...")
        
        prompt = (
            f"Target Event: {event}\n\n"
            f"Incident Commander's Draft Conclusion:\n{draft_conclusion}\n\n"
            "Critique this conclusion. Be adversarial but logical. Try to falsify it."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self.llm_chat(messages, response_model=EvidenceChain)
        if isinstance(result, EvidenceChain):
            result.agent = self.name
            self.publish("critique", result.conclusion, payload=result.model_dump())
        return result
