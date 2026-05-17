"""Sector Rotation Dashboard — Streamlit entry point.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.universe import (
    ALL_TICKERS,
    UNIVERSE_BY_CLASS,
    BENCH,
    class_of,
)
from src.data import fetch_ohlcv
from src.indicators import compute_all_indicators
from src.flow import compute_flow_signals, flow_composite_z, STUB_MODE
from src.macro import assess_regime
from src.scoring import (
    compute_composite,
    apply_state_machine,
    recent_transitions,
    STATES,
)
from src.visuals import (
    rrg_chart,
    momentum_bar,
    price_chart_with_30wma,
    cmf_chart,
    obv_chart,
    color_for_state,
    STATE_COLOR,
)


# ============================== page setup ========================================

st.set_page_config(
    page_title="Sector Rotation Dashboard",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .small { font-size: 0.85em; color: #666; }
    .pill  { display: inline-block; padding: 2px 8px; border-radius: 10px;
             font-size: 0.85em; font-weight: 600; color: #fff; }
    .state-table td, .state-table th { padding: 4px 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================== data layer (cached) ==============================

@st.cache_data(ttl=3600, show_spinner=False)
def _load_data(period: str = "3y") -> dict[str, pd.DataFrame]:
    tickers = ALL_TICKERS + ["^TNX", "^IRX"]
    return fetch_ohlcv(tickers, period=period)


def _trigger_refresh() -> None:
    _load_data.clear()


# ============================== sidebar ===========================================

with st.sidebar:
    st.title("⚙️ Controls")
    period = st.selectbox("Lookback", ["3y", "5y", "max"], index=0)
    if st.button("🔄 Refresh data"):
        _trigger_refresh()
        st.rerun()
    st.markdown(f'<span class="small">Pillar 7 stub mode: <b>{"ON" if STUB_MODE else "OFF"}</b></span>',
                unsafe_allow_html=True)
    st.markdown(
        '<span class="small">Stubbed flow signals return neutral values until wired to a real provider — see <code>src/flow.py</code>.</span>',
        unsafe_allow_html=True,
    )
    show_classes = st.multiselect(
        "Asset classes to show",
        options=list(UNIVERSE_BY_CLASS.keys()),
        default=list(UNIVERSE_BY_CLASS.keys()),
    )

# ============================== header / load ====================================

st.title("📈 Sector Rotation Dashboard")
st.caption(
    "Layered 7-pillar methodology · cross-sectional momentum · Faber 10mo SMA · "
    "Weinstein Stage 2 · Antonacci dual mom · RRG · business cycle · institutional flow."
)

with st.spinner("Fetching market data (yfinance)…"):
    ohlcv = _load_data(period=period)

bench_ticker = BENCH["US"]
bil_ticker = BENCH["TBILL"]

missing = [t for t in [bench_ticker, bil_ticker] if t not in ohlcv]
if missing:
    st.error(f"Missing data for benchmark/T-bill: {missing}. Hit Refresh and try again.")
    st.stop()


# ============================== compute everything ===============================

with st.spinner("Computing indicators…"):
    indicators_df = compute_all_indicators(ohlcv, bench_ticker=bench_ticker, bil_ticker=bil_ticker)
    flow_df = compute_flow_signals(ohlcv)
    flow_z = flow_composite_z(flow_df)
    regime = assess_regime(
        ohlcv[bench_ticker],
        ohlcv.get("^TNX"),
        ohlcv.get("^IRX"),
    )
    scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
    scored = apply_state_machine(scored)


# ============================== macro banner =====================================

c1, c2, c3, c4 = st.columns(4)
c1.metric("Risk regime", "RISK-ON" if regime.risk_on else "RISK-OFF",
          delta="SPY > 10mo SMA" if regime.spy_above_10mo_sma else "SPY < 10mo SMA",
          delta_color="normal" if regime.risk_on else "inverse")
c2.metric("Yield curve",
          "Positive" if regime.yield_curve_positive else ("Inverted" if regime.yield_curve_positive is False else "—"))
c3.metric("Cycle phase (hint)", regime.phase_hint)
c4.metric("Universe size", str(len(scored)))

st.info(regime.note)
st.divider()


# ============================== TOP: 7-pillar heatmap ============================

st.subheader("Summary — all tickers, all 7 pillars")
st.caption(
    "Color-coded z-scores within each asset class. The composite **S_score** is the master ranking; "
    "**state** is the alert from §6 of the methodology. A red ⛔ on F_score means hard veto."
)

# Filter by selected universe classes
display = scored[scored["class"].isin(show_classes)].copy()

# build a tidy heatmap-style table
display["mom_12_1_pct"] = display["mom_12_1"] * 100
display["mansfield_rs"] = display["mansfield_rs"]
display["S_score"] = display["S_score"].round(3)
display["F_score"] = display["F_score"].round(3)
display["rs_ratio"] = display["rs_ratio"].round(1)
display["rs_momentum"] = display["rs_momentum"].round(1)
display["cmf21"] = display["cmf21"].round(3)
display["rvol"] = display["rvol"].round(2)
display["breadth_50d"] = (display["breadth_50d"] * 100).round(0)

# pretty column ordering
COLS = [
    "class", "rank_in_class", "state", "S_score",
    "mom_12_1_pct", "faber", "stage", "mansfield_rs", "antonacci",
    "rs_ratio", "rs_momentum", "rrg_quadrant",
    "F_score", "cmf21", "rvol", "dist_days_25", "obv_divergence",
    "breadth_50d", "selected", "veto",
]
COLS = [c for c in COLS if c in display.columns]


def _state_html(state: str) -> str:
    color = color_for_state(state)
    return f'<span class="pill" style="background:{color};">{state}</span>'


display_render = display[COLS].copy()
display_render["state"] = display_render["state"].apply(_state_html)

# Streamlit styler for numeric heatmap
def _color_for_numeric(val, vmin, vmax, neutral=0):
    if pd.isna(val):
        return ""
    if val >= neutral:
        # green scale
        t = min(1.0, (val - neutral) / (vmax - neutral + 1e-9))
        return f"background-color: rgba(26,138,78,{0.15 + 0.45*t:.2f}); color: #0a0;"
    else:
        t = min(1.0, (neutral - val) / (neutral - vmin + 1e-9))
        return f"background-color: rgba(213,86,44,{0.15 + 0.45*t:.2f}); color: #900;"


numeric_cols = ["S_score", "F_score", "mom_12_1_pct", "mansfield_rs", "cmf21"]
styled = display_render.drop(columns=["state"]).style
for c in numeric_cols:
    if c in display_render.columns:
        col_min = float(display[c].min(skipna=True))
        col_max = float(display[c].max(skipna=True))
        styled = styled.map(
            lambda v, lo=col_min, hi=col_max: _color_for_numeric(v, lo, hi),
            subset=[c],
        )

# Show state column as HTML separately
st.markdown("**State (last column shown below as colored pill):**", unsafe_allow_html=True)
st.dataframe(styled, use_container_width=True, height=560)

with st.expander("Show states as colored pills (HTML view)"):
    html_view = display_render.to_html(escape=False, index=True)
    st.markdown(f'<div class="state-table">{html_view}</div>', unsafe_allow_html=True)

# Top picks per class
st.subheader("🎯 Top picks by class")
top_cols = st.columns(len(show_classes) if show_classes else 1)
for col, cls in zip(top_cols, show_classes):
    sub = display[display["class"] == cls]
    picks = sub[sub["selected"]].sort_values("rank_in_class")
    with col:
        st.markdown(f"**{cls}**")
        if picks.empty:
            st.write("_no selections_")
        else:
            for tkr, row in picks.iterrows():
                color = color_for_state(row["state"])
                st.markdown(
                    f"`{tkr}` — S={row['S_score']:+.2f} · "
                    f"<span class='pill' style='background:{color};'>{row['state']}</span>",
                    unsafe_allow_html=True,
                )

st.divider()

# ============================== Drill-down sections ==============================

st.subheader("🔍 Drill-down")

tab_rrg, tab_mom, tab_flow, tab_state, tab_ticker = st.tabs(
    ["RRG quadrants", "Cross-sectional momentum", "Institutional flow", "State machine log", "Per-ticker"]
)

with tab_rrg:
    st.caption("Snapshot of each ticker's RS-Ratio and RS-Momentum vs SPY. Color = current state.")
    for cls in show_classes:
        sub = display[display["class"] == cls]
        if sub.empty:
            continue
        fig = rrg_chart(sub, title=f"RRG — {cls}")
        st.plotly_chart(fig, use_container_width=True)

with tab_mom:
    st.caption("12-1 cross-sectional momentum: 12-month return excluding the most recent month. Higher = recent winner.")
    for cls in show_classes:
        sub = display[display["class"] == cls]
        if sub.empty:
            continue
        fig = momentum_bar(sub, title=f"12-1 momentum — {cls}")
        st.plotly_chart(fig, use_container_width=True)

with tab_flow:
    st.caption(
        "Pillar 7 institutional flow. CMF, OBV, MFI, RVOL are live. Block-trade, dark-pool, ETF SHO, "
        "13F, and short-interest are stubbed in this build — see the README for wiring instructions."
    )
    flow_view = display[[
        "class", "F_score", "cmf21", "obv_slope", "mfi14", "rvol",
        "dist_days_25", "obv_divergence",
        "etf_flow_5d_pct", "block_up_ratio", "dark_pool_pct",
        "si_delta_15d", "thirteen_f_q",
    ]].copy()
    flow_view = flow_view.sort_values("F_score", ascending=False)
    st.dataframe(flow_view, use_container_width=True, height=560)

with tab_state:
    st.caption("Recent state transitions from the persisted state machine (most recent first).")
    trans = recent_transitions(n=50)
    if not trans:
        st.write("_No transitions yet — run the dashboard daily so the state machine can detect changes._")
    else:
        st.dataframe(pd.DataFrame(trans), use_container_width=True)
    st.markdown("**State legend**")
    legend = " ".join(
        f"<span class='pill' style='background:{c};'>{s}</span>"
        for s, c in STATE_COLOR.items()
    )
    st.markdown(legend, unsafe_allow_html=True)

with tab_ticker:
    tkr = st.selectbox("Pick a ticker", options=sorted(display.index.tolist()))
    if tkr and tkr in ohlcv:
        row = display.loc[tkr]
        c1, c2, c3 = st.columns(3)
        c1.metric("Composite score", f"{row['S_score']:+.3f}")
        c2.metric("Flow score (F)", f"{row['F_score']:+.3f}",
                  delta="VETO" if row.get("veto") else None,
                  delta_color="inverse" if row.get("veto") else "normal")
        c3.metric("State", row["state"])

        st.plotly_chart(price_chart_with_30wma(ohlcv[tkr], tkr), use_container_width=True)
        st.plotly_chart(cmf_chart(ohlcv[tkr], tkr), use_container_width=True)
        st.plotly_chart(obv_chart(ohlcv[tkr], tkr), use_container_width=True)

        st.markdown("**Indicator detail**")
        st.dataframe(row.to_frame(name="value"), use_container_width=True)
