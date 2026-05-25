from typing import Dict, Any, List
import concurrent.futures
import json
import uuid

from sentinel.orchestration.message_bus import bus, AgentMessage, EvidenceChain
from sentinel.orchestration.debate import run_debate
from sentinel.storage.duckdb_store import insert_event, insert_incident
from sentinel.storage.chroma_store import store_incident

from sentinel.agents.sanitizer import SanitizerAgent
from sentinel.agents.triage import TriageAgent
from sentinel.agents.threat_intel import ThreatIntelAgent
from sentinel.agents.forensics import ForensicsAgent
from sentinel.agents.mitre_mapper import MitreMapperAgent
from sentinel.agents.adversary_emulator import AdversaryEmulatorAgent
from sentinel.agents.incident_commander import IncidentCommanderAgent
from sentinel.agents.red_team_critic import RedTeamCriticAgent
from sentinel.agents.compliance_reporter import ComplianceReporterAgent

class SentinelSociety:
    def __init__(self):
        self.sanitizer = SanitizerAgent()
        self.triage = TriageAgent()
        
        self.investigators = [
            ThreatIntelAgent(),
            ForensicsAgent(),
            MitreMapperAgent(),
            AdversaryEmulatorAgent()
        ]
        
        self.commander = IncidentCommanderAgent()
        self.critic = RedTeamCriticAgent()
        self.reporter = ComplianceReporterAgent()

    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Main orchestration pipeline."""
        
        # 1. Sanitize
        clean_event, injection_report = self.sanitizer.sanitize(event)
        
        # Save to DuckDB immediately
        event_id = str(uuid.uuid4())
        clean_event['event_id'] = event_id
        insert_event(clean_event)
        
        # 2. Triage
        triage_decision = self.triage.analyze(clean_event)
        
        if triage_decision.get("decision") != "investigate":
            return {"status": "dropped", "reason": triage_decision.get("reason")}
            
        # 3. Parallel Fan-out
        squad_results = self._run_parallel_analysis(clean_event)
        
        # 4. Draft Conclusion
        context = {"squad_outputs": squad_results, "event": clean_event}
        draft_chain = self.commander.analyze(event=clean_event, context=context)
        
        # 5. Debate
        final_chain = run_debate(
            commander=self.commander,
            critic=self.critic,
            draft_chain=draft_chain,
            evidence_context=context
        )
        
        # 6. Save Incident
        incident_id = f"INC-{event_id[:8]}"
        incident_record = {
            "incident_id": incident_id,
            "ts": clean_event.get("ts"),
            "severity": getattr(final_chain, 'severity', 'medium'), # Default severity
            "conclusion": final_chain.conclusion,
            "confidence": final_chain.confidence,
            "evidence_json": final_chain.model_dump_json(),
            "mitre_techniques": json.dumps(final_chain.mitre_techniques),
            "agent_decisions": json.dumps(squad_results)
        }
        
        insert_incident(incident_record)
        
        # Save to vector memory
        store_incident(
            incident_id=incident_id,
            summary_text=final_chain.conclusion,
            metadata={"severity": incident_record["severity"]}
        )
        
        return {"status": "investigated", "incident_id": incident_id, "evidence_chain": final_chain}

    def _run_parallel_analysis(self, event: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.investigators)) as executor:
            future_to_agent = {
                executor.submit(agent.analyze, event): agent.name 
                for agent in self.investigators
            }
            
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    result = future.result()
                    results[agent_name] = result.model_dump() if isinstance(result, EvidenceChain) else result
                except Exception as exc:
                    results[agent_name] = {"error": str(exc)}
                    
        return results
        
    def generate_compliance_reports(self, incident_id: str) -> Dict[str, Any]:
        from sentinel.storage.duckdb_store import get_incident
        
        incident = get_incident(incident_id)
        if not incident:
            return {}
            
        context = {"evidence_chain": incident}
        reports = self.reporter.analyze(event={}, context=context)
        
        return {
            "markdown": reports.conclusion,
            "pdf_bytes": self.reporter.generate_pdf(f"Report for {incident_id}", reports.conclusion)
        }
