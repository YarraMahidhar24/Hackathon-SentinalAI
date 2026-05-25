"""
SENTINEL-AI · Evidence Panel

Displays the current evidence chain: event card, severity badge,
confidence meter, evidence items, conclusion, and next actions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

# ── Severity → colour map ───────────────────────────────────────────────────
_SEV_COLOURS: Dict[str, str] = {
    "low":      "#00d4ff",
    "medium":   "#ffaa00",
    "high":     "#ff8800",
    "critical": "#ff3366",
}

_SEV_EMOJI: Dict[str, str] = {
    "low":      "🔵",
    "medium":   "🟡",
    "high":     "🟠",
    "critical": "🔴",
}


def _confidence_class(val: float) -> str:
    if val < 0.4:
        return "confidence-low"
    if val < 0.7:
        return "confidence-medium"
    return "confidence-high"


def _render_event_card(event: Dict[str, Any]) -> str:
    """Build the current-event card HTML."""
    raw = event.get("raw", event.get("content", ""))
    if isinstance(raw, dict):
        import json
        raw = json.dumps(raw, indent=2)
    raw_esc = str(raw).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    injection = event.get("injection_detected", False)
    injection_badge = ""
    if injection:
        injection_badge = (
            '<span class="badge-injection" style="margin-left:10px;">'
            "🛡️ INJECTION NEUTRALIZED</span>"
        )

    return f"""
    <div class="glass-card" style="border-left:3px solid #00d4ff;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <span style="font-weight:700;color:#00d4ff;font-size:0.9rem;">📡 Current Event</span>
            {injection_badge}
        </div>
        <div class="evidence-excerpt">{raw_esc}</div>
    </div>
    """


def _render_severity_badge(severity: str) -> str:
    sev = severity.lower()
    colour = _SEV_COLOURS.get(sev, "#888888")
    emoji = _SEV_EMOJI.get(sev, "⚪")
    css = f"severity-{sev}"
    return (
        f'<span class="severity-badge {css}">{emoji} {severity.upper()}</span>'
    )


def _render_confidence_bar(confidence: float) -> str:
    pct = max(0, min(100, int(confidence * 100)))
    cls = _confidence_class(confidence)
    colour_label = "#00ff88" if confidence >= 0.7 else ("#00d4ff" if confidence >= 0.4 else "#ffaa00")
    return f"""
    <div style="margin:10px 0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:0.75rem;color:#8888a0;text-transform:uppercase;letter-spacing:0.08em;">
                Confidence
            </span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{colour_label};">
                {pct}%
            </span>
        </div>
        <div class="confidence-meter">
            <div class="confidence-fill {cls}" style="width:{pct}%;"></div>
        </div>
    </div>
    """


def _render_evidence_item(item: Dict[str, Any], idx: int) -> str:
    log_id = item.get("log_id", f"log-{idx}")
    ts = item.get("timestamp", "")
    excerpt = str(item.get("excerpt", "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    why = str(item.get("why_relevant", "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""
    <div class="evidence-card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#00d4ff;">
                {log_id}
            </span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#555570;">
                {ts}
            </span>
        </div>
        <div class="evidence-excerpt">{excerpt}</div>
        <div class="evidence-why">💡 {why}</div>
    </div>
    """


# ── Public API ───────────────────────────────────────────────────────────────

def render(evidence_chain: Optional[Dict[str, Any]] = None) -> None:
    """Render the Evidence Panel.

    Parameters
    ----------
    evidence_chain : dict | None
        Dict matching the EvidenceChain schema:
        ``agent``, ``conclusion``, ``confidence``, ``evidence``,
        ``mitre_techniques``, ``next_actions``.
    """
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="font-size:1.1rem;">🔎</span>
            <span style="font-weight:700;font-size:0.95rem;
                         background:linear-gradient(135deg,#00d4ff,#00ff88);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         background-clip:text;">
                Evidence &amp; Analysis
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Current event card
    current_event: Optional[Dict[str, Any]] = st.session_state.get("current_event")
    if current_event:
        st.markdown(_render_event_card(current_event), unsafe_allow_html=True)

    if not evidence_chain:
        st.markdown(
            """
            <div style="text-align:center;padding:40px 20px;color:#555570;">
                <div style="font-size:2.5rem;margin-bottom:8px;">🔍</div>
                <div style="font-size:0.9rem;font-weight:600;color:#8888a0;">
                    No evidence collected yet
                </div>
                <div style="font-size:0.75rem;margin-top:4px;">
                    Evidence will appear here once agents begin analysis
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Header row: severity + agent
    agent = evidence_chain.get("agent", "Unknown")
    confidence = float(evidence_chain.get("confidence", 0.0))

    # Derive severity from confidence heuristic
    if confidence >= 0.85:
        severity = "critical"
    elif confidence >= 0.65:
        severity = "high"
    elif confidence >= 0.4:
        severity = "medium"
    else:
        severity = "low"

    # Check if evidence_chain carries an explicit severity
    severity = evidence_chain.get("severity", severity)

    header_html = f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        {_render_severity_badge(severity)}
        <span style="font-size:0.8rem;color:#8888a0;">Assessed by
            <b style="color:#e8e8f0;">{agent}</b>
        </span>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # Confidence bar
    st.markdown(_render_confidence_bar(confidence), unsafe_allow_html=True)

    # Conclusion
    conclusion = evidence_chain.get("conclusion", "")
    if conclusion:
        st.markdown(
            f"""
            <div class="glass-card" style="border-left:3px solid #00ff88;padding:14px 16px;">
                <div style="font-size:0.7rem;color:#8888a0;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">
                    📋 Conclusion
                </div>
                <div style="font-size:0.85rem;color:#e8e8f0;line-height:1.6;">
                    {conclusion}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Evidence items
    evidence_items: List[Dict[str, Any]] = evidence_chain.get("evidence", [])
    if evidence_items:
        st.markdown(
            "<div style='font-size:0.8rem;font-weight:600;color:#8888a0;"
            "margin:12px 0 6px;text-transform:uppercase;letter-spacing:0.08em;'>"
            f"📎 Evidence Items ({len(evidence_items)})</div>",
            unsafe_allow_html=True,
        )
        items_html = "\n".join(
            _render_evidence_item(item, idx)
            for idx, item in enumerate(evidence_items)
        )
        st.markdown(items_html, unsafe_allow_html=True)

    # Next actions
    next_actions: List[str] = evidence_chain.get("next_actions", [])
    if next_actions:
        st.markdown(
            "<div style='font-size:0.8rem;font-weight:600;color:#8888a0;"
            "margin:12px 0 6px;text-transform:uppercase;letter-spacing:0.08em;'>"
            "🚀 Recommended Actions</div>",
            unsafe_allow_html=True,
        )
        actions_html = ""
        for action in next_actions:
            actions_html += (
                f"<div style='padding:6px 12px;margin-bottom:4px;"
                f"background:rgba(0,212,255,0.06);border-radius:6px;"
                f"font-size:0.8rem;color:#e8e8f0;border-left:2px solid #00d4ff;'>"
                f"→ {action}</div>"
            )
        st.markdown(actions_html, unsafe_allow_html=True)
