import streamlit as st

def render():
    st.subheader("Compliance Export")
    
    incident = st.session_state.get("current_incident")
    if not incident:
        st.info("No active incident to export.")
        return
        
    incident_id = incident.get("incident_id")
    society = st.session_state.get("society")
    
    if st.button("Generate Reports"):
        with st.spinner("Generating reports..."):
            reports = society.generate_compliance_reports(incident_id)
            if reports:
                st.success("Reports generated successfully!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📄 Download Markdown",
                        data=reports.get("markdown", ""),
                        file_name=f"{incident_id}_compliance.md",
                        mime="text/markdown"
                    )
                with col2:
                    st.download_button(
                        label="📋 Download PDF",
                        data=reports.get("pdf_bytes", b""),
                        file_name=f"{incident_id}_compliance.pdf",
                        mime="application/pdf"
                    )
                    
                with st.expander("Preview"):
                    st.markdown(reports.get("markdown", ""))
            else:
                st.error("Failed to generate reports.")
