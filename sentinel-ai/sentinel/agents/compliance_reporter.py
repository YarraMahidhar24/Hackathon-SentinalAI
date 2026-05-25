from typing import Dict, Any, Optional
import io
from sentinel.agents.base import BaseAgent
from sentinel.llm.prompts import COMPLIANCE_REPORTER_SYSTEM_PROMPT
from sentinel.orchestration.message_bus import EvidenceChain
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

class ComplianceReporterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="ComplianceReporterAgent", system_prompt=COMPLIANCE_REPORTER_SYSTEM_PROMPT)

    def analyze(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> EvidenceChain:
        self.publish("thought", "Generating compliance reports based on the final decision...")
        evidence_chain = context.get("evidence_chain") if context else None
        
        prompt = (
            f"Final Incident Decision:\n{evidence_chain}\n\n"
            "Generate three concise compliance report summaries based on this incident:\n"
            "1. SOC2 Type II (Focus on access controls and anomaly detection)\n"
            "2. ISO 27001 Annex A (Focus on incident management and mitigation)\n"
            "3. GDPR Article 33 (Focus on data breach impact and notification timelines)\n"
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # We don't need structured output here, just text
        result_text = self.llm_chat(messages)
        
        # Format the text as a mock chain
        chain = EvidenceChain(
            agent=self.name,
            conclusion=result_text,
            confidence=1.0,
            evidence=[],
            mitre_techniques=[],
            next_actions=[]
        )
        self.publish("thought", "Compliance reports generated successfully.")
        return chain

    def generate_pdf(self, title: str, content: str) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 12))
        
        for paragraph in content.split('\n\n'):
            story.append(Paragraph(paragraph, styles['BodyText']))
            story.append(Spacer(1, 12))
            
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
