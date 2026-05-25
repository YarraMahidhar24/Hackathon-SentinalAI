from sentinel.orchestration.message_bus import EvidenceChain

def run_debate(commander, critic, draft_chain: EvidenceChain, evidence_context: dict, max_rounds: int = 2) -> EvidenceChain:
    """Runs a debate loop between the Incident Commander and Red Team Critic."""
    
    current_draft = draft_chain
    
    for round_num in range(max_rounds):
        # 1. Critic challenges the draft
        critique_context = evidence_context.copy()
        critique_context["draft_conclusion"] = current_draft.conclusion
        
        critique_chain = critic.analyze(event=evidence_context.get("event"), context=critique_context)
        
        if not critique_chain or not critique_chain.conclusion:
            break
            
        # 2. Commander revises or defends
        revision_context = evidence_context.copy()
        revision_context["squad_outputs"] = evidence_context.get("squad_outputs")
        revision_context["critique"] = critique_chain.conclusion
        
        revised_chain = commander.analyze(event=evidence_context.get("event"), context=revision_context)
        
        if not revised_chain:
            break
            
        # 3. Decision logic
        if revised_chain.confidence >= current_draft.confidence:
            # Confidence increased or stayed same, accept revision
            current_draft = revised_chain
            break
        else:
            # Confidence dropped significantly, maybe the critic is right
            current_draft = revised_chain
            
    return current_draft
