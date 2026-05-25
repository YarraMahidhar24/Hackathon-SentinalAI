"""
SENTINEL-AI · Live Agent Society Panel

Streaming chat-style view of AgentMessage events with colour-coded
message bubbles, kind badges, and an animated thinking indicator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

# ── Agent colour map ─────────────────────────────────────────────────────────
AGENT_COLOURS: Dict[str, str] = {
    "Sanitizer":          "#ffaa00",
    "Triage":             "#00d4ff",
    "ThreatIntel":        "#4488ff",
    "Forensics":          "#00ccaa",
    "MitreMapper":        "#8855ff",
    "AdversaryEmulator":  "#ff8800",
    "RedTeamCritic":      "#ff3366",
    "IncidentCommander":  "#00ff88",
    "ComplianceReporter": "#888888",
}

AGENT_ICONS: Dict[str, str] = {
    "Sanitizer":          "🛡️",
    "Triage":             "🔍",
    "ThreatIntel":        "🌐",
    "Forensics":          "🔬",
    "MitreMapper":        "🗺️",
    "AdversaryEmulator":  "⚔️",
    "RedTeamCritic":      "🔴",
    "IncidentCommander":  "🟢",
    "ComplianceReporter": "📋",
}

KIND_LABELS: Dict[str, str] = {
    "thought":     "💭 thought",
    "question":    "❓ question",
    "answer":      "💬 answer",
    "critique":    "⚡ critique",
    "decision":    "⚖️ decision",
    "tool_call":   "🔧 tool_call",
    "tool_result": "📦 tool_result",
}


def _css_class_for_agent(agent_name: str) -> str:
    """Return the CSS class suffix for the given agent."""
    lookup = agent_name.lower().replace(" ", "").replace("_", "")
    return f"agent-msg-{lookup}"


def _kind_css(kind: str) -> str:
    return f"kind-{kind.replace(' ', '_')}"


def _render_message(msg: Any) -> str:
    """Build the HTML for a single agent-message bubble."""
    agent = getattr(msg, "from_agent", "Unknown")
    colour = AGENT_COLOURS.get(agent, "#888888")
    icon = AGENT_ICONS.get(agent, "🤖")
    css_cls = _css_class_for_agent(agent)
    kind = getattr(msg, "kind", "thought")
    kind_label = KIND_LABELS.get(kind, kind)
    kind_cls = _kind_css(kind)
    ts = getattr(msg, "ts", "")
    if ts and "T" in ts:
        ts = ts.split("T")[1][:8]
    content = getattr(msg, "content", "")
    # Escape basic HTML
    content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Preserve newlines
    content = content.replace("\n", "<br>")

    return f"""<div class="agent-msg {css_cls}">
    <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
            <span style="color:{colour};font-size:1rem;">{icon}</span>
            <span class="agent-name" style="color:{colour};">{agent}</span>
            <span class="kind-badge {kind_cls}">{kind_label}</span>
        </div>
        <span class="agent-timestamp">{ts}</span>
    </div>
    <div class="agent-content">{content}</div>
</div>"""


def _render_thinking_indicator(agent_name: str = "Agents") -> str:
    """Build the animated thinking-dots HTML."""
    colour = AGENT_COLOURS.get(agent_name, "#00d4ff")
    icon = AGENT_ICONS.get(agent_name, "🤖")
    return f"""<div class="thinking-indicator">
    <span style="color:{colour};font-size:1rem;">{icon}</span>
    <span style="color:{colour};font-weight:600;">{agent_name}</span>
    <span style="color:var(--text-secondary);">is reasoning</span>
    <div class="thinking-dots">
        <span></span><span></span><span></span>
    </div>
</div>"""


# ── Public API ───────────────────────────────────────────────────────────────

def render() -> None:
    """Render the Live Agent Society panel."""
    st.markdown(
        """<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
    <span style="font-size:1.3rem;">🧠</span>
    <span style="font-weight:700;font-size:1.05rem;
                 background:linear-gradient(135deg,#00d4ff,#8855ff);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text;">
        Agent Society
    </span>
    <span class="live-dot"></span>
    <span style="font-size:0.7rem;color:#8888a0;text-transform:uppercase;letter-spacing:0.1em;">Live</span>
</div>""",
        unsafe_allow_html=True,
    )

    messages: List[Dict[str, Any]] = st.session_state.get("messages", [])
    is_processing: bool = st.session_state.get("replay_active", False)

    # Fixed-height scrollable container
    container_html_parts: List[str] = []

    if not messages:
        container_html_parts.append(
            """<div style="display:flex;flex-direction:column;align-items:center;
            justify-content:center;height:100%;padding:60px 20px;
            color:#555570;text-align:center;border:1px dashed rgba(255,255,255,0.1);border-radius:12px;">
    <div style="font-size:3.5rem;margin-bottom:12px;">🛰️</div>
    <div style="font-size:1.2rem;font-weight:600;color:#e8e8f0;">Awaiting telemetry…</div>
    <div style="font-size:0.9rem;margin-top:6px;color:#8888a0;">
        Click the <b style="color:#00d4ff;">▶ Run Simulation</b> button to watch the agents work
    </div>
</div>"""
        )
    else:
        if is_processing:
            # Determine which agent is currently thinking
            thinking_agent = "Agents"
            if messages:
                last = messages[-1]
                # Guess the *next* agent from the last message
                pipeline = [
                    "Sanitizer", "Triage", "ThreatIntel", "Forensics",
                    "MitreMapper", "AdversaryEmulator", "RedTeamCritic",
                    "IncidentCommander",
                ]
                last_agent = getattr(last, "from_agent", "")
                if last_agent in pipeline:
                    idx = pipeline.index(last_agent)
                    if idx + 1 < len(pipeline):
                        thinking_agent = pipeline[idx + 1]
                    else:
                        thinking_agent = "IncidentCommander"
            container_html_parts.append(_render_thinking_indicator(thinking_agent))

        for msg in reversed(messages):
            if getattr(msg, "content", "") == "speed_sample":
                continue
            container_html_parts.append(_render_message(msg))



    all_html = "\n".join(container_html_parts)

    # Wrap in a scrollable div that auto-scrolls to bottom
    wrapper = f"""<div id="agent-feed" style="
    height:72vh;
    display:flex;
    flex-direction:column-reverse;
    overflow-y:auto;
    padding:16px;
    border:1px solid rgba(255,255,255,0.06);
    border-radius:12px;
    background:linear-gradient(180deg, rgba(10,10,15,0.8) 0%, rgba(15,15,22,0.95) 100%);
    box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
">
{all_html}
</div>"""
    st.markdown(wrapper, unsafe_allow_html=True)
