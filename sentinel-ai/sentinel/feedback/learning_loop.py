import json
from sentinel.storage.duckdb_store import insert_feedback, get_incident
from sentinel.storage.chroma_store import store_feedback, search_feedback, search_similar_incidents

def record_feedback(incident_id: str, label: str, notes: str = '') -> None:
    """Record analyst feedback into DuckDB and ChromaDB."""
    # 1. Write to DuckDB
    insert_feedback(incident_id, label, notes)
    
    # 2. Get incident details
    incident = get_incident(incident_id)
    if not incident:
        return
        
    summary_text = incident.get('conclusion', '')
    
    # 3. Embed into ChromaDB 'analyst_feedback' collection
    metadata = {
        "incident_id": incident_id,
        "label": label,
        "notes": notes,
        "severity": incident.get('severity', 'unknown')
    }
    store_feedback(incident_id, summary_text, label, metadata)

def get_past_cases_for_prompt(event_summary: str, n: int = 3) -> str:
    """Retrieve similar past incidents and format as few-shot examples."""
    cases = []
    
    # Try finding analyst feedback first (higher quality examples)
    feedback_cases = search_feedback(event_summary, n=n)
    if feedback_cases:
        for case in feedback_cases:
            meta = case.get('metadata', {})
            doc = case.get('document', '')
            cases.append(f"Case {len(cases)+1} (Label: {meta.get('label')}): {doc}")
            
    # If we need more, get generic past incidents
    if len(cases) < n:
        similar_cases = search_similar_incidents(event_summary, n=(n - len(cases)))
        if similar_cases:
            for case in similar_cases:
                 meta = case.get('metadata', {})
                 doc = case.get('document', '')
                 # Avoid duplicates if it's already in feedback_cases
                 if meta.get('incident_id') not in [c.split(':')[0] for c in cases]:
                    cases.append(f"Case {len(cases)+1} (Label: {meta.get('outcome', 'unknown')}): {doc}")
                    
    if not cases:
        return "No similar past cases found."
        
    return "\n\n".join(cases)
