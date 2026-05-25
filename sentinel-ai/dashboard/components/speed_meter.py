"""
SENTINEL-AI · Cerebras Speed Meter

Live tokens/sec display, rolling average, peak value, Plotly gauge,
and a side-by-side SOC speed comparator.
"""

from __future__ import annotations

from typing import Any, Dict, List

import plotly.graph_objects as go
import streamlit as st

# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_gauge(current_tps: float, peak_tps: float) -> go.Figure:
    """Build a Plotly radial gauge for tokens-per-second."""
    max_val = max(peak_tps * 1.3, 5000)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=current_tps,
        number=dict(
            font=dict(size=36, color="#00d4ff", family="JetBrains Mono"),
            suffix=" tok/s",
        ),
        gauge=dict(
            axis=dict(
                range=[0, max_val],
                tickwidth=1,
                tickcolor="rgba(85,85,112,0.3)",
                tickfont=dict(size=9, color="#555570"),
            ),
            bar=dict(color="#00d4ff", thickness=0.3),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                dict(range=[0, max_val * 0.33], color="rgba(0,212,255,0.05)"),
                dict(range=[max_val * 0.33, max_val * 0.66], color="rgba(0,255,136,0.05)"),
                dict(range=[max_val * 0.66, max_val], color="rgba(255,51,102,0.05)"),
            ],
            threshold=dict(
                line=dict(color="#ff3366", width=3),
                thickness=0.75,
                value=peak_tps,
            ),
        ),
    ))

    fig.update_layout(
        height=180,
        margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter"),
    )

    return fig


# ── Public API ───────────────────────────────────────────────────────────────

def render() -> None:
    """Render the Cerebras Speed Meter panel."""
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="font-size:1.1rem;">⚡</span>
            <span style="font-weight:700;font-size:0.95rem;
                         background:linear-gradient(135deg,#00d4ff,#00ff88);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         background-clip:text;">
                Cerebras Speed
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    speed_samples: List[float] = st.session_state.get("speed_samples", [])
    total_tokens: int = st.session_state.get("total_tokens", 0)
    processing_start: float = st.session_state.get("processing_start_time", 0)

    # Compute metrics
    current_tps = speed_samples[-1] if speed_samples else 0.0
    avg_tps = sum(speed_samples) / len(speed_samples) if speed_samples else 0.0
    peak_tps = max(speed_samples) if speed_samples else 0.0

    # Gauge chart
    fig = _build_gauge(current_tps, peak_tps)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Stats row
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;
                            font-weight:700;color:#00d4ff;">{current_tps:,.0f}</div>
                <div style="font-size:0.6rem;color:#8888a0;text-transform:uppercase;
                            letter-spacing:0.1em;">Current</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;
                            font-weight:700;color:#00ff88;">{avg_tps:,.0f}</div>
                <div style="font-size:0.6rem;color:#8888a0;text-transform:uppercase;
                            letter-spacing:0.1em;">Average</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:1.2rem;
                            font-weight:700;color:#ff3366;">{peak_tps:,.0f}</div>
                <div style="font-size:0.6rem;color:#8888a0;text-transform:uppercase;
                            letter-spacing:0.1em;">Peak</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── SOC Speed Comparator ─────────────────────────────────────────────
    st.markdown(
        """
        <div style="font-size:0.75rem;font-weight:600;color:#8888a0;
                    text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;">
            ⏱️ Response Time Comparison
        </div>
        """,
        unsafe_allow_html=True,
    )

    import time
    elapsed = 0.0
    if processing_start > 0:
        elapsed = time.time() - processing_start

    left, right = st.columns(2)

    with left:
        st.markdown(
            """
            <div class="comparator-box comparator-traditional">
                <div style="font-size:1.5rem;margin-bottom:4px;">⏳</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:1.4rem;
                            font-weight:800;color:#ff3366;">~45 min</div>
                <div style="font-size:0.65rem;color:#8888a0;text-transform:uppercase;
                            letter-spacing:0.08em;margin-top:4px;">Traditional SOC</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        if elapsed > 0:
            if elapsed < 60:
                time_str = f"{elapsed:.1f}s"
            else:
                mins = int(elapsed // 60)
                secs = elapsed % 60
                time_str = f"{mins}m {secs:.0f}s"
        else:
            time_str = "—"

        sentinel_colour = "#00ff88" if elapsed > 0 else "#555570"
        st.markdown(
            f"""
            <div class="comparator-box comparator-sentinel">
                <div style="font-size:1.5rem;margin-bottom:4px;">⚡</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:1.4rem;
                            font-weight:800;color:{sentinel_colour};">{time_str}</div>
                <div style="font-size:0.65rem;color:#8888a0;text-transform:uppercase;
                            letter-spacing:0.08em;margin-top:4px;">SENTINEL-AI</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Speed-up factor
    if elapsed > 0:
        speedup = (45 * 60) / max(elapsed, 0.01)
        st.markdown(
            f"""
            <div style="text-align:center;margin-top:10px;padding:8px;
                        background:rgba(0,255,136,0.06);border:1px solid rgba(0,255,136,0.2);
                        border-radius:8px;">
                <span style="font-size:0.8rem;color:#00ff88;font-weight:700;">
                    ⚡ {speedup:,.0f}× faster
                </span>
                <span style="font-size:0.7rem;color:#8888a0;">
                     than traditional SOC
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Total tokens generated
    st.markdown(
        f"""
        <div style="text-align:center;margin-top:10px;font-size:0.7rem;color:#555570;">
            Total tokens generated: <b style="color:#8888a0;">
            {total_tokens:,}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )
