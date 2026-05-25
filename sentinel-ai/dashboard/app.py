import sys
from pathlib import Path
import streamlit as st
import threading
import time
import json
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel.models import AgentMessage
from sentinel.orchestration.society import SentinelSociety
from sentinel.orchestration.message_bus import bus
from sentinel.storage.duckdb_store import init_db
from dashboard.components import live_agents, killchain_view, evidence_panel, speed_meter, feedback_widget, compliance_export

# --- Layout Configuration ---
st.set_page_config(
    page_title="SENTINEL-AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load CSS
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    with open(css_path, encoding='utf-8') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- State Initialization ---
if "society" not in st.session_state:
    init_db()
    st.session_state.society = SentinelSociety()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_event" not in st.session_state:
    st.session_state.current_event = None
if "current_incident" not in st.session_state:
    st.session_state.current_incident = None

# Update messages from bus
new_msgs = bus.get_history(limit=1000)
if new_msgs:
    st.session_state.messages = new_msgs
    
# Top Bar
st.markdown("<h1 style='text-align: center; color: #00d4ff;'>🛡️ SENTINEL-AI Operations Center</h1>", unsafe_allow_html=True)

if st.button("▶️ Run Multi-Stage Kill Chain Simulation"):
    def run_replay(society_instance):
        bus.clear_history() # Clear old runs
        path = Path(__file__).parent.parent / "data" / "attack_scenarios" / "multi_stage_killchain.jsonl"
        bus.publish(AgentMessage(from_agent="System", kind="thought", content=f"Starting replay of {path.name}"))
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                event = json.loads(line)
                bus.publish(AgentMessage(from_agent="System", kind="thought", content=f"Ingested event: {event.get('event_type')}"))
                society_instance.process_event(event)
                time.sleep(0.5)
                
    threading.Thread(target=run_replay, args=(st.session_state.society,), daemon=True).start()

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

# Query actual counts from DuckDB
try:
    con = st.session_state.society.sanitizer.get_duckdb_connection() # Fallback if we don't have direct access
except:
    from sentinel.storage.duckdb_store import get_store
    con = get_store().connection

try:
    events_count = con.cursor().execute("SELECT COUNT(*) FROM events").fetchone()
    events_count = events_count[0] if events_count else 0
    incidents_count = con.cursor().execute("SELECT COUNT(*) FROM incidents").fetchone()
    incidents_count = incidents_count[0] if incidents_count else 0
except Exception:
    events_count = 0
    incidents_count = 0

col1.metric("Events Processed", events_count)
col2.metric("Incidents Detected", incidents_count)
col3.metric("Tokens Generated", "14,520") # Static placeholder for demo
col4.metric("Est. Cost Saved", "$8,250") # Static placeholder for demo

st.markdown("---")

# Main 2-Column Layout
left_col, right_col = st.columns([3, 7])

with left_col:
    st.markdown("### 💬 Live Agent Society")
    live_agents.render()

with right_col:
    top_right_1, top_right_2 = st.columns([4, 3])
    
    # Fetch the latest incident from DuckDB
    try:
        latest_row = con.cursor().execute("SELECT evidence_json FROM incidents ORDER BY created_at DESC LIMIT 1").fetchone()
        evidence_chain = json.loads(latest_row[0]) if latest_row else None
        if not isinstance(evidence_chain, dict):
            evidence_chain = None
    except Exception:
        evidence_chain = None

    with top_right_1:
        st.markdown("### 🔍 Investigation")
        evidence_panel.render(evidence_chain)
        
    with top_right_2:
        st.markdown("### ⚡ Telemetry & Controls")
        feedback_widget.render()
        st.markdown("---")
        compliance_export.render()
        st.markdown("---")
        speed_meter.render()

    st.markdown("---")
    killchain_view.render(evidence_chain)

# Auto-refresh logic (crude way without streamlit-autorefresh)
time.sleep(1)
st.rerun()
