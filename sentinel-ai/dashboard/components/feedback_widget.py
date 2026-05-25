import streamlit as st
from sentinel.feedback.learning_loop import record_feedback

def render():
    st.subheader("Analyst Feedback")
    
    incident = st.session_state.get("current_incident")
    if not incident:
        st.info("No active incident to provide feedback on.")
        return
        
    incident_id = incident.get("incident_id")
    
    st.write(f"Provide feedback for **{incident_id}**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ True Positive"):
            record_feedback(incident_id, "true_positive")
            st.success("Feedback recorded: True Positive")
            
    with col2:
        if st.button("❌ False Positive"):
            record_feedback(incident_id, "false_positive")
            st.success("Feedback recorded: False Positive")
            
    with col3:
        if st.button("❓ Needs More Info"):
            record_feedback(incident_id, "needs_info")
            st.success("Feedback recorded: Needs More Info")
            
    if st.button("Replay Last Event"):
        st.info("Replaying event with new feedback context...")
        society = st.session_state.get("society")
        event = st.session_state.get("current_event")
        if society and event:
            # Re-process to show improved calibration
            society.process_event(event)
