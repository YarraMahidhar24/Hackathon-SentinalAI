"""
SENTINEL-AI · MITRE ATT&CK Kill-Chain Timeline

Horizontal timeline rendered with Plotly, mapping detected techniques
to their ATT&CK tactical phases.  Dark-theme, gradient-coloured.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import plotly.graph_objects as go
import streamlit as st

# ── ATT&CK Tactical Phases (Enterprise) ─────────────────────────────────────
ATTACK_PHASES: List[Dict[str, str]] = [
    {"id": "TA0001", "name": "Initial\nAccess"},
    {"id": "TA0002", "name": "Execution"},
    {"id": "TA0003", "name": "Persistence"},
    {"id": "TA0004", "name": "Priv\nEscalation"},
    {"id": "TA0005", "name": "Defense\nEvasion"},
    {"id": "TA0006", "name": "Credential\nAccess"},
    {"id": "TA0007", "name": "Discovery"},
    {"id": "TA0008", "name": "Lateral\nMovement"},
    {"id": "TA0009", "name": "Collection"},
    {"id": "TA0010", "name": "Exfiltration"},
    {"id": "TA0040", "name": "Impact"},
]

# Technique-ID → tactical phase mapping (partial lookup for common techniques)
_TECHNIQUE_TO_PHASE: Dict[str, str] = {
    "T1190": "TA0001", "T1566": "TA0001", "T1078": "TA0001", "T1133": "TA0001",
    "T1195": "TA0001", "T1199": "TA0001",
    "T1059": "TA0002", "T1203": "TA0002", "T1204": "TA0002", "T1047": "TA0002",
    "T1569": "TA0002", "T1053": "TA0002",
    "T1098": "TA0003", "T1136": "TA0003", "T1543": "TA0003", "T1547": "TA0003",
    "T1546": "TA0003", "T1053": "TA0003",
    "T1548": "TA0004", "T1134": "TA0004", "T1068": "TA0004", "T1484": "TA0004",
    "T1055": "TA0005", "T1070": "TA0005", "T1036": "TA0005", "T1027": "TA0005",
    "T1562": "TA0005", "T1218": "TA0005", "T1112": "TA0005",
    "T1110": "TA0006", "T1003": "TA0006", "T1552": "TA0006", "T1558": "TA0006",
    "T1555": "TA0006",
    "T1087": "TA0007", "T1082": "TA0007", "T1083": "TA0007", "T1046": "TA0007",
    "T1135": "TA0007", "T1018": "TA0007", "T1057": "TA0007",
    "T1021": "TA0008", "T1570": "TA0008", "T1563": "TA0008", "T1080": "TA0008",
    "T1560": "TA0009", "T1005": "TA0009", "T1119": "TA0009", "T1074": "TA0009",
    "T1041": "TA0010", "T1048": "TA0010", "T1567": "TA0010", "T1537": "TA0010",
    "T1486": "TA0040", "T1489": "TA0040", "T1490": "TA0040", "T1498": "TA0040",
    "T1496": "TA0040", "T1485": "TA0040", "T1499": "TA0040",
}


def _resolve_phase(technique_id: str) -> Optional[str]:
    """Map a technique ID (e.g. T1059, T1059.001) to a tactic phase ID."""
    base = technique_id.split(".")[0].upper()
    # Direct lookup
    if base in _TECHNIQUE_TO_PHASE:
        return _TECHNIQUE_TO_PHASE[base]
    # Already a tactic ID
    if base.startswith("TA"):
        return base
    return None


def _build_figure(detected_phase_ids: Set[str], technique_labels: Dict[str, List[str]]) -> go.Figure:
    """Build the Plotly horizontal timeline figure."""
    n = len(ATTACK_PHASES)
    xs = list(range(n))
    labels = [p["name"] for p in ATTACK_PHASES]
    phase_ids = [p["id"] for p in ATTACK_PHASES]

    # Colour gradient: blue (early) → red (late)
    def _gradient(i: int) -> str:
        r = int(30 + (225 * i / (n - 1)))
        g = int(140 - (100 * i / (n - 1)))
        b = int(255 - (200 * i / (n - 1)))
        return f"rgb({r},{g},{b})"

    # Empty vs filled
    colours = []
    sizes = []
    symbols = []
    hover_texts = []
    border_widths = []
    border_colors = []
    opacities = []

    for i, pid in enumerate(phase_ids):
        if pid in detected_phase_ids:
            colours.append(_gradient(i))
            sizes.append(42)
            symbols.append("circle")
            border_widths.append(4)
            border_colors.append("rgba(255,255,255,0.8)")
            opacities.append(1.0)
            techs = technique_labels.get(pid, [])
            hover_texts.append(
                f"<b>{labels[i].replace(chr(10),' ')}</b><br>"
                + ("<br>".join(techs) if techs else "Detected")
            )
        else:
            colours.append("rgba(85,85,112,0.3)")
            sizes.append(28)
            symbols.append("circle-open")
            border_widths.append(2)
            border_colors.append("rgba(85,85,112,0.5)")
            opacities.append(0.4)
            hover_texts.append(f"<b>{labels[i].replace(chr(10),' ')}</b><br><i>Not detected</i>")

    fig = go.Figure()

    # Connector line
    fig.add_trace(go.Scatter(
        x=xs, y=[0] * n,
        mode="lines",
        line=dict(color="rgba(85,85,112,0.3)", width=3, dash="dot"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Phase nodes
    fig.add_trace(go.Scatter(
        x=xs, y=[0] * n,
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=colours,
            symbol=symbols,
            line=dict(width=border_widths, color=border_colors),
            opacity=opacities,
        ),
        text=labels,
        textposition="bottom center",
        textfont=dict(size=12, color="rgba(232,232,240,0.7)", family="Inter"),
        hovertext=hover_texts,
        hoverinfo="text",
        hoverlabel=dict(
            bgcolor="#12121a",
            bordercolor="#00d4ff",
            font=dict(color="#e8e8f0", family="Inter", size=14),
        ),
        showlegend=False,
    ))

    fig.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=30, b=80),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False,
            range=[-0.5, n - 0.5],
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False,
            range=[-1, 1],
        ),
        font=dict(family="Inter"),
    )

    return fig


# ── Public API ───────────────────────────────────────────────────────────────

def render(evidence_chain: Optional[Dict[str, Any]] = None) -> None:
    """Render the MITRE Kill-Chain Timeline.

    Parameters
    ----------
    evidence_chain : dict | None
        A dict with at least a ``mitre_techniques`` list of technique IDs.
    """
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="font-size:1.1rem;">🗺️</span>
            <span style="font-weight:700;font-size:0.95rem;
                         background:linear-gradient(135deg,#8855ff,#ff3366);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         background-clip:text;">
                ATT&CK Kill Chain
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    techniques: List[str] = []
    if evidence_chain:
        techniques = evidence_chain.get("mitre_techniques", [])

    detected_phases: Set[str] = set()
    phase_techniques: Dict[str, List[str]] = {}

    for t in techniques:
        phase = _resolve_phase(t)
        if phase:
            detected_phases.add(phase)
            phase_techniques.setdefault(phase, []).append(t)

    fig = _build_figure(detected_phases, phase_techniques)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if techniques:
        tech_str = "  ".join(
            [f"`{t}`" for t in techniques]
        )
        st.markdown(
            f"<div style='font-size:0.75rem;color:#8888a0;text-align:center;'>"
            f"Detected: {tech_str}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='font-size:0.75rem;color:#555570;text-align:center;'>"
            "No techniques detected yet</div>",
            unsafe_allow_html=True,
        )
