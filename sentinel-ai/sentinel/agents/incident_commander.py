from typing import Dict, Any, Optional
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import INCIDENT_COMMANDER_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain
from sentinel.feedback.learning_loop import get_past_cases_for_prompt

class IncidentCommanderAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="IncidentCommanderAgent", system_prompt=INCIDENT_COMMANDER_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        self.publish("thought", "Synthesizing squad outputs into a draft conclusion...")
        
        # Inject few-shot cases
        event_summary = str(event)
        past_cases = get_past_cases_for_prompt(event_summary, n=3)
        prompt_with_cases = self.system_prompt.replace("{past_cases}", past_cases)
        
        squad_outputs = context.get("squad_outputs", {}) if context else {}
        critique = context.get("critique", None) if context else None
        
        if critique:
            prompt = (
                f"Target Event: {event}\n\n"
                f"Squad Findings: {squad_outputs}\n\n"
                f"Red Team Critic Challenge:\n{critique}\n\n"
                "Address the critique. Either revise your conclusion or defend it. Produce the final verdict."
            )
        else:
             prompt = (
                f"Target Event: {event}\n\n"
                f"Squad Findings: {squad_outputs}\n\n"
                "Synthesize these findings into a comprehensive incident draft conclusion."
            )

        messages = [
            {"role": "system", "content": prompt_with_cases},
            {"role": "user", "content": prompt}
        ]
        
        result = self.llm_chat(messages, response_model=EvidenceChain)
        if isinstance(result, EvidenceChain):
            result.agent = self.name
            self.publish("decision", result.conclusion, payload=result.model_dump())
        return result
