"""Sector Rotation Dashboard - terminal-aesthetic rewrite.

Run with: streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.universe import ALL_TICKERS, UNIVERSE_BY_CLASS, BENCH, class_of
from src.data import fetch_ohlcv
from src.indicators import compute_all_indicators
from src.flow import compute_flow_signals, flow_composite_z, STUB_MODE
from src.macro import assess_regime
from src.scoring import (
    compute_composite,
    apply_state_machine,
    recent_transitions,
)
from src.visuals import (
    sparkline,
    rrg_chart_dark,
    momentum_bar,
    price_chart_with_30wma,
    cmf_chart,
    obv_chart,
    color_for_state,
    STATE_COLOR,
    TERM_GREEN, TERM_RED, TERM_AMBER, TERM_BLUE, TERM_MUTED,
)


# =============================== page config =====================================

st.set_page_config(
    page_title="Sector Rotation",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================== theme css =======================================

def inject_css(dark: bool):
    fg = "#e6e6e6" if dark else "#111"
    bg = "#0a0a0a" if dark else "#fafafa"
    panel = "#141414" if dark else "#fff"
    border = "#222" if dark else "#e0e0e0"
    muted = "#8b8b8b" if dark else "#666"
    accent = "#5fa8d3"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --fg: {fg};
            --bg: {bg};
            --panel: {panel};
            --border: {border};
            --muted: {muted};
            --accent: {accent};
            --green: {TERM_GREEN};
            --red: {TERM_RED};
            --amber: {TERM_AMBER};
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: var(--fg) !important;
        }}
        .stApp {{
            background: var(--bg) !important;
        }}
        .mono, .num, code, pre {{
            font-family: 'JetBrains Mono', 'Menlo', monospace !important;
        }}

        /* status row tiles */
        .tile {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 6px;
        }}
        .tile .label {{
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 6px;
        }}
        .tile .value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.4rem;
            font-weight: 600;
        }}
        .tile .sub {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: var(--muted);
            margin-top: 4px;
        }}

        /* pill */
        .pill {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 11px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            font-weight: 600;
            color: #fff;
            letter-spacing: 0.03em;
        }}

        /* card */
        .card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-left: 3px solid var(--border);
            border-radius: 6px;
            padding: 12px 14px;
            margin-bottom: 8px;
            transition: border-color .15s ease;
        }}
        .card:hover {{
            border-left-color: var(--accent);
        }}
        .card .ticker {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.05rem;
            font-weight: 700;
            letter-spacing: 0.04em;
        }}
        .card .name {{
            font-size: 0.78rem;
            color: var(--muted);
            margin-bottom: 6px;
        }}
        .card .metrics {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: var(--fg);
            margin-top: 6px;
        }}
        .card .metrics .pos {{ color: var(--green); }}
        .card .metrics .neg {{ color: var(--red); }}
        .card .footer {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--muted);
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        /* alert row */
        .alert-row {{
            display: flex;
            align-items: center;
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.84rem;
        }}
        .alert-row:last-child {{ border-bottom: none; }}
        .alert-dot {{
            width: 8px; height: 8px;
            border-radius: 50%;
            margin-right: 12px;
            display: inline-block;
        }}
        .alert-ticker {{ font-weight: 700; min-width: 64px; }}
        .alert-state {{ flex: 1; color: var(--muted); }}
        .alert-time {{ color: var(--muted); }}

        /* section header */
        .section-h {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--muted);
            margin: 24px 0 10px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border);
        }}

        /* hide streamlit chrome */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}

        /* sidebar */
        section[data-testid="stSidebar"] {{
            background: var(--panel) !important;
            border-right: 1px solid var(--border);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================== data layer (cached) =============================

@st.cache_data(ttl=3600, show_spinner=False)
def _load_data(period: str = "3y") -> dict[str, pd.DataFrame]:
    tickers = ALL_TICKERS + ["^TNX", "^IRX"]
    return fetch_ohlcv(tickers, period=period)


# =============================== sidebar =========================================

with st.sidebar:
    st.markdown("### ⚙ CONTROLS")
    dark = st.toggle("Dark theme", value=True)
    period = st.selectbox("Lookback", ["3y", "5y", "max"], index=0)
    if st.button("🔄 Refresh data"):
        _load_data.clear()
        st.rerun()
    show_classes = st.multiselect(
        "Asset classes",
        options=list(UNIVERSE_BY_CLASS.keys()),
        default=list(UNIVERSE_BY_CLASS.keys()),
    )
    st.divider()
    st.caption(f"Flow stubs: **{'ON' if STUB_MODE else 'OFF'}**")
    st.caption("Cache TTL: 1 hour")

inject_css(dark)


# =============================== load + compute ==================================

with st.spinner("Loading market data..."):
    ohlcv = _load_data(period=period)

bench_ticker = BENCH["US"]
bil_ticker = BENCH["TBILL"]
if bench_ticker not in ohlcv or bil_ticker not in ohlcv:
    st.error(f"Missing benchmark/T-bill data. Hit Refresh and retry.")
    st.stop()

with st.spinner("Computing indicators..."):
    indicators_df = compute_all_indicators(ohlcv, bench_ticker, bil_ticker)
    flow_df = compute_flow_signals(ohlcv)
    flow_z = flow_composite_z(flow_df)
    regime = assess_regime(ohlcv[bench_ticker], ohlcv.get("^TNX"), ohlcv.get("^IRX"))
    scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
    scored = apply_state_machine(scored)


# =============================== header tiles ====================================

st.markdown(
    f"<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px;'>"
    f"<h1 style='margin:0;font-family:JetBrains Mono;font-size:1.6rem;letter-spacing:0.04em;'>📈 SECTOR ROTATION</h1>"
    f"<span class='mono' style='color:var(--muted);font-size:0.82rem;'>UPDATED {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# transitions
transitions = recent_transitions(n=20)
recent_count = len([t for t in transitions if t.get("to") in {"WARNING", "EXIT", "BEARISH_STAGE_4"}])

regime_color = TERM_GREEN if regime.risk_on else TERM_RED
regime_label = "RISK-ON" if regime.risk_on else "RISK-OFF"
curve_label  = "POSITIVE" if regime.yield_curve_positive else ("INVERTED" if regime.yield_curve_positive is False else "N/A")
curve_color  = TERM_GREEN if regime.yield_curve_positive else TERM_AMBER

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f"<div class='tile'>"
        f"<div class='label'>RISK REGIME</div>"
        f"<div class='value' style='color:{regime_color};'>{regime_label}</div>"
        f"<div class='sub'>{'SPY > 10mo SMA' if regime.risk_on else 'SPY < 10mo SMA'}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"<div class='tile'>"
        f"<div class='label'>CYCLE PHASE</div>"
        f"<div class='value' style='color:var(--fg);'>{regime.phase_hint}</div>"
        f"<div class='sub'>YIELD CURVE {curve_label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
with c3:
    alert_color = TERM_RED if recent_count > 0 else TERM_MUTED
    st.markdown(
        f"<div class='tile'>"
        f"<div class='label'>ACTIVE WARNINGS</div>"
        f"<div class='value' style='color:{alert_color};'>{recent_count}</div>"
        f"<div class='sub'>LAST 20 TRANSITIONS</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# =============================== alerts banner ===================================

st.markdown("<div class='section-h'>🔔 Recent state transitions</div>", unsafe_allow_html=True)

if not transitions:
    st.markdown(
        "<div class='alert-row'><span class='alert-state'>No state changes yet - the state machine starts logging from the first run.</span></div>",
        unsafe_allow_html=True,
    )
else:
    rows_html = []
    for t in transitions[:8]:
        new_state = t.get("to", "")
        dot_color = color_for_state(new_state)
        date_str = t.get("date", "")
        ticker = t.get("ticker", "")
        from_state = t.get("from", "")
        rows_html.append(
            f"<div class='alert-row'>"
            f"<span class='alert-dot' style='background:{dot_color};'></span>"
            f"<span class='alert-ticker'>{ticker}</span>"
            f"<span class='alert-state'>{from_state}  →  <b>{new_state}</b></span>"
            f"<span class='alert-time'>{date_str}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='background:var(--panel);border:1px solid var(--border);border-radius:6px;'>{''.join(rows_html)}</div>",
        unsafe_allow_html=True,
    )


# =============================== picks cards =====================================

st.markdown("<div class='section-h'>🎯 Current picks</div>", unsafe_allow_html=True)

display = scored[scored["class"].isin(show_classes)].copy()
picks = display[display["selected"]].sort_values(["class", "rank_in_class"])

if picks.empty:
    st.info("No selections meet the gates right now. The system is sitting in risk-off / defensive cash.")
else:
    # 4 cards per row
    cards_per_row = 4
    tickers_list = picks.index.tolist()
    for row_start in range(0, len(tickers_list), cards_per_row):
        cols = st.columns(cards_per_row)
        for i, ticker in enumerate(tickers_list[row_start: row_start + cards_per_row]):
            row = picks.loc[ticker]
            with cols[i]:
                state = row["state"]
                color = color_for_state(state)
                s_score = row["S_score"]
                f_score = row["F_score"]
                mom = row["mom_12_1"] * 100 if pd.notna(row["mom_12_1"]) else 0
                mom_class = "pos" if mom >= 0 else "neg"
                quad = row.get("rrg_quadrant") or "-"
                stage = row.get("stage") or "-"
                veto = " · VETO" if row.get("veto") else ""

                st.markdown(
                    f"<div class='card' style='border-left-color:{color};'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                    f"<span class='ticker'>{ticker}</span>"
                    f"<span class='pill' style='background:{color};'>{state}</span>"
                    f"</div>"
                    f"<div class='name'>{row['class']}</div>",
                    unsafe_allow_html=True,
                )
                # Sparkline
                if ticker in ohlcv:
                    st.plotly_chart(
                        sparkline(ohlcv[ticker], height=50),
                        use_container_width=True,
                        config={"displayModeBar": False, "staticPlot": True},
                    )
                st.markdown(
                    f"<div class='metrics'>"
                    f"S <b>{s_score:+.2f}</b>  ·  F <b>{f_score:+.2f}</b>{veto}<br>"
                    f"MOM <span class='{mom_class}'>{mom:+.1f}%</span>  ·  Stage {stage}<br>"
                    f"</div>"
                    f"<div class='footer'>{quad}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# =============================== big RRG =========================================

st.markdown("<div class='section-h'>🔄 Rotation</div>", unsafe_allow_html=True)

rrg_class = st.selectbox(
    "Universe",
    options=show_classes if show_classes else list(UNIVERSE_BY_CLASS.keys()),
    label_visibility="collapsed",
)
rrg_sub = display[display["class"] == rrg_class]
if not rrg_sub.empty:
    st.plotly_chart(
        rrg_chart_dark(rrg_sub, title=f"{rrg_class.upper()} - RELATIVE ROTATION"),
        use_container_width=True,
    )
else:
    st.info(f"No data for {rrg_class}.")


# =============================== full table (collapsed) ==========================

with st.expander("▼  Full 7-pillar table", expanded=False):
    cols_keep = [
        "class", "rank_in_class", "state", "S_score", "F_score",
        "mom_12_1", "faber", "stage", "mansfield_rs", "antonacci",
        "rs_ratio", "rs_momentum", "rrg_quadrant",
        "cmf21", "rvol", "dist_days_25", "obv_divergence",
        "breadth_50d", "selected", "veto",
    ]
    cols_keep = [c for c in cols_keep if c in display.columns]
    table = display[cols_keep].copy()
    if "mom_12_1" in table.columns:
        table["mom_12_1"] = (table["mom_12_1"] * 100).round(1)
    for c in ["S_score", "F_score", "mansfield_rs", "rs_ratio", "rs_momentum", "cmf21", "rvol"]:
        if c in table.columns:
            table[c] = table[c].round(3)
    if "breadth_50d" in table.columns:
        table["breadth_50d"] = (table["breadth_50d"] * 100).round(0)
    st.dataframe(table, use_container_width=True, height=520)


# =============================== per-ticker drilldown ============================

st.markdown("<div class='section-h'>🔍 Per-ticker drill-down</div>", unsafe_allow_html=True)
sel = st.selectbox(
    "Pick a ticker",
    options=sorted(display.index.tolist()),
    label_visibility="collapsed",
)
if sel and sel in ohlcv:
    row = display.loc[sel]
    state = row["state"]
    color = color_for_state(state)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f"<div class='tile'><div class='label'>COMPOSITE</div>"
        f"<div class='value mono'>{row['S_score']:+.3f}</div></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"<div class='tile'><div class='label'>FLOW</div>"
        f"<div class='value mono' style='color:{TERM_GREEN if row['F_score']>=0 else TERM_RED};'>{row['F_score']:+.3f}</div>"
        f"<div class='sub'>{'VETO' if row.get('veto') else 'OK'}</div></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"<div class='tile'><div class='label'>STATE</div>"
        f"<div class='value mono' style='color:{color};font-size:1.0rem;'>{state}</div></div>",
        unsafe_allow_html=True,
    )
    c4.markdown(
        f"<div class='tile'><div class='label'>RRG QUADRANT</div>"
        f"<div class='value mono' style='font-size:1.0rem;'>{row.get('rrg_quadrant', '-')}</div></div>",
        unsafe_allow_html=True,
    )

    st.plotly_chart(price_chart_with_30wma(ohlcv[sel], sel), use_container_width=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(cmf_chart(ohlcv[sel], sel), use_container_width=True)
    with col_r:
        st.plotly_chart(obv_chart(ohlcv[sel], sel), use_container_width=True)

    with st.expander("All indicator values for this ticker"):
        st.dataframe(row.to_frame(name="value"), use_container_width=True)
