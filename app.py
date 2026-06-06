"""Sentiment Board - Streamlit implementation of the Claude Design mockup.

Run with: streamlit run app.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from src.backtest import drawdown_frame, normalized_equity_frame
from src.ad_hoc_analysis import score_ad_hoc_tickers
from src.browser_qa_data import browser_qa_ohlcv_result
from src.calibration_dashboard import (
    calibration_artifact_status_rows,
    expanded_calibration_artifact_status_rows,
    shared_artifact_hash,
)
from src.component_bridge import (
    apply_control_bridge_query_actions,
    drill_bridge_attrs,
    drill_click_bridge_html,
    rrg_plotly_click_bridge_html,
)
from src.component_docs import DASHBOARD_COMPONENT_DOCS, component_docs_html
from src.comparison_view import (
    comparison_card_rows,
    initialize_comparison_tickers,
)
from src.controls import refresh_market_data, toggle_theme
from src.custom_universe import (
    analyze_custom_universe,
    custom_universe_rows_frame,
    parse_custom_universe_file,
    parse_custom_universe_text,
    summary_counts_frame,
)
from src.data_health import dashboard_health_summary, data_health_rows
from src.data import fetch_ohlcv_result, _select_ohlcv_provider
from src.evidence_gates import evaluate_promotion_gate, promotion_gate_decisions_frame
from src.flow import compute_flow_signals, flow_composite_z, provider_flow_feeds_stubbed, provider_flow_health_statuses
from src.fred_data import fred_available
from src.indicators import compute_all_indicators
from src.macro import assess_regime
from src.macro_tiles import MACRO_CONTEXT_SYMBOLS, fred_macro_snapshot, fred_macro_tile_groups, macro_tile_rows, session_range_tile
from src.momentum_v2 import (
    DISPLAY_LABELS as MOMENTUM_V2_DISPLAY_LABELS,
    SCREEN_LABELS as MOMENTUM_V2_SCREEN_LABELS,
    build_view_rows as build_momentum_v2_rows,
    css as momentum_v2_css,
    render_display as render_momentum_v2_display,
)
from src.navigation import initialize_drill_ticker, select_drill_ticker
from src.ohlcv_prefetch import prefetch_status, submit_ohlcv_prefetch
from src.personal_trades import (
    TradeInputResult,
    evaluate_trade_history,
    parse_trade_history_csv,
    parse_trade_history_excel,
    trade_alignment_frame,
    trade_alignment_summary_frame,
)
from src.pl_tracker import (
    analyze_position_pnl,
    latest_prices_from_ohlcv,
    pnl_rows_frame,
    pnl_summary_frame,
)
from src.portfolio import (
    analyze_holdings,
    analysis_rows_frame,
    exposure_frame,
    parse_holdings_csv,
    parse_holdings_excel,
    parse_single_ticker,
    PortfolioInputResult,
)
from src.performance_audit import DashboardPerformanceAudit, classify_rerun, session_snapshot, should_reuse_dashboard_compute
from src.preferences import (
    BLUF_MODES,
    DENSITY_MODES,
    PALETTE_OPTIONS,
    SPARKLINE_STYLES,
    apply_preference_profile,
    delete_preference_profile,
    density_class,
    initialize_preferences,
    is_compact_bluf,
    load_preference_profiles,
    palette_css_variables,
    palette_key,
    save_preference_profile,
    should_render_bluf,
    sparkline_mode,
)
from src.run_debrief import (
    build_debrief_markdown_report,
    debrief_journal,
    debrief_outcome_rows,
    summarize_debriefs,
    summarize_debriefs_by_macro_condition,
    threshold_review_candidates,
)
from src.run_journal import DEFAULT_JOURNAL_PATH, append_dashboard_run, dashboard_run_fingerprint
from src.saved_inputs import (
    delete_saved_input,
    load_saved_inputs,
    save_portfolio,
    save_watchlist,
)
from src.scoring import compute_composite, apply_state_machine, recent_transitions, state_storage_health
from src.structured_logging import configure_structured_logging, log_event
from src.table_sort import (
    FULL_TABLE_SORT_DIRECTIONS,
    FULL_TABLE_SORT_FIELDS,
    normalize_full_table_sort,
    sort_full_table_frame,
)
from src.table_preview import table_row_rrg_preview_html
from src.ticker_identity import TICKER_DISPLAY_NAMES, ticker_display_label, ticker_display_name
from src.transition_pulse import transition_pulse_class, transition_row_pulse_class
from src.ui_states import (
    defensive_basket_rows,
    loading_skeleton_slots,
    provider_status_banner_html as build_provider_status_banner_html,
)
from src.universe import (
    ALL_TICKERS,
    BENCH,
    COUNTRIES,
    CRYPTO,
    FACTORS,
    MEGA_CAP_STOCKS,
    SCORED_TICKERS,
    THEMES,
    UNIVERSE_BY_CLASS,
    US_INDUSTRIES,
    US_SECTORS,
)
from src.visuals import (
    rrg_chart_dark,
    sector_spaghetti_chart,
    filter_ohlcv_lookback,
    price_chart_with_30wma,
    cmf_chart,
    obv_chart,
    svg_sparkline,
    color_for_state,
    STATE_COLOR,
)


APP_VERSION = "v2.4.11"
APP_LOGGER = configure_structured_logging()
DRILL_RANGE_OPTIONS = ("3M", "6M", "1Y", "3Y", "MAX")
DATA_SYMBOLS = list(dict.fromkeys(ALL_TICKERS + list(MACRO_CONTEXT_SYMBOLS) + ["^TNX", "^IRX"]))
def _md(html: str):
    """Streamlit markdown wrapper that strips leading whitespace so HTML isn't
    treated as a code block. Indented HTML inside f-strings (>=4 spaces) gets
    misparsed otherwise."""
    cleaned = "\n".join(line.lstrip() for line in html.split("\n"))
    st.markdown(cleaned, unsafe_allow_html=True)


def _browser_qa_mode_enabled() -> bool:
    return str(os.environ.get("BROWSER_QA_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}


def _operator_mode_enabled() -> bool:
    return str(os.environ.get("DASHBOARD_OPERATOR_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}


def _pytest_mode_enabled() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


def _browser_qa_query_value(name: str) -> str:
    return str(st.query_params.get(name, "")).strip()


def _browser_qa_query_enabled(name: str) -> bool:
    return _browser_qa_query_value(name).lower() in {"1", "true", "yes", "on"}


def render_loading_state(placeholder, label: str, card_count: int = 4) -> None:
    cards = ""
    for slot in loading_skeleton_slots(card_count):
        cards += f"""
        <div class="skeleton-card" style="--skeleton-index:{slot}">
          <div class="skeleton-line short"></div>
          <div class="skeleton-line wide"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line tiny"></div>
        </div>
        """
    html = f"""
    <div class="app loading-app">
      <section class="section loading-state" aria-live="polite" aria-busy="true">
        <div class="section-head">
          <h2>{label}</h2>
          <div class="right">FETCHING</div>
        </div>
        <div class="loading-copy">Preparing dashboard data without blocking the page chrome.</div>
        <div class="picks-grid skeleton-grid">{cards}</div>
      </section>
    </div>
    """
    cleaned = "\n".join(line.lstrip() for line in html.split("\n"))
    placeholder.markdown(cleaned, unsafe_allow_html=True)



# =============================== tooltip text ====================================

INDICATOR_TIPS = {
    # BLUF
    "bluf_exit":     "Tickers with model risk flags this week. Review exposure and risk controls. Triggered by close below 30wMA, Mansfield RS negative, Antonacci absolute failed, RRG entered Lagging, CMF below -0.10, or sustained ETF redemptions.",
    "bluf_warning":  "Tickers showing early bearish evidence. Review stops and avoid adding until evidence improves. Triggered by RRG dropping to Weakening, breadth below 50%, distribution-day cluster, or OBV/price bearish divergence.",
    "bluf_buy":      "Stage 2 candidates passing the strict evidence gates: price above 30-week SMA with positive slope, Mansfield RS positive, RRG in Leading quadrant, sector breadth >= 60%, CMF above +0.05, and non-negative ETF primary flow when available.",
    # Status tiles
    "tip_regime":     "Faber 10-month SMA on SPY. Portfolio-level forward circuit breaker. SPY > SMA historically associated with positive forward equity returns; SPY < SMA precedes the worst drawdowns (2000, 2008, 2020). Flip to RISK-OFF triggers defensive rotation to TLT/GLD/BIL.",
    "tip_phase":     "Business-cycle phase per Stovall/Fidelity. Predicts which sector basket will lead the next 3-6 months. EARLY: cyclicals (XLY, XLF, XLRE, XLI, XLK). MID: tech / industrials. LATE: energy + defensives (XLE, XLB, XLP, XLV). RECESSION: pure defensives (XLP, XLU, XLV).",
    "tip_warnings":  "Tickers currently in EXIT or WARNING state. Watch the week-over-week change to gauge market deterioration. Spikes here often precede broader risk-off.",
    # Pick card metrics
    "tip_S":     "Composite forward-outlook score. Weighted z-score across the 7 pillars; the higher this is for a ticker, the stronger the system's forward call. A hard veto fires if F < -0.5sigma. Forward horizon is roughly the worst-case across pillars (1 week to 6 months).",
    "tip_F":     "Money flow z-score. Combines OHLCV-derived CMF/OBV/MFI/RVOL signals plus provider-backed flow fields when those feeds are live. F < -0.5sigma is treated as a model veto, but check data health because provider feeds can be neutral or unavailable.",
    "tip_MOM":     "12-1 momentum (Jegadeesh-Titman 1993): 12-month return excluding the most recent month. Historically associated with 3-12 month relative strength, but live results vary by regime, costs, and sample.",
    "tip_STAGE":     "Weinstein Stage. Stage 1 = basing, Stage 2 = advance, Stage 3 = topping risk, Stage 4 = decline. The dashboard treats Stage 2/4 as trend evidence, not a certain outcome.",
    "tip_RRG":     "Relative Rotation Graph quadrant. Improving/Leading can indicate strengthening relative rotation; Weakening/Lagging can indicate fading leadership. Use it as one evidence pillar, not a standalone forecast.",
    # Quadrant cards
    "tip_q_leading":   "Outperforming the benchmark with rising relative momentum. Best buy zone.",
    "tip_q_weakening": "Still outperforming but momentum decaying. Tighten stops; rotation candidate.",
    "tip_q_lagging":   "Underperforming with declining momentum. Avoid or short.",
    "tip_q_improving": "Underperforming but momentum turning up. Watch for early entry evidence.",
    # Full table column headers
    "tip_col_FABER":   "Time-series momentum filter. 1 if monthly close > 10-month SMA, else 0. Faber 2007. The binary 'is this asset in its own uptrend' switch.",
    "tip_col_STAGE2":  "1 if Weinstein Stage = 2 (advance), else 0. Requires all three: P > 30wMA, slope > 0, Mansfield RS > 0.",
    "tip_col_ANT":     "Antonacci absolute momentum. 1 if asset's 12mo return > BIL T-bill return. This is the catastrophic-loss circuit breaker that kept the system out of 2008.",
    "tip_col_BREADTH": "Sector breadth proxy. 1 if % of recent 50 sessions above 50dMA >= 50%. A clean way to confirm trend internals.",
    "tip_col_FLOW":    "Pillar-7 flow check. 1 if F > 0 (institutional flow positive). The independent confirmation that price movement is backed by real money.",
    # Drill-down tiles
    "tip_drill_composite": "Master S-score for this ticker (this is the ranking metric).",
    "tip_drill_flow":      "Institutional flow F-score. VETO fires when F < -0.5 sigma regardless of price-based pillars.",
    "tip_drill_state":     "Current state machine output. See state pill tooltips for definition.",
    "tip_drill_momentum":  "12-1 momentum, Mansfield 52-week relative strength shown alongside.",
}

STATE_TIPS = {
    "STAGE_2_BULLISH":  "MODEL SIGNAL: the strongest bullish evidence state. Entry gates pass (price > 30wMA + slope > 0 + Mansfield RS > 0 + RRG Leading + breadth >= 60% + CMF > 0.05 + ETF flow non-negative when available). Treat as decision support, not a guaranteed outcome.",
    "HOLD":             "MODEL SIGNAL: trend evidence is acceptable but one or more strict fresh-buy gates are missing. Review position size and risk controls before adding.",
    "WARNING":          "MODEL SIGNAL: early deterioration evidence is present. Triggered by RRG -> Weakening, breadth < 50%, sustained CMF < 0, OBV/price bearish divergence, or 4+ distribution days.",
    "EXIT":             "MODEL SIGNAL: one or more major risk gates failed. Triggered by close < 30wMA, Mansfield RS < 0, Antonacci failed, RRG -> Lagging, CMF < -0.10, ETF redemptions > 1.5% AUM, or weak block ratio. Review exit/risk plan.",
    "BEARISH_STAGE_4":  "MODEL SIGNAL: bearish trend evidence is confirmed by price below 30wMA, negative MA slope, weak relative strength, and negative flow evidence. Avoid treating it as an automatic short without separate risk review.",
    "STAGE_1_BASING":   "MODEL SIGNAL: possible base-building setup. Price has improved but full Stage 2 confirmation is not present yet. Watchlist evidence, not a buy signal.",
}

STATE_STRENGTH_RANK = {
    "BEARISH_STAGE_4": 0,
    "EXIT": 1,
    "WARNING": 2,
    "STAGE_1_BASING": 3,
    "HOLD": 4,
    "STAGE_2_BULLISH": 5,
}


def _esc(s: str) -> str:
    """HTML-attr-safe escape for tooltip text."""
    return (s.replace('&', '&amp;').replace('"', '&quot;')
             .replace('<', '&lt;').replace('>', '&gt;'))


def _display_value(value, *, signed: bool = False, pct: bool = False, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        number = float(value)
        if pct:
            number *= 100
            return f"{number:+.{decimals}f}%" if signed else f"{number:.{decimals}f}%"
        return f"{number:+.{decimals}f}" if signed else f"{number:.{decimals}f}"
    return str(value)


def _ticker_identity_subtext(ticker: str) -> str:
    name = _ticker_display_name(ticker)
    normalized = str(ticker or "").strip().upper()
    return "" if not name or name == normalized else name


def _metric_tip_for_row(ticker: str, row, metric: str) -> str:
    label = ticker_display_label(ticker)
    state = str(row.get("state") or "UNKNOWN").replace("_", " ")
    if metric == "S":
        score = _display_value(row.get("S_score"), signed=True, decimals=2)
        grade = _grade_letter(row.get("S_score"))
        rank = row.get("rank_in_class")
        rank_text = "n/a" if rank is None or pd.isna(rank) else str(int(rank))
        veto_text = "A flow veto is active, so ranking strength is capped." if bool(row.get("veto")) else "No hard flow veto is active."
        return f"{label}: composite S-score is {score} ({grade}), rank {rank_text}. This is the cross-sectional ranking score, not the state label. {veto_text} Current state is {state}."
    if metric == "F":
        flow = _display_value(row.get("F_score"), signed=True, decimals=2)
        cmf = _display_value(row.get("cmf21"), signed=True, decimals=2)
        etf_flow = _display_value(row.get("etf_flow_5d_pct"), signed=True, pct=True, decimals=2)
        veto_text = "below the veto line" if bool(row.get("veto")) else "above the veto line"
        return f"{label}: flow F-score is {flow}, CMF is {cmf}, ETF 5-day flow is {etf_flow}. Flow is {veto_text}; F < -0.5 sigma blocks strong-looking price setups."
    if metric == "MOM":
        mom = _display_value(row.get("mom_12_1"), signed=True, pct=True, decimals=1)
        mansfield = _display_value(row.get("mansfield_rs"), signed=True, decimals=2)
        return f"{label}: 12-1 momentum is {mom} and Mansfield relative strength is {mansfield}. Positive values mean the instrument has been outperforming on the methodology lookback."
    if metric == "STAGE":
        stage = _display_value(row.get("stage"), decimals=0)
        above = _display_value(row.get("above_30wma"))
        slope = _display_value(row.get("ma_slope_pos"))
        return f"{label}: Weinstein Stage is {stage}; above 30-week average={above}; 30-week average slope up={slope}. Stage 2 is supportive only when price and slope also confirm."
    if metric == "RRG":
        rrg = str(row.get("rrg_quadrant") or "n/a")
        ratio = _display_value(row.get("rs_ratio"), decimals=1)
        momentum = _display_value(row.get("rs_momentum"), decimals=1)
        return f"{label}: RRG quadrant is {rrg}, RS-Ratio {ratio}, RS-Momentum {momentum}. Leading/Improving is constructive; Weakening/Lagging means leadership is fading."
    return f"{label}: value-specific methodology tooltip unavailable."


def _state_tip_for_row(ticker: str, row) -> str:
    state = str(row.get("state") or "UNKNOWN")
    stage = _display_value(row.get("stage"), decimals=0)
    rrg = str(row.get("rrg_quadrant") or "n/a")
    breadth = _display_value(row.get("breadth_50d"), pct=True, decimals=0)
    cmf = _display_value(row.get("cmf21"), signed=True, decimals=2)
    flow = _display_value(row.get("F_score"), signed=True, decimals=2)
    etf_flow = _display_value(row.get("etf_flow_5d_pct"), pct=True, signed=True, decimals=2)
    momentum = _display_value(row.get("mom_12_1"), pct=True, signed=True, decimals=1)
    composite = _display_value(row.get("S_score"), signed=True, decimals=2)
    above_30wma = _display_value(row.get("above_30wma"))
    slope_up = _display_value(row.get("ma_slope_pos"))
    mansfield = _display_value(row.get("mansfield_rs"), signed=True, decimals=2)

    readings = (
        f"Actual readings: Stage={stage}; S={composite}; Flow={flow}; MOM={momentum}; "
        f"RRG={rrg}; Breadth={breadth}; CMF={cmf}; ETF 5d flow={etf_flow}; "
        f"price above 30wMA={above_30wma}; MA slope up={slope_up}; Mansfield RS={mansfield}."
    )

    if state == "STAGE_2_BULLISH":
        return (
            f"Why bullish Stage 2 now: {ticker} is in an advancing trend and the confirmation gates agree. "
            "In simple terms, price trend, relative strength, sector rotation, market breadth, and money flow are all pointing the same way. "
            f"{readings} "
            "What it means: the dashboard expects relative outperformance over roughly 4-26 weeks. "
            "It is a decision-support buy/accumulate signal, not a guarantee and not necessarily an immediate next-day move."
        )

    if state == "HOLD":
        return (
            f"Why hold: {ticker} still has an acceptable trend, but one or more strict buy gates are not strong enough for a fresh buy. "
            f"{readings} "
            "What it means: existing exposure can be monitored, but the dashboard is not calling this a top new entry."
        )

    if state == "WARNING":
        return (
            f"Why warning: {ticker} is showing early deterioration. "
            "Common drivers are weakening rotation, softer breadth, negative CMF, or distribution pressure. "
            f"{readings} "
            "What it means: tighten risk controls and avoid adding until the weak signals improve."
        )

    if state in {"EXIT", "BEARISH_STAGE_4"}:
        return (
            f"Why exit/bearish: {ticker} has broken important trend or flow gates. "
            f"{readings} "
            "What it means: downside or underperformance risk is elevated, so the dashboard prefers reducing or avoiding exposure."
        )

    if state == "STAGE_1_BASING":
        return (
            f"Why Stage 1 basing: {ticker} may be stabilizing, but the full Stage 2 advance is not confirmed yet. "
            f"{readings} "
            "What it means: watchlist candidate; wait for trend slope, relative strength, rotation, and flow to confirm."
        )

    return f"{STATE_TIPS.get(state, 'State explanation unavailable.')} {readings}"

# =============================== system explainer ================================

def _grade_letter(s: float | None) -> str:
    """Translate composite z-score into a letter grade for at-a-glance reading."""
    if s is None or pd.isna(s):
        return "?"
    if s >= 1.0:  return "A"
    if s >= 0.0:  return "B"
    if s >= -1.0: return "C"
    if s >= -1.5: return "D"
    return "F"


SYSTEM_EXPLAINER_HTML = f"""
<div class="explainer">

<p><b>Evidence-based signal system.</b> The Sentiment Board monitors {len(SCORED_TICKERS)} instruments across US sectors, industries, countries, factors, themes, crypto exposures, and mega-cap stocks, then applies a 7-pillar methodology to rank current evidence. Scores and states are decision-support signals, not guaranteed predictions or financial advice. Each pillar has research support and failure modes; always check data health and risk context.</p>

<h3>Data flow</h3>
<pre class="flow">yfinance daily OHLCV (3y, {len(DATA_SYMBOLS)} symbols)
        |
        v
weekly + monthly resamples for stage / Faber
        |
        v
7 forward-looking pillars computed per ticker
        |
        v
Cross-sectional z-scores within each asset class
        |
        v
Composite S-score (weighted) + Flow F-score (z-scored)
        |
        v
State machine (6 forward-outlook states with strict gates)
        |
        v
state.json (persists across restarts)  -->  BLUF + alerts + cards</pre>

<h3>The 7 pillars - weights and forward horizons</h3>
<p>Weights sum to 1.00. "Evidence window" is the historical horizon the dashboard reviews for that pillar; it is not a promise that a move will occur inside that window.</p>
<table>
<thead><tr><th>#</th><th>Pillar</th><th>What it measures</th><th>Evidence window</th><th class="weight">Weight</th></tr></thead>
<tbody>
<tr><td>1</td><td>12-1 Cross-sectional Momentum</td><td>Forward 3-12mo relative performance</td><td>3-12 mo</td><td class="weight">22%</td></tr>
<tr><td>2</td><td>Mansfield 52-week Relative Strength</td><td>Whether the sector keeps leading the index</td><td>2-6 mo</td><td class="weight">12%</td></tr>
<tr><td>3</td><td>RRG RS-Ratio</td><td>Future quadrant position</td><td>4-12 wk</td><td class="weight">15%</td></tr>
<tr><td>4</td><td>RRG RS-Momentum</td><td>Direction of next rotation step</td><td>2-8 wk</td><td class="weight">8%</td></tr>
<tr><td>5</td><td>Binary Trend Filters (Faber + Stage 2 + Antonacci)</td><td>Forward risk-on / risk-off + own-uptrend</td><td>1-6 mo</td><td class="weight">12%</td></tr>
<tr><td>6</td><td>Business-Cycle Tilt</td><td>Sector basket likely to lead the next phase</td><td>3-6 mo</td><td class="weight">8%</td></tr>
<tr><td>7</td><td>Institutional Flow (F-score)</td><td>Smart-money positioning, leads price</td><td>1-8 wk</td><td class="weight">23%</td></tr>
</tbody>
</table>

<h3>Composite formula</h3>
<pre class="flow">S = 0.22 * z(MOM_12_1)
  + 0.12 * z(MANSFIELD_RS)
  + 0.15 * z(RRG_RS_Ratio)
  + 0.08 * z(RRG_RS_Momentum)
  + 0.12 * (FILTERS / 3)
  + 0.08 * CYCLE_TILT
  + 0.23 * z(F_score)</pre>

<h3>Hard flow veto</h3>
<p>A high S-score is overridden if <code>F &lt; -0.5&sigma;</code>. Price moves without real money behind them historically reverse; flow rejection is the system's main protection against pure-momentum traps.</p>

<h3>Letter grade (forward outlook ranking)</h3>
<table>
<thead><tr><th>Grade</th><th>S-score range</th><th>Forward outlook</th></tr></thead>
<tbody>
<tr><td><span class="grade A">A</span></td><td><code>S &ge; +1.0</code></td><td>Strongest evidence bucket; review data health, gates, and risk before acting.</td></tr>
<tr><td><span class="grade B">B</span></td><td><code>0.0 &le; S &lt; +1.0</code></td><td>Modestly bullish forward call</td></tr>
<tr><td><span class="grade C">C</span></td><td><code>-1.0 &lt; S &lt; 0.0</code></td><td>No edge in either direction</td></tr>
<tr><td><span class="grade D">D</span></td><td><code>-1.5 &le; S &le; -1.0</code></td><td>Weak evidence bucket; review risk and wait for improvement.</td></tr>
<tr><td><span class="grade F">F</span></td><td><code>S &lt; -1.5</code></td><td>Weakest evidence bucket; requires caution and separate risk review.</td></tr>
</tbody>
</table>

<h3>State machine - forward calls</h3>
<table>
<thead><tr><th>State</th><th>Forward outlook</th></tr></thead>
<tbody>
<tr><td><span class="pill STAGE_2_BULLISH">STAGE 2 BULLISH</span></td><td>Strongest bullish evidence state. All strict entry gates passed.</td></tr>
<tr><td><span class="pill HOLD">HOLD</span></td><td>Trend evidence is acceptable, but a fresh-buy gate is missing.</td></tr>
<tr><td><span class="pill WARNING">WARNING</span></td><td>Deterioration evidence is present; review risk controls.</td></tr>
<tr><td><span class="pill EXIT">EXIT</span></td><td>Major risk gate failed; review exit/risk plan and data quality.</td></tr>
<tr><td><span class="pill BEARISH_STAGE_4">BEARISH STAGE 4</span></td><td>Bearish trend evidence is confirmed by multiple gates.</td></tr>
<tr><td><span class="pill STAGE_1_BASING">STAGE 1 BASING</span></td><td>Possible <b>Stage-2 setup forming</b> over next 4-13 weeks if remaining gates fill.</td></tr>
</tbody>
</table>

<h3>Empirical evidence per pillar</h3>
<p>Research evidence supporting each pillar. Citations in full bibliography at <code>docs/sector-rotation-methodology.md</code> &sect;11.</p>
<table>
<thead><tr><th>Pillar</th><th>Evidence and caveats</th></tr></thead>
<tbody>
<tr><td>12-1 Momentum</td><td>Jegadeesh-Titman 1993; 30+ years of out-of-sample data (Asness et al. 2013, AQR; alphaarchitect.com 2024). Top-minus-bottom decile spread averages <b>~1% per month over the next year</b>. The most-studied anomaly in finance.</td></tr>
<tr><td>Mansfield RS / Weinstein Stage 2</td><td>Weinstein 1988; 30+ years of practitioner use. Stage-2 breakouts on weekly charts historically continue an average 6-9 months before Stage 3 confirmation.</td></tr>
<tr><td>Faber 10mo SMA</td><td>Faber 2007 (SSRN 962461); updated 2013 & 2020. SMA10 timing on S&P 500 + 4 other asset classes returned <b>~10.5% vs 9.9% buy-and-hold from 1973-2012</b> with HALF the drawdown; drawdown reduction is the documented edge.</td></tr>
<tr><td>Antonacci Dual Momentum</td><td>Antonacci 2014. Absolute-momentum filter kept the model in T-bills through 2008, capping drawdown at <b>~20% vs S&P 500's -55%</b>. Direct demonstration of forward downside protection.</td></tr>
<tr><td>RRG (RS-Ratio + RS-Momentum)</td><td>de Kempenaer 2004-present (relativerotationgraphs.com). Improving -> Leading transitions historically precede outperformance phases by 4-12 weeks; visible on Bloomberg terminals since 2011.</td></tr>
<tr><td>Business-Cycle Tilt</td><td>Stovall 1996; Fidelity Business Cycle Approach (2014, updated annually). Forward sector returns by phase published with cycle-by-cycle data going back to 1962.</td></tr>
<tr><td>Institutional Flow</td><td>Chordia-Swaminathan 2000 (JoF) and Lee-Swaminathan 2000 (JoF): volume-confirmed momentum substantially outperforms pure-price momentum. CMF/OBV divergences historically lead price by <b>1-3 weeks</b> on breakdowns.</td></tr>
</tbody>
</table>

<p style="margin-top: 18px;"><b>Critical caveat:</b> Past predictive power does not guarantee future predictive power. Each pillar has documented failure modes (momentum crashes per Daniel-Moskowitz 2016, "myth of sector rotation" per Molchanov-Stangl 2018). The system layers seven different pillars precisely because no single signal is reliable on its own. The hard flow-veto and the multi-pillar consensus requirement are designed to reduce the false-positive rate.</p>

<h3>References</h3>
<p>Full methodology with formulas and academic citations: <code>docs/sector-rotation-methodology.md</code> &middot; PDF version in <code>docs/sector-rotation-methodology.pdf</code>.</p>

</div>
"""


# =============================== page config =====================================

st.set_page_config(
    page_title="Sentiment Board",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================== load css ========================================

APP_ROOT = Path(__file__).resolve().parent
_STATIC = APP_ROOT / "static"
_CSS = (_STATIC / "style.css").read_text(encoding="utf-8") + momentum_v2_css()
BACKTEST_REPORT_PATH = APP_ROOT / "docs" / "backtest_report.md"
BACKTEST_EQUITY_PATH = APP_ROOT / "docs" / "backtest_equity.csv"
BACKTEST_STATES_PATH = APP_ROOT / "docs" / "backtest_states.csv"
BACKTEST_METADATA_PATH = APP_ROOT / "docs" / "backtest_metadata.json"
CALIBRATION_BASELINE_CONFIG_PATH = APP_ROOT / "docs" / "calibration_10y_baseline_config.json"
CALIBRATION_REPORT_PATH = APP_ROOT / "docs" / "calibration_10y_report.md"
CALIBRATION_SUMMARY_PATH = APP_ROOT / "docs" / "calibration_10y_summary.csv"
CALIBRATION_CANDIDATES_PATH = APP_ROOT / "docs" / "calibration_10y_candidates.csv"
CALIBRATION_CANDIDATE_CONFIG_PATH = APP_ROOT / "docs" / "calibration_10y_candidate_config.json"
CALIBRATION_METADATA_PATH = APP_ROOT / "docs" / "calibration_10y_metadata.json"
CALIBRATION_EXPANDED_REPORT_PATH = APP_ROOT / "docs" / "calibration_expanded_report.md"
CALIBRATION_EXPANDED_CANDIDATES_PATH = APP_ROOT / "docs" / "calibration_expanded_candidates.csv"
CALIBRATION_SECTOR_OVERRIDES_PATH = APP_ROOT / "docs" / "calibration_sector_overrides.csv"
CALIBRATION_EXPANDED_METADATA_PATH = APP_ROOT / "docs" / "calibration_expanded_metadata.json"
FRED_VALIDATION_SUMMARY_PATH = APP_ROOT / "docs" / "fred_macro_validation_summary.csv"
MASSIVE_VALIDATION_SUMMARY_PATH = APP_ROOT / "docs" / "massive_provider_validation_summary.csv"
FRED_VALIDATION_REPORT_PATH = APP_ROOT / "docs" / "fred_macro_validation_report.md"
MASSIVE_VALIDATION_REPORT_PATH = APP_ROOT / "docs" / "massive_provider_validation_report.md"
EVIDENCE_GATE_REPORT_PATH = APP_ROOT / "docs" / "evidence_gate_report.md"
SAVED_INPUTS_PATH = APP_ROOT / "data" / "saved_inputs.json"
PREFERENCE_PROFILES_PATH = APP_ROOT / "data" / "preference_profiles.json"
LOAD_WATCHLIST_LABEL = "LOAD WATCHLIST"
DELETE_WATCHLIST_LABEL = "DELETE WATCHLIST"
SAVE_WATCHLIST_LABEL = "SAVE WATCHLIST"
LOAD_PORTFOLIO_LABEL = "LOAD PORTFOLIO"
DELETE_PORTFOLIO_LABEL = "DELETE PORTFOLIO"
SAVE_PORTFOLIO_LABEL = "SAVE PORTFOLIO"

# Streamlit-specific overrides on top of the design CSS
_EXTRA = """
/* hide streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.stApp { background: var(--bg) !important; }
section.main > div.block-container { padding-top: 0; padding-bottom: 0; max-width: 1480px; }
[data-testid="stSidebar"] { display: none !important; }
.element-container, .stMarkdown { font-family: var(--font-prose); }
/* keep plotly chart wrappers transparent */
.element-container .stPlotlyChart { background: transparent !important; }
"""


# =============================== data load (cached) ==============================

@st.cache_data(ttl=3600, show_spinner=False)
def _load_data(period: str = "3y", refresh_token: str | None = None):
    tickers = DATA_SYMBOLS
    if _browser_qa_mode_enabled():
        return browser_qa_ohlcv_result(tickers, period=period)
    return fetch_ohlcv_result(tickers, period=period, force_refresh=bool(refresh_token))


@st.cache_data(ttl=3600, show_spinner=False)
def _load_ad_hoc_data(tickers: tuple[str, ...], period: str = "3y", refresh_token: str | None = None):
    symbols = tuple(dict.fromkeys([*tickers, BENCH["US"], BENCH["TBILL"]]))
    if _browser_qa_mode_enabled():
        return browser_qa_ohlcv_result(symbols, period=period)
    return fetch_ohlcv_result(symbols, period=period, force_refresh=bool(refresh_token))


@st.cache_data(ttl=21600, show_spinner=False)  # FRED updates monthly/weekly, cache 6h
def _load_fred(refresh_token: str | None = None) -> dict:
    """Fetch FRED macro series. Empty dict if no API key configured."""
    if _browser_qa_mode_enabled():
        return {}
    try:
        from src.fred_data import fetch_fred, fred_available
        if not fred_available():
            return {}
        return fetch_fred()
    except Exception:
        return {}


def _refresh_data_lane(lane_id: str) -> None:
    lane_id = lane_id if lane_id in {
        "all",
        "market_ohlcv",
        "fred_macro",
        "dashboard_compute",
        "provider_flow",
        "state_persistence",
    } else "all"
    requested_at = datetime.now(timezone.utc).isoformat()
    cleared_caches: list[str] = []

    if lane_id in {"all", "market_ohlcv"}:
        refresh_market_data(_load_data)
        refresh_market_data(_load_ad_hoc_data)
        st.session_state.data_refresh_token = f"{lane_id}:{requested_at}"
        cleared_caches.extend(["market_ohlcv", "ad_hoc_ohlcv"])
    if lane_id in {"all", "fred_macro"}:
        refresh_market_data(_load_fred)
        st.session_state.fred_refresh_token = f"{lane_id}:{requested_at}"
        cleared_caches.append("fred_macro")
    if lane_id in {"all", "provider_flow"}:
        st.session_state.flow_refresh_token = f"{lane_id}:{requested_at}"
    if lane_id in {"all", "dashboard_compute"}:
        st.session_state.compute_refresh_token = f"{lane_id}:{requested_at}"

    st.session_state.pop("dashboard_compute_snapshot", None)
    st.session_state.data_refresh_requested_at = requested_at
    st.session_state.data_refresh_lane = lane_id
    log_event(APP_LOGGER, "data_lane_refresh_requested",
        lane_id=lane_id,
        requested_at=requested_at,
        caches_cleared=cleared_caches,
    )


def _refresh_loaded_data() -> None:
    _refresh_data_lane("all")


def _mark_data_refresh_completed(ohlcv_result_obj) -> None:
    requested_at = st.session_state.get("data_refresh_requested_at")
    if not requested_at or st.session_state.get("data_refresh_completed_request_at") == requested_at:
        return
    completed_at = datetime.now(timezone.utc).isoformat()
    lane_id = str(st.session_state.get("data_refresh_lane") or "all")
    st.session_state.data_refresh_completed_request_at = requested_at
    st.session_state.data_refresh_completed_at = completed_at
    completed_by_lane = dict(st.session_state.get("data_refresh_completed_by_lane", {}) or {})
    lane_ids = (
        "market_ohlcv",
        "fred_macro",
        "dashboard_compute",
        "provider_flow",
        "state_persistence",
    ) if lane_id == "all" else (lane_id,)
    for completed_lane in lane_ids:
        completed_by_lane[str(completed_lane)] = completed_at
    st.session_state.data_refresh_completed_by_lane = completed_by_lane
    log_event(APP_LOGGER, "data_lane_refresh_completed",
        lane_id=lane_id,
        requested_at=requested_at,
        completed_at=completed_at,
        provider=getattr(ohlcv_result_obj, "provider", "unknown"),
        fetched_count=len(getattr(ohlcv_result_obj, "data", {}) or {}),
        fresh_cache_hit_count=len(getattr(ohlcv_result_obj, "fresh_cache_hits", ()) or ()),
        stale_cache_hit_count=len(getattr(ohlcv_result_obj, "stale_cache_hits", ()) or ()),
        missing_ohlcv_count=len(getattr(ohlcv_result_obj, "missing", ()) or ()),
        provider_warning_count=len(getattr(ohlcv_result_obj, "warnings", ()) or ()),
        cache_refresh_forced=bool(getattr(ohlcv_result_obj, "cache_refresh_forced", False)),
    )


def _lane_completed_text(lane_id: str) -> str:
    completed_by_lane = st.session_state.get("data_refresh_completed_by_lane", {}) or {}
    completed_at = completed_by_lane.get(lane_id)
    if not completed_at:
        return "not refreshed yet"
    try:
        parsed = pd.Timestamp(completed_at)
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize("UTC")
        parsed = parsed.tz_convert("UTC")
        return f"rendered after request {parsed.strftime('%Y-%m-%d %H:%M UTC')}"
    except Exception:
        return f"rendered after request {completed_at}"


def _apply_control_bridge_actions() -> None:
    result = apply_control_bridge_query_actions(
        st.session_state,
        st.query_params,
        refresh_callback=_refresh_loaded_data,
    )
    if result.should_rerun:
        st.rerun()


def _start_ohlcv_cache_prefetch() -> None:
    if _browser_qa_mode_enabled() or _pytest_mode_enabled():
        return
    future = submit_ohlcv_prefetch(DATA_SYMBOLS, period="3y")
    st.session_state["ohlcv_prefetch_future"] = future
    st.session_state["ohlcv_prefetch_status"] = prefetch_status(future)


if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "klass" not in st.session_state:
    st.session_state.klass = "US Sectors"
if "drill_ticker" not in st.session_state:
    st.session_state.drill_ticker = "XLK"
if "methodology_ticker_input" not in st.session_state:
    st.session_state.methodology_ticker_input = st.session_state.drill_ticker
if "methodology_ticker_submitted_text" not in st.session_state:
    st.session_state.methodology_ticker_submitted_text = st.session_state.methodology_ticker_input
if "drill_range" not in st.session_state:
    st.session_state.drill_range = "1Y"
elif st.session_state.drill_range not in DRILL_RANGE_OPTIONS:
    st.session_state.drill_range = "1Y"
if "portfolio_single_ticker" not in st.session_state:
    st.session_state.portfolio_single_ticker = st.session_state.drill_ticker
if "portfolio_single_submitted_ticker" not in st.session_state:
    st.session_state.portfolio_single_submitted_ticker = st.session_state.portfolio_single_ticker
if "portfolio_single_source" not in st.session_state:
    st.session_state.portfolio_single_source = st.session_state.drill_ticker
if "custom_universe_text" not in st.session_state:
    st.session_state.custom_universe_text = ""
if "custom_universe_submitted_text" not in st.session_state:
    st.session_state.custom_universe_submitted_text = ""
if "transition_history_limit" not in st.session_state:
    st.session_state.transition_history_limit = 25
if "table_open" not in st.session_state:
    st.session_state.table_open = True
if "momentum_v2_display" not in st.session_state:
    st.session_state.momentum_v2_display = "C"
elif st.session_state.momentum_v2_display not in MOMENTUM_V2_DISPLAY_LABELS:
    st.session_state.momentum_v2_display = "C"
if "momentum_v2_screen" not in st.session_state:
    st.session_state.momentum_v2_screen = "overview"
elif st.session_state.momentum_v2_screen not in MOMENTUM_V2_SCREEN_LABELS:
    st.session_state.momentum_v2_screen = "overview"
if "table_sort" not in st.session_state:
    st.session_state.table_sort = "S_score:desc"
_legacy_table_sort = str(st.session_state.table_sort or "S_score:desc").split(":", 1)
_table_sort_field, _table_sort_direction = normalize_full_table_sort(
    _legacy_table_sort[0],
    _legacy_table_sort[1] if len(_legacy_table_sort) > 1 else "desc",
)
if "table_sort_field" not in st.session_state:
    st.session_state.table_sort_field = _table_sort_field
if "table_sort_direction" not in st.session_state:
    st.session_state.table_sort_direction = _table_sort_direction
st.session_state.table_sort_field, st.session_state.table_sort_direction = normalize_full_table_sort(
    st.session_state.table_sort_field,
    st.session_state.table_sort_direction,
)
if "table_sort_field_choice" not in st.session_state:
    st.session_state.table_sort_field_choice = st.session_state.table_sort_field
if "table_sort_direction_choice" not in st.session_state:
    st.session_state.table_sort_direction_choice = st.session_state.table_sort_direction
st.session_state.table_sort_field_choice, st.session_state.table_sort_direction_choice = normalize_full_table_sort(
    st.session_state.table_sort_field_choice,
    st.session_state.table_sort_direction_choice,
)
st.session_state.table_sort_field = st.session_state.table_sort_field_choice
st.session_state.table_sort_direction = st.session_state.table_sort_direction_choice
st.session_state.table_sort = f"{st.session_state.table_sort_field}:{st.session_state.table_sort_direction}"
initialize_preferences(st.session_state)
_apply_control_bridge_actions()
if _browser_qa_mode_enabled():
    qa_palette = _browser_qa_query_value("browser_qa_palette")
    if qa_palette in PALETTE_OPTIONS:
        st.session_state.color_palette = qa_palette
_density_class = density_class(st.session_state.view_density)
_palette_key = palette_key(st.session_state.color_palette)
_palette_css = palette_css_variables(st.session_state.color_palette, st.session_state.theme)
PERF_AUDIT = DashboardPerformanceAudit()
_PERF_START_SNAPSHOT = session_snapshot(st.session_state)
_PERF_RERUN = classify_rerun(st.session_state.get("performance_last_snapshot"), _PERF_START_SNAPSHOT)
_REUSED_COMPUTE_SNAPSHOT = should_reuse_dashboard_compute(_PERF_RERUN, st.session_state.get("dashboard_compute_snapshot"))

_md(
    f"<style>{_CSS}{_EXTRA}{_palette_css}</style>"
    f'<script>'
    f'document.documentElement.setAttribute("data-theme","{st.session_state.theme}");'
    f'document.documentElement.setAttribute("data-palette","{_palette_key}");'
    f'document.documentElement.classList.remove("density-comfortable","density-compact");'
    f'document.documentElement.classList.add("{_density_class}");'
    f'</script>',
)


def provider_status_banner_html(ohlcv_result):
    return build_provider_status_banner_html(ohlcv_result)


def render_provider_status_banner(ohlcv_result) -> None:
    html = provider_status_banner_html(ohlcv_result)
    if html:
        _md(html)


def _render_browser_qa_provider_banner() -> None:
    if not (_browser_qa_mode_enabled() and _browser_qa_query_enabled("browser_qa_provider_banner")):
        return
    render_provider_status_banner(
        SimpleNamespace(
            used_stale_cache=False,
            missing=("BROWSER_QA",),
            warnings=("Browser QA provider fallback fixture - no API keys required.",),
        )
    )


def _current_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _record_dashboard_run(scored_df, bluf_payload, regime_obj, transitions_rows, ohlcv_payload, ohlcv_result_obj, fred_snapshot) -> None:
    provider = str(getattr(ohlcv_result_obj, "provider", "") or _select_ohlcv_provider(None))
    metadata = {
        "phase": regime_obj.phase_hint,
        "risk_on": regime_obj.risk_on,
        "fred_used": regime_obj.fred_used,
        "regime_note": regime_obj.note,
        "fred_macro_snapshot": fred_snapshot,
        "transition_count_14d": len(transitions_rows),
        "benchmarks": {"us": BENCH["US"], "tbill": BENCH["TBILL"]},
        "missing_ohlcv": sorted(set(DATA_SYMBOLS) - set(ohlcv_payload)),
        "ohlcv_provider": provider,
        "fresh_cache_hit_count": len(getattr(ohlcv_result_obj, "fresh_cache_hits", ()) or ()),
        "stale_cache_hit_count": len(getattr(ohlcv_result_obj, "stale_cache_hits", ()) or ()),
        "missing_ohlcv_provider": sorted(getattr(ohlcv_result_obj, "missing", ()) or ()),
        "provider_warning_count": len(getattr(ohlcv_result_obj, "warnings", ()) or ()),
        "cache_refresh_forced": bool(getattr(ohlcv_result_obj, "cache_refresh_forced", False)),
        "data_refresh_lane": st.session_state.get("data_refresh_lane"),
        "data_refresh_requested_at": st.session_state.get("data_refresh_requested_at"),
        "bluf_counts": {
            "exits": bluf_payload.get("exits_count", 0),
            "warnings": bluf_payload.get("warns_count", 0),
            "buys": bluf_payload.get("buys_count", 0),
        },
    }
    git_sha = _current_git_sha()
    fingerprint = dashboard_run_fingerprint(
        scored_df,
        bluf_payload,
        git_sha=git_sha,
        app_version=APP_VERSION,
        provider=provider,
        metadata=metadata,
    )
    if st.session_state.get("run_journal_last_fingerprint") == fingerprint:
        return

    result = append_dashboard_run(
        DEFAULT_JOURNAL_PATH,
        scored_df,
        bluf_payload,
        git_sha=git_sha,
        app_version=APP_VERSION,
        provider=provider,
        metadata=metadata,
        dedupe_content=True,
    )
    if result.ok:
        st.session_state.run_journal_last_run_id = result.run_id
        st.session_state.run_journal_last_fingerprint = fingerprint
        if result.skipped_duplicate:
            log_event(APP_LOGGER, "dashboard_run_duplicate_skipped",
                run_id=result.run_id,
                provider=provider,
                ticker_count=len(scored_df),
                git_sha=git_sha,
            )
            return
        log_event(APP_LOGGER, "dashboard_run_recorded",
            run_id=result.run_id,
            provider=provider,
            ticker_count=len(scored_df),
            transition_count_14d=metadata["transition_count_14d"],
            git_sha=git_sha,
        )
    else:
        st.session_state.run_journal_last_error = result.error
        log_event(APP_LOGGER, "dashboard_run_journal_error",
            level="WARNING",
            error=result.error,
            provider=provider,
            git_sha=git_sha,
        )


if _REUSED_COMPUTE_SNAPSHOT:
    with PERF_AUDIT.section("reuse_compute_snapshot"):
        compute_snapshot = st.session_state["dashboard_compute_snapshot"]
        ohlcv_result = compute_snapshot["ohlcv_result"]
        ohlcv = compute_snapshot["ohlcv"]
        _fred_data = compute_snapshot["fred_data"]
        regime = compute_snapshot["regime"]
        scored = compute_snapshot["scored"]
        dashboard_compute_created_at = compute_snapshot.get("created_at")
    render_provider_status_banner(ohlcv_result)
    _render_browser_qa_provider_banner()
else:
    loading_placeholder = st.empty()
    render_loading_state(loading_placeholder, "Loading market data", card_count=4)
    try:
        with PERF_AUDIT.section("load_data"):
            refresh_token = st.session_state.get("data_refresh_token")
            fred_refresh_token = st.session_state.get("fred_refresh_token")
            ohlcv_result = _load_data("3y", refresh_token=refresh_token)
            render_provider_status_banner(ohlcv_result)
            _render_browser_qa_provider_banner()
            ohlcv = ohlcv_result.data

        bench_ticker = BENCH["US"]
        bil_ticker = BENCH["TBILL"]
        if bench_ticker not in ohlcv or bil_ticker not in ohlcv:
            st.error("Missing benchmark/T-bill data. Try the refresh button.")
            st.stop()
        with PERF_AUDIT.section("compute_signals"):
            scoring_ohlcv = {t: ohlcv[t] for t in ALL_TICKERS if t in ohlcv}

            render_loading_state(loading_placeholder, "Computing indicators", card_count=4)
            indicators_df = compute_all_indicators(scoring_ohlcv, bench_ticker, bil_ticker)
            flow_df = compute_flow_signals(scoring_ohlcv)
            flow_z = flow_composite_z(flow_df)
            _fred_data = _load_fred(refresh_token=fred_refresh_token)
            regime = assess_regime(ohlcv[bench_ticker], ohlcv.get("^TNX"), ohlcv.get("^IRX"), fred_cache=_fred_data)
            scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
            scored = apply_state_machine(scored)
            _COMPUTE_SNAPSHOT_CREATED_AT = datetime.now().timestamp()
            dashboard_compute_created_at = _COMPUTE_SNAPSHOT_CREATED_AT
            st.session_state.dashboard_compute_snapshot = {
                "ohlcv_result": ohlcv_result,
                "ohlcv": ohlcv,
                "fred_data": _fred_data,
                "regime": regime,
                "scored": scored,
                "created_at": _COMPUTE_SNAPSHOT_CREATED_AT,
            }
    finally:
        loading_placeholder.empty()

AVAILABLE_TICKERS = sorted(scored.index.tolist())
initialize_drill_ticker(st.session_state, st.query_params, AVAILABLE_TICKERS)
if _REUSED_COMPUTE_SNAPSHOT is False:
    with PERF_AUDIT.section("ohlcv_prefetch"):
        _start_ohlcv_cache_prefetch()


# =============================== derive view-model ===============================

def _state_color_var(state: str) -> str:
    return {
        "STAGE_2_BULLISH": "var(--st-stage2)",
        "HOLD": "var(--st-hold)",
        "WARNING": "var(--st-warn)",
        "EXIT": "var(--st-exit)",
        "BEARISH_STAGE_4": "var(--st-bear)",
        "STAGE_1_BASING": "var(--st-basing)",
    }.get(state, "var(--muted)")


def _build_bluf(scored_df: pd.DataFrame):
    """Compute the BLUF action lists from current state."""
    exits = scored_df[scored_df["state"].isin(["EXIT", "BEARISH_STAGE_4"])]
    warns = scored_df[scored_df["state"] == "WARNING"]
    buys = scored_df[scored_df["state"] == "STAGE_2_BULLISH"]

    def _note_exit(row):
        bits = []
        if row.get("above_30wma") is False:
            bits.append("below 30wMA")
        if (row.get("cmf21") or 0) < -0.05:
            bits.append(f"CMF {row['cmf21']:+.2f}")
        if row.get("rrg_quadrant") == "Lagging":
            bits.append("RRG Lagging")
        if row.get("veto"):
            bits.append("flow veto")
        if not bits:
            bits = [f"S {row['S_score']:+.2f}"]
        return " | ".join(bits[:3])

    def _note_warn(row):
        bits = []
        if row.get("rrg_quadrant") == "Weakening":
            bits.append("RRG Weakening")
        if (row.get("breadth_50d") or 0) < 0.50:
            bits.append(f"breadth {row['breadth_50d']*100:.0f}%")
        if (row.get("cmf21") or 0) < 0:
            bits.append(f"CMF {row['cmf21']:+.2f}")
        if not bits:
            bits = [f"S {row['S_score']:+.2f}"]
        return " | ".join(bits[:3])

    def _note_buy(row):
        bits = [f"S {row['S_score']:+.2f}"]
        if (row.get("F_score") or 0) > 0:
            bits.append(f"F {row['F_score']:+.2f}")
        if (row.get("mom_12_1") or 0) > 0:
            bits.append(f"mom +{row['mom_12_1']*100:.0f}%")
        return " | ".join(bits[:3])

    def _pack(sub_df, note_fn, kind, label, eta, state):
        items = []
        sub_sorted = sub_df.sort_values("S_score", ascending=(kind == "exit"))
        for tkr, r in sub_sorted.iterrows():
            items.append({"t": tkr, "note": note_fn(r)})
        return {
            "kind": kind, "label": label, "eta": eta, "state": state, "tickers": items
        }

    return {
        "exits_count": len(exits),
        "warns_count": len(warns),
        "buys_count":  len(buys),
        "actions": [
            _pack(exits, _note_exit, "exit", "EXIT NOW",        "ON MONDAY OPEN", "EXIT"),
            _pack(warns, _note_warn, "warn", "WATCH CLOSELY",   "TIGHTEN STOPS",  "WARNING"),
            _pack(buys,  _note_buy,  "buy",  "BUY CANDIDATES",  "ENTER ON DIP",   "STAGE_2_BULLISH"),
        ],
    }


def _browser_qa_transitions(scored_df: pd.DataFrame) -> list[dict]:
    if not (_browser_qa_mode_enabled() and _browser_qa_query_enabled("browser_qa_transition")):
        return []
    ticker = "XLK" if "XLK" in scored_df.index else str(scored_df.index[0])
    return [
        {
            "ticker": ticker,
            "from": "BROWSER_QA",
            "to": "STAGE_2_BULLISH",
            "date": datetime.now(timezone.utc).date().isoformat(),
        }
    ]


bluf = _build_bluf(scored)
transition_history_limit = int(st.session_state.get("transition_history_limit", 25) or 25)
transitions = recent_transitions(n=transition_history_limit)
transitions = _browser_qa_transitions(scored) + transitions
if not _REUSED_COMPUTE_SNAPSHOT:
    _record_dashboard_run(scored, bluf, regime, transitions, ohlcv, ohlcv_result, fred_macro_snapshot(_fred_data))

# Phase index for the phase bar
PHASE_IDX = {"EARLY": 0, "MID": 1, "LATE": 2, "RECESSION": 3, "UNKNOWN": -1}
phase_idx = PHASE_IDX.get(regime.phase_hint, -1)


# =============================== render helpers ==================================


DRILL_SELECTOR_PLACEHOLDER = "__choose_drill_ticker__"


def _go_to_drill(ticker: str) -> None:
    changed = select_drill_ticker(st.session_state, st.query_params, ticker, AVAILABLE_TICKERS)
    selected_ticker = str(st.session_state.get("drill_ticker", "")).upper()
    if selected_ticker:
        st.session_state["drill_focus_ticker"] = selected_ticker
        st.query_params["focus"] = "drill"
    if changed:
        st.rerun()


def _go_to_selected_drill(widget_key: str) -> None:
    selected = st.session_state.get(widget_key)
    if selected == DRILL_SELECTOR_PLACEHOLDER:
        return
    if isinstance(selected, str) and selected:
        _go_to_drill(selected)


def _ticker_display_name(ticker: str) -> str:
    return ticker_display_name(ticker)


def _drill_option_label(ticker: str) -> str:
    if ticker == DRILL_SELECTOR_PLACEHOLDER:
        return "Choose ticker..."
    label = ticker_display_label(ticker)
    if ticker not in scored.index:
        return label
    row = scored.loc[ticker]
    state = str(row.get("state") or "UNKNOWN").replace("_", " ")
    score = row.get("S_score")
    score_text = "n/a" if score is None or pd.isna(score) else f"{float(score):+.2f}"
    return f"{label} | {state} | S {score_text}"


def _render_drill_selector(prefix: str, tickers: list[str], label: str) -> None:
    drill_tickers = [ticker for ticker in dict.fromkeys(tickers) if ticker in scored.index]
    if not drill_tickers:
        return
    key = f"{prefix}_select"
    current_ticker = str(st.session_state.get("drill_ticker", ""))
    select_options = drill_tickers
    default_ticker = current_ticker
    if current_ticker not in drill_tickers:
        select_options = [DRILL_SELECTOR_PLACEHOLDER, *drill_tickers]
        default_ticker = DRILL_SELECTOR_PLACEHOLDER
    if st.session_state.get(key) != default_ticker:
        st.session_state[key] = default_ticker
    _md('<div class="drill-selector-slot"></div>')
    st.selectbox(
        label,
        select_options,
        key=key,
        format_func=_drill_option_label,
        help="Choose a ticker from this section and the dashboard will open its detailed methodology drill-down.",
        on_change=_go_to_selected_drill,
        args=(key,),
    )
    focus_ticker = str(st.session_state.get("drill_focus_ticker", "")).upper()
    if focus_ticker in drill_tickers:
        _md(
            f"""
            <div class="drill-selection-confirm">
              Selected <b>{_esc(focus_ticker)}</b>.
              <a href="#drill">Open complete report</a>
            </div>
            """
        )


def _macro_tile_html(row: dict[str, object], extra_class: str = "") -> str:
    tone = str(row.get("tone", "warn"))
    sentiment_class = str(row.get("sentiment_label", "unavailable")).replace(" ", "-")
    sentiment_label = str(row.get("sentiment_label", "unavailable")).upper()
    trend_label = str(row.get("trend_label", "data pending"))
    trend_symbol = str(row.get("trend_symbol", "?"))
    gauge_pct = max(0, min(100, int(row.get("gauge_pct") or 50)))
    trend_tip = (
        f"Trend marker: {trend_label}. Left side means negative/worsening pressure; "
        "center means neutral; right side means positive/improving pressure for this dashboard's momentum model."
    )
    return f"""
    <div class="tile macro-tile {extra_class} {tone}" data-tip="{_esc(str(row.get('tooltip', '')))}" data-tip-pos="below">
      <div class="tile-label">{_esc(str(row.get('label', '')))}<span class="tile-delta">{_esc(str(row.get('symbol', row.get('series_id', ''))))}</span></div>
      <div class="tile-value {tone}">{_esc(str(row.get('value', 'DATA PENDING')))}</div>
      <div class="macro-signal {sentiment_class}">
        <span class="signal-symbol">{_esc(trend_symbol)}</span>
        <span>{_esc(sentiment_label)}</span>
        <span class="trend">{_esc(trend_label)}</span>
      </div>
      <div class="macro-gauge-label">trend pressure</div>
      <div class="macro-gauge {sentiment_class}" style="--gauge:{gauge_pct}%" data-tip="{_esc(trend_tip)}">
        <span class="macro-gauge-fill"></span>
        <span class="macro-gauge-mid"></span>
        <span class="macro-gauge-marker"></span>
      </div>
      <div class="tile-sub">{_esc(str(row.get('change', '-')))} / {_esc(str(row.get('subtitle', '')))}</div>
    </div>
    """


def _transition_sentiment(row: dict) -> tuple[str, str, str]:
    from_state = str(row.get("from") or "")
    to_state = str(row.get("to") or "")
    from_rank = STATE_STRENGTH_RANK.get(from_state)
    to_rank = STATE_STRENGTH_RANK.get(to_state)
    if from_rank is None or to_rank is None or from_rank == to_rank:
        return "transition-neutral", "neutral", "="
    if to_rank > from_rank:
        return "transition-positive", "positive", "+"
    return "transition-negative", "negative", "!"


def _score_text(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):+.3f}"


def _analysis_scored_frame_for_result(result):
    analysis = analyze_holdings(result.holdings, scored)
    ad_hoc_result = None
    if not analysis.missing_tickers:
        return scored, analysis, ad_hoc_result

    missing = tuple(sorted(set(analysis.missing_tickers)))
    refresh_token = st.session_state.get("data_refresh_token")
    ohlcv_result = _load_ad_hoc_data(missing, period="3y", refresh_token=refresh_token)
    ad_hoc_ohlcv = {**ohlcv, **ohlcv_result.data}
    ad_hoc_result = score_ad_hoc_tickers(
        missing,
        ad_hoc_ohlcv,
        phase=regime.phase_hint,
        bench_ticker=BENCH["US"],
        bil_ticker=BENCH["TBILL"],
    )
    if ad_hoc_result.scored.empty:
        return scored, analysis, ad_hoc_result

    analysis_scored = pd.concat([scored, ad_hoc_result.scored], axis=0)
    return analysis_scored, analyze_holdings(result.holdings, analysis_scored), ad_hoc_result


def _render_ad_hoc_status(ad_hoc_result, *, compact: bool = False) -> None:
    if ad_hoc_result is None:
        return
    if not ad_hoc_result.scored.empty:
        tickers = ", ".join(ad_hoc_result.scored.index.tolist())
        message = (
            f"Ad hoc methodology snapshot: {tickers} was scored from fetched OHLCV. "
            "It is read-only and not saved into the dashboard universe."
        )
        if compact:
            st.caption(message)
        else:
            st.info(message)
    for warning in ad_hoc_result.warnings:
        st.warning(warning)


def render_ticker_analyzer():
    _md(
        f"""
        <section class="section" id="ticker-analyzer">
          <div class="section-head">
            <h2>Analyze ticker <span class="count">methodology snapshot</span></h2>
            <div class="right">{len(scored)} scored tickers</div>
          </div>
        </section>
        """
    )

    with st.form("ticker_analyzer_form", clear_on_submit=False):
        input_col, action_col = st.columns([3, 1])
        with input_col:
            ticker_text = st.text_input("Ticker to analyze", key="methodology_ticker_input", placeholder="XLK")
        with action_col:
            _md('<div class="form-action-spacer"></div>')
            submitted = st.form_submit_button("ANALYZE TICKER", type="primary", width="stretch")
    if submitted:
        st.session_state.methodology_ticker_submitted_text = ticker_text

    submitted_text = st.session_state.get("methodology_ticker_submitted_text", ticker_text)
    result = parse_single_ticker(submitted_text)
    for error in result.errors:
        st.warning(error.message)

    if not result.holdings:
        return

    ticker = result.holdings[0].ticker
    ticker_label = ticker_display_label(ticker)
    try:
        analysis_scored, analysis, ad_hoc_result = _analysis_scored_frame_for_result(result)
    except ValueError as exc:
        st.error(str(exc))
        return

    if analysis.missing_tickers:
        _render_ad_hoc_status(ad_hoc_result, compact=True)
        st.warning(f"{ticker} could not be analyzed because market data was unavailable.")
        return

    _render_ad_hoc_status(ad_hoc_result, compact=True)
    row = analysis_scored.loc[ticker]
    is_ad_hoc = bool(row.get("ad_hoc", False))
    state = str(row.get("state") or "UNKNOWN")
    asset_class = str(row.get("class") or "UNKNOWN")
    s_score = row.get("S_score")
    f_score = row.get("F_score")
    rank = row.get("rank_in_class")
    rank_text = "n/a" if rank is None or pd.isna(rank) else str(int(rank))
    selected = "YES" if bool(row.get("selected")) else "NO"
    veto = "VETO" if bool(row.get("veto")) else "OK"
    stage = row.get("stage") or "n/a"
    quadrant = str(row.get("rrg_quadrant") or "n/a").upper()
    state_label = state.replace("_", " ")

    _md(
        f"""
        <div class="ticker-analysis-grid">
          <div class="tile">
            <div class="tile-label">State</div>
            <div class="tile-value" style="color:{_state_color_var(state)};font-size:1.1rem;">{_esc(state_label)}</div>
            <div class="tile-sub">Stage {_esc(str(stage))} / {_esc(quadrant)}</div>
          </div>
          <div class="tile">
            <div class="tile-label">Composite</div>
            <div class="tile-value {'up' if (s_score or 0) >= 0 else 'down'}">{_score_text(s_score)}<span class="grade {_grade_letter(s_score)}">{_grade_letter(s_score)}</span></div>
            <div class="tile-sub">rank {rank_text} in {_esc(asset_class)}</div>
          </div>
          <div class="tile">
            <div class="tile-label">Flow</div>
            <div class="tile-value {'up' if (f_score or 0) >= 0 else 'down'}">{_score_text(f_score)}</div>
            <div class="tile-sub">{veto}</div>
          </div>
          <div class="tile">
            <div class="tile-label">Selection</div>
            <div class="tile-value {'up' if selected == 'YES' else 'flat'}">{selected}</div>
            <div class="tile-sub">{_esc(ticker_label)} / {_esc(asset_class)}</div>
          </div>
        </div>
        """
    )
    st.dataframe(analysis_rows_frame(analysis), hide_index=True, width="stretch")
    if (not is_ad_hoc) and st.button(f"VIEW FULL DRILL-DOWN {ticker}", key=f"ticker_analyzer_drill_{ticker}", width="stretch"):
        _go_to_drill(ticker)


def render_explainer():
    with st.expander("HOW THIS WORKS - system, data flow, pillars, gates", expanded=False):
        _md(SYSTEM_EXPLAINER_HTML)


def render_component_docs():
    if not _operator_mode_enabled():
        return
    with st.expander("Component inventory", expanded=False):
        _md(component_docs_html(DASHBOARD_COMPONENT_DOCS))


def render_header():
    now = datetime.now()
    last_update = now.strftime("%H:%M")
    as_of = now.strftime("%a %b %d %Y | %H:%M %Z").upper().strip(" |").strip()
    cache_window = "60M CACHE"
    html = f"""
    <div class="app">
      <header class="header">
        <div class="brand">
          <span class="brand-mark"></span>
          SENTIMENT&nbsp;BOARD
        </div>
        <div class="meta">
          <span><span class="live-dot"></span>RENDERED | {last_update}</span>
          <span class="sep">|</span>
          <span>{as_of}</span>
          <span class="sep">|</span>
          <span><span class="val">{cache_window}</span></span>
        </div>
      </header>
    """
    _md(html)


def render_view_preferences():
    with st.expander("VIEW OPTIONS", expanded=False):
        def _load_preference_profile(profile_name: str) -> None:
            profile = next(
                (item for item in load_preference_profiles(PREFERENCE_PROFILES_PATH) if item.name == profile_name),
                None,
            )
            if profile is None:
                st.session_state.preference_profile_error = "profile unavailable"
                st.session_state.pop("preference_profile_message", None)
                return
            apply_preference_profile(st.session_state, profile)
            st.session_state.preference_profile_message = f"loaded profile {profile.name}"
            st.session_state.pop("preference_profile_error", None)

        def _save_preference_profile() -> None:
            result = save_preference_profile(
                st.session_state.get("preference_profile_name", ""),
                {
                    "bluf_mode": st.session_state.bluf_mode,
                    "view_density": st.session_state.view_density,
                    "sparkline_style": st.session_state.sparkline_style,
                    "color_palette": st.session_state.color_palette,
                },
                path=PREFERENCE_PROFILES_PATH,
            )
            if not result.ok:
                st.session_state.preference_profile_error = result.message
                st.session_state.pop("preference_profile_message", None)
                return
            st.session_state.preference_profile_message = result.message
            st.session_state.pop("preference_profile_error", None)
            if result.profile is not None:
                st.session_state.preference_profile_choice = result.profile.name

        def _delete_preference_profile(profile_name: str) -> None:
            if delete_preference_profile(profile_name, path=PREFERENCE_PROFILES_PATH):
                st.session_state.preference_profile_message = f"deleted profile {profile_name}"
                st.session_state.pop("preference_profile_error", None)
            else:
                st.session_state.preference_profile_error = "profile unavailable"
                st.session_state.pop("preference_profile_message", None)
            st.session_state.pop("preference_profile_choice", None)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.radio(
                "BLUF",
                BLUF_MODES,
                horizontal=True,
                key="bluf_mode",
            )
        with c2:
            st.radio(
                "Density",
                DENSITY_MODES,
                horizontal=True,
                key="view_density",
            )
        with c3:
            st.radio(
                "Sparkline",
                SPARKLINE_STYLES,
                horizontal=True,
                key="sparkline_style",
            )
        with c4:
            st.radio(
                "Palette",
                PALETTE_OPTIONS,
                horizontal=True,
                key="color_palette",
            )
        profiles = load_preference_profiles(PREFERENCE_PROFILES_PATH)
        profile_names = [profile.name for profile in profiles]
        profile_by_name = {profile.name: profile for profile in profiles}
        selected_value = st.session_state.get("preference_profile_choice")
        if selected_value and selected_value not in profile_by_name and "preference_profile_choice" in st.session_state:
            del st.session_state["preference_profile_choice"]
        p1, p2, p3, p4, p5 = st.columns([2, 2, 1, 1, 1])
        with p1:
            selected_profile_name = st.selectbox(
                "Profile",
                profile_names or ["No saved profiles"],
                key="preference_profile_choice",
                disabled=not profile_names,
            )
        selected_profile = profile_by_name.get(selected_profile_name)
        with p2:
            profile_name = st.text_input("Name", key="preference_profile_name", placeholder="Review desk")
        with p3:
            st.button(
                "Load",
                key="preference_profile_load",
                disabled=selected_profile is None,
                width="stretch",
                on_click=_load_preference_profile,
                args=(selected_profile_name,),
            )
        with p4:
            st.button(
                "Save",
                key="preference_profile_save",
                width="stretch",
                on_click=_save_preference_profile,
            )
        with p5:
            st.button(
                "Delete",
                key="preference_profile_delete",
                disabled=selected_profile is None,
                width="stretch",
                on_click=_delete_preference_profile,
                args=(selected_profile_name,),
            )
        if st.session_state.get("preference_profile_error"):
            st.warning(st.session_state.preference_profile_error)
        elif st.session_state.get("preference_profile_message"):
            st.caption(st.session_state.preference_profile_message)


def _sync_header_preference_widget(widget_key: str, target_key: str) -> None:
    st.session_state[widget_key] = st.session_state.get(target_key)


def _apply_header_preference(widget_key: str, target_key: str, allowed: tuple[str, ...]) -> None:
    value = st.session_state.get(widget_key)
    if value in allowed:
        st.session_state[target_key] = value


def render_drill_click_bridge():
    st.iframe(drill_click_bridge_html(), height=1)


def render_header_controls():
    _md('<div class="header-controls-slot"></div>')
    for widget_key, target_key in (
        ("header_bluf_mode", "bluf_mode"),
        ("header_view_density", "view_density"),
        ("header_sparkline_style", "sparkline_style"),
        ("header_color_palette", "color_palette"),
    ):
        _sync_header_preference_widget(widget_key, target_key)

    refresh_col, theme_col, view_col, density_col, spark_col, palette_col = st.columns([1, 1, 1.15, 1.15, 1.15, 1.15])
    with refresh_col:
        st.button("Refresh", key="header_refresh_data_button", width="stretch", on_click=_refresh_loaded_data)
    with theme_col:
        theme_label = "Light" if st.session_state.theme == "dark" else "Dark"
        st.button(theme_label, key="header_theme_toggle", width="stretch", on_click=toggle_theme, args=(st.session_state,))
    with view_col:
        st.selectbox(
            "VIEW",
            BLUF_MODES,
            key="header_bluf_mode",
            on_change=_apply_header_preference,
            args=("header_bluf_mode", "bluf_mode", BLUF_MODES),
        )
    with density_col:
        st.selectbox(
            "DENSITY",
            DENSITY_MODES,
            key="header_view_density",
            on_change=_apply_header_preference,
            args=("header_view_density", "view_density", DENSITY_MODES),
        )
    with spark_col:
        st.selectbox(
            "SPARK",
            SPARKLINE_STYLES,
            key="header_sparkline_style",
            on_change=_apply_header_preference,
            args=("header_sparkline_style", "sparkline_style", SPARKLINE_STYLES),
        )
    with palette_col:
        st.selectbox(
            "PALETTE",
            PALETTE_OPTIONS,
            key="header_color_palette",
            on_change=_apply_header_preference,
            args=("header_color_palette", "color_palette", PALETTE_OPTIONS),
        )

def render_bluf():
    if not should_render_bluf(st.session_state.bluf_mode):
        return
    compact = is_compact_bluf(st.session_state.bluf_mode)
    sub = (
        f"Model evidence: {bluf['exits_count']} tickers with major risk flags, "
        f"{bluf['warns_count']} showing topping signals, "
        f"{bluf['buys_count']} passing strict bullish evidence gates. "
        f"Universe: {len(scored)} instruments. "
        f"Risk regime is {('on' if regime.risk_on else 'off')} ({regime.phase_hint.lower()} cycle)."
    )
    compact_class = " compact" if compact else ""
    head_html = f"""
    <section class="section">
      <div class="bluf{compact_class}">
        <div class="bluf-head">
          <div class="bluf-eyebrow">
            <span class="pill-tiny">BLUF</span>
          <span>BOTTOM LINE | FORWARD OUTLOOK | {datetime.now().strftime('%H:%M')}</span>
            <span class="stamp">{'RISK-ON' if regime.risk_on else 'RISK-OFF'}</span>
          </div>
        </div>
        <div class="bluf-headline">
          <span class="exit-num tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_exit'])}">{bluf['exits_count']}</span> <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_exit'])}">EXIT</span>
          <span class="sep">|</span>
          <span class="warn-num tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_warning'])}">{bluf['warns_count']}</span> <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_warning'])}">WARNINGS</span>
          <span class="sep">|</span>
          <span class="buy-num tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_buy'])}">{bluf['buys_count']}</span> <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_buy'])}">NEW BUYS</span>
        </div>
        <div class="bluf-sub">{sub}</div>
    """
    if compact:
        _md(head_html + "</div></section>")
        return

    head_html += """
        <div class="bluf-actions">
    """
    cards = []
    for a in bluf["actions"]:
        first_ticker = next((it["t"] for it in a["tickers"] if it.get("t")), "")
        action_count = len(a["tickers"])
        items_html = "".join(
            f'<li {drill_bridge_attrs(it["t"], label=it["note"])}><span class="t">{it["t"]}<small>{_esc(_ticker_identity_subtext(it["t"]))}</small></span><span class="n">{it["note"]}</span></li>'
            for it in a["tickers"]
        ) or '<li><span class="t">-</span><span class="n">none</span></li>'
        card_html = f"""
        <div class="action-card {a['kind']}" {drill_bridge_attrs(first_ticker, label=a['label'])}>
          <div class="action-head">
            <div class="action-label">{a['label']}</div>
            <div class="action-eta">{a['eta']}</div>
          </div>
          <span class="pill {a['state']}" data-tip="{_esc(STATE_TIPS.get(a['state'], ""))}">{a['state'].replace('_', ' ')}</span>
          <div class="action-count">{action_count} ticker{'s' if action_count != 1 else ''} in this list</div>
          <ul class="action-list">{items_html}</ul>
        </div>
        """
        cards.append(card_html)
    _md(head_html + "".join(cards) + "</div></div></section>")
    selector_cols = st.columns(3)
    for col, a in zip(selector_cols, bluf["actions"]):
        with col:
            _render_drill_selector(
                f"bluf_{a['kind']}_drill",
                [it["t"] for it in a["tickers"]],
                f"DRILL-DOWN FROM {a['label']}",
            )


def _normalize_gate_passed(passed: bool | None) -> bool | None:
    if passed is None or pd.isna(passed):
        return None
    return bool(passed)


def _gate_class(passed: bool | None) -> str:
    normalized = _normalize_gate_passed(passed)
    if normalized is True:
        return "trigger-pass"
    if normalized is False:
        return "trigger-fail"
    return "trigger-neutral"


def _gate_label(passed: bool | None) -> str:
    normalized = _normalize_gate_passed(passed)
    if normalized is True:
        return "PASS"
    if normalized is False:
        return "FAIL"
    return "N/A"


def _gate_row(label: str, actual: str, rule: str, passed: bool | None, meaning: str) -> str:
    tone = _gate_class(passed)
    return (
        f"<tr class=\"{tone}\">"
        f"<td><b>{_esc(label)}</b><span>{_esc(meaning)}</span></td>"
        f"<td>{_esc(actual)}</td>"
        f"<td>{_esc(rule)}</td>"
        f"<td><span class=\"trigger-badge\">{_gate_label(passed)}</span></td>"
        "</tr>"
    )


def _forecast_horizon_for_state(state: str) -> str:
    return {
        "STAGE_2_BULLISH": "Evidence window: trend and Stage 2 evidence is usually reviewed over 4-26 weeks; flow evidence is shorter-term.",
        "HOLD": "Evidence window: trend evidence remains acceptable, but this is not a fresh-buy setup.",
        "WARNING": "Evidence window: review deterioration evidence over the next several sessions to weeks.",
        "EXIT": "Evidence window: a major risk gate failed; review risk plan and data quality before acting.",
        "BEARISH_STAGE_4": "Evidence window: bearish trend evidence can persist until a new base forms.",
        "STAGE_1_BASING": "Evidence window: watch for confirmation before treating it as Stage 2.",
    }.get(state, "No calibrated horizon available for this state.")


def _ticker_report_html(ticker: str, row) -> str:
    state = str(row.get("state") or "UNKNOWN")
    state_label = state.replace("_", " ")
    class_name = str(row.get("class") or "UNKNOWN")
    ticker_label = ticker_display_label(ticker)
    forecast = _forecast_horizon_for_state(state)
    verdict = _state_tip_for_row(ticker, row)

    s_score = _display_value(row.get("S_score"), signed=True, decimals=2)
    f_score = _display_value(row.get("F_score"), signed=True, decimals=2)
    mom = _display_value(row.get("mom_12_1"), signed=True, pct=True, decimals=1)
    stage = _display_value(row.get("stage"), decimals=0)
    faber = _display_value(row.get("faber"), decimals=0)
    antonacci = _display_value(row.get("antonacci"), decimals=0)
    rrg = str(row.get("rrg_quadrant") or "n/a")
    rs_ratio = _display_value(row.get("rs_ratio"), decimals=1)
    rs_momentum = _display_value(row.get("rs_momentum"), decimals=1)
    breadth = _display_value(row.get("breadth_50d"), pct=True, decimals=0)
    cmf = _display_value(row.get("cmf21"), signed=True, decimals=2)
    etf_flow = _display_value(row.get("etf_flow_5d_pct"), signed=True, pct=True, decimals=2)
    block_ratio = _display_value(row.get("block_up_ratio"), decimals=2)
    cycle_tilt_value = _display_value(row.get("cycle_tilt"), signed=True, decimals=2)
    mansfield = _display_value(row.get("mansfield_rs"), signed=True, decimals=2)
    rank = row.get("rank_in_class")
    rank_text = "n/a" if rank is None or pd.isna(rank) else str(int(rank))
    selected_text = "selected" if bool(row.get("selected")) else "not selected"
    veto_text = "flow veto active" if bool(row.get("veto")) else "no flow veto"
    grade = _grade_letter(row.get("S_score"))
    contradiction_note = (
        f"{ticker_label} can show composite grade {grade} while the state is {state_label} because these are different layers. "
        "The composite S-score ranks cross-sectional evidence against peers. The state machine is a gatekeeper: a failed trend, rotation, breadth, or flow rule can keep the state cautious even when the rank score is strong."
    )

    stage_value = row.get("stage")
    rrg_value = str(row.get("rrg_quadrant") or "")
    breadth_value = row.get("breadth_50d")
    cmf_value = row.get("cmf21")
    flow_value = row.get("F_score")
    etf_flow_value = row.get("etf_flow_5d_pct")
    mansfield_value = row.get("mansfield_rs")
    above_30wma_value = row.get("above_30wma")
    slope_value = row.get("ma_slope_pos")
    antonacci_value = row.get("antonacci")
    block_value = row.get("block_up_ratio")

    buy_rows = [
        _gate_row("Weinstein trend", f"Stage={stage}; above 30wMA={_display_value(above_30wma_value)}; slope up={_display_value(slope_value)}", "Stage = 2, price above 30wMA, MA slope up", stage_value == 2 and above_30wma_value is not False and slope_value is not False, "The main trend should be advancing."),
        _gate_row("Relative strength", f"Mansfield RS={mansfield}", "Mansfield RS > 0", None if mansfield_value is None or pd.isna(mansfield_value) else mansfield_value > 0, "The ticker should beat its benchmark."),
        _gate_row("RRG rotation", f"RRG={rrg}; RS Ratio={rs_ratio}; RS Momentum={rs_momentum}", "RRG quadrant = Leading", rrg_value == "Leading", "Leadership should be visible in relative rotation."),
        _gate_row("Breadth confirmation", f"Breadth={breadth}", "Breadth >= 60%", None if breadth_value is None or pd.isna(breadth_value) else breadth_value >= 0.60, "More constituents should participate in the move."),
        _gate_row("Money flow", f"CMF={cmf}; Flow={f_score}; ETF 5d flow={etf_flow}", "CMF > +0.05 and ETF flow >= 0", None if cmf_value is None or pd.isna(cmf_value) else cmf_value > 0.05 and (etf_flow_value is None or pd.isna(etf_flow_value) or etf_flow_value >= 0), "Accumulation should support the price trend."),
        _gate_row("Hard veto", veto_text, "F-score must stay above -0.5 sigma", not bool(row.get("veto")), "A flow veto blocks an otherwise strong setup."),
    ]

    risk_rows = [
        _gate_row("Trend break", f"above 30wMA={_display_value(above_30wma_value)}", "Healthy while price remains above 30wMA", None if above_30wma_value is None or pd.isna(above_30wma_value) else above_30wma_value is not False, "A weekly trend break weakens the Stage 2 thesis."),
        _gate_row("Relative strength break", f"Mansfield RS={mansfield}", "Healthy while Mansfield RS >= 0", None if mansfield_value is None or pd.isna(mansfield_value) else mansfield_value >= 0, "Underperformance can precede price damage."),
        _gate_row("Rotation breakdown", f"RRG={rrg}", "Healthy while RRG is not Lagging", None if not rrg_value else rrg_value != "Lagging", "Lagging rotation means relative momentum has broken."),
        _gate_row("Distribution", f"CMF={cmf}; block up ratio={block_ratio}", "Healthy while CMF >= -0.10 and block ratio >= 0.70", not ((cmf_value is not None and not pd.isna(cmf_value) and cmf_value < -0.10) or (block_value is not None and not pd.isna(block_value) and block_value < 0.70)), "Negative volume pressure can invalidate the setup."),
        _gate_row("Absolute momentum", f"Antonacci={antonacci}", "Healthy while Antonacci != 0", None if antonacci_value is None or pd.isna(antonacci_value) else antonacci_value != 0, "The ticker should beat cash/T-bills on the lookback."),
    ]

    pillar_rows = [
        _gate_row("1. Momentum", f"MOM 12-1={mom}; S={s_score}", "Positive and preferably top-ranked", (row.get("mom_12_1") or 0) > 0, "Classic winners tend to keep leading over 3-12 months."),
        _gate_row("2. Trend filters", f"Faber={faber}; Stage={stage}; Antonacci={antonacci}", "Faber=1, Stage=2, Antonacci=1", row.get("faber") == 1 and stage_value == 2 and antonacci_value == 1, "Trend filters keep the system aligned with major uptrends."),
        _gate_row("3. Weinstein Stage", f"Stage={stage}; Mansfield={mansfield}", "Stage 2 with RS > 0", stage_value == 2 and (mansfield_value is not None and not pd.isna(mansfield_value) and mansfield_value > 0), "Stage 2 is the advance phase."),
        _gate_row("4. Dual momentum", f"MOM={mom}; Antonacci={antonacci}", "Relative and absolute momentum both positive", (row.get("mom_12_1") or 0) > 0 and antonacci_value == 1, "The ticker should beat peers and cash."),
        _gate_row("5. RRG rotation", f"RRG={rrg}; ratio={rs_ratio}; momentum={rs_momentum}", "Leading or Improving preferred", rrg_value in {"Leading", "Improving"}, "Rotation shows where leadership is moving."),
        _gate_row("6. Business cycle", f"Cycle tilt={cycle_tilt_value}", "Positive is supportive", (row.get("cycle_tilt") or 0) > 0, "Macro phase can add or subtract sector tailwind."),
        _gate_row("7. Institutional flow", f"F={f_score}; CMF={cmf}; ETF flow={etf_flow}; block ratio={block_ratio}", "F > 0 and no veto preferred", (flow_value is not None and not pd.isna(flow_value) and flow_value > 0) and not bool(row.get("veto")), "Flow confirms whether real money supports the signal."),
    ]

    state_color = _state_color_var(state)
    return f"""
    <section class="section ticker-report" id="ticker-report">
      <div class="section-head">
        <h2>Complete ticker report <span class="count">{_esc(ticker_label)} | {_esc(class_name)}</span></h2>
        <div class="right">Evidence window | {_esc(forecast)}</div>
      </div>
      <div class="ticker-report-grid">
        <div class="ticker-report-verdict">
          <div class="report-kicker">Plain-English verdict</div>
          <h3 style="color:{state_color};">{_esc(state_label)}</h3>
          <p>{_esc(verdict)}</p>
          <div class="report-facts">
            <span>S {s_score}</span>
            <span>Grade {grade}</span>
            <span>F {f_score}</span>
            <span>Rank {rank_text}</span>
            <span>{_esc(selected_text)}</span>
          </div>
        </div>
        <div class="ticker-report-watch">
          <div class="report-kicker">Score and state relationship</div>
          <p>{_esc(contradiction_note)}</p>
          <div class="report-kicker">What would change the call</div>
          <p><b>For bullish calls:</b> watch for a weekly close below the 30-week average, Mansfield RS falling below zero, RRG slipping into Lagging, CMF moving below -0.10, or a flow veto.</p>
          <p><b>For warnings/exits:</b> the call improves when price reclaims the 30-week average, breadth recovers, RRG rotates back toward Improving/Leading, and flow turns positive.</p>
        </div>
      </div>
      <div class="ticker-report-grid report-tables">
        <div>
          <h3>Trigger checklist</h3>
          <div class="report-kicker">Stage 2 buy gates</div>
          <table class="ticker-report-table"><tbody>{"".join(buy_rows)}</tbody></table>
        </div>
        <div>
          <h3>Risk / exit triggers</h3>
          <div class="report-kicker">Invalidation watch</div>
          <table class="ticker-report-table"><tbody>{"".join(risk_rows)}</tbody></table>
        </div>
      </div>
      <div class="ticker-report-matrix">
        <h3>7-pillar methodology matrix</h3>
        <table class="ticker-report-table"><tbody>{"".join(pillar_rows)}</tbody></table>
      </div>
    </section>
    """


def _price_chart_narrative(ticker: str, row, frame: pd.DataFrame) -> str:
    label = ticker_display_label(ticker)
    try:
        weekly = frame.resample("W-FRI").agg({"close": "last"})
        sma30 = weekly["close"].rolling(30).mean()
        latest_close = float(weekly["close"].dropna().iloc[-1])
        latest_sma = float(sma30.dropna().iloc[-1])
        distance = (latest_close / latest_sma - 1.0) * 100 if latest_sma else None
        distance_text = "n/a" if distance is None else f"{distance:+.1f}%"
    except Exception:
        latest_close = latest_sma = None
        distance_text = "n/a"
    above = _display_value(row.get("above_30wma"))
    slope = _display_value(row.get("ma_slope_pos"))
    stage = _display_value(row.get("stage"), decimals=0)
    close_text = "n/a" if latest_close is None else f"{latest_close:.2f}"
    sma_text = "n/a" if latest_sma is None else f"{latest_sma:.2f}"
    return (
        f"{label}: latest weekly close is {close_text}, 30-week average is {sma_text}, distance {distance_text}. "
        f"Dashboard readings: Stage={stage}, price above 30wMA={above}, average slope up={slope}. "
        "A bullish trend needs price above the average and a rising average; a weekly close back below the average weakens the trend call."
    )


def _cmf_chart_narrative(ticker: str, row) -> str:
    label = ticker_display_label(ticker)
    cmf = _display_value(row.get("cmf21"), signed=True, decimals=2)
    flow = _display_value(row.get("F_score"), signed=True, decimals=2)
    if row.get("cmf21") is None or pd.isna(row.get("cmf21")):
        reading = "CMF is not available, so flow confirmation is weaker."
    elif float(row.get("cmf21")) > 0.05:
        reading = "CMF is supportive accumulation evidence."
    elif float(row.get("cmf21")) < -0.10:
        reading = "CMF is distribution evidence and can trigger risk controls."
    else:
        reading = "CMF is neutral or only mildly supportive."
    return f"{label}: CMF(21) is {cmf} and flow F-score is {flow}. {reading} The model prefers CMF above +0.05 for fresh bullish Stage 2 entries."


def _obv_chart_narrative(ticker: str, row) -> str:
    label = ticker_display_label(ticker)
    divergence = bool(row.get("obv_divergence"))
    obv_slope = _display_value(row.get("obv_slope"), signed=True, decimals=2)
    message = (
        "OBV divergence is flagged, meaning volume confirmation is not keeping up with price."
        if divergence
        else "No OBV divergence is flagged in the current snapshot."
    )
    return f"{label}: OBV slope reading is {obv_slope}. {message} This chart checks whether volume is confirming the price trend or warning that buyers are fading."


def _provider_status_list_html(providers) -> str:
    rows = []
    for provider in providers or []:
        if not isinstance(provider, dict):
            continue
        status = _esc(str(provider.get("status", "info")))
        label = _esc(str(provider.get("label", "Provider")))
        mode = _esc(str(provider.get("mode", provider.get("status", "unknown"))))
        source = _esc(str(provider.get("provider", "")))
        signal = _esc(str(provider.get("signal", "")))
        meta = " | ".join(part for part in (source, signal) if part)
        rows.append(
            f'<li class="{status}"><b>{label}</b><span>{mode}</span>'
            f'<small>{meta}</small></li>'
        )
    if not rows:
        return ""
    return '<ul class="data-health-provider-list">' + "".join(rows) + "</ul>"


def render_data_health():
    provider_statuses = provider_flow_health_statuses()
    rows = data_health_rows(
        ohlcv=ohlcv,
        expected_symbols=DATA_SYMBOLS,
        ohlcv_result=ohlcv_result,
        fred_data=_fred_data,
        compute_created_at=dashboard_compute_created_at,
        provider_flow_stubbed=provider_flow_feeds_stubbed(provider_statuses),
        provider_flow_statuses=provider_statuses,
        fred_configured=fred_available(),
    )
    storage = state_storage_health()
    storage_status = "healthy" if storage.get("state_file_exists") and storage.get("transition_journal_exists") else "warning"
    rows.append(
        {
            "source": "Persisted state and transitions",
            "role": "Critical: dashboard memory for state changes, alerts, feeds, and debrief evidence",
            "status": storage_status,
            "latest": str(storage.get("state_updated") or "-"),
            "freshness": (
                f"{storage.get('by_ticker_count', 0)} states; "
                f"{storage.get('journal_transition_count', 0)} journaled transitions"
            ),
            "coverage": f"latest transition {storage.get('latest_transition_date') or 'none'}",
            "detail": (
                f"state={storage.get('state_file')}; "
                f"journal={storage.get('transition_journal')}; "
                f"backups={storage.get('backup_dir')}"
            ),
            "lane_id": "state_persistence",
            "sla": "must persist across restarts",
            "refresh_label": "Re-read state log",
            "refresh_key": "data_health_refresh_state_persistence",
            "severity_symbol": "OK" if storage_status == "healthy" else "WARN",
        }
    )
    summary = dashboard_health_summary(rows)
    requested_at = st.session_state.get("data_refresh_requested_at")
    refresh_text = f"Manual refresh requested {requested_at}" if requested_at else "No manual refresh in this session"
    cards_html = ""
    for row in rows:
        status = str(row.get("status", "warning"))
        latest_text = _esc(str(row.get("latest", "-")))
        coverage = str(row.get("coverage") or "")
        sla = str(row.get("sla") or "")
        severity = str(row.get("severity_symbol") or status.upper())
        subline = f"latest {latest_text}"
        if coverage:
            subline += f" | {coverage}"
        if sla:
            subline += f" | SLA {sla}"
        cards_html += f"""
        <div class="data-health-card {status}">
          <div class="data-health-card-head">
            <span>{_esc(str(row.get('source', 'Source')))}</span>
            <b>{_esc(severity)} | {_esc(status.upper())}</b>
          </div>
          <div class="data-health-main">{_esc(str(row.get('freshness', '-')))}</div>
          <div class="data-health-sub">{_esc(subline)}</div>
          <div class="data-health-role">{_esc(str(row.get('role', '')))}</div>
          {_provider_status_list_html(row.get('providers', []))}
          <p>{_esc(str(row.get('detail', '')))}</p>
        </div>
        """
    _md(
        f"""
        <section class="section data-health-panel">
          <div class="section-head">
            <h2>Data and dashboard health <span class="count">{_esc(summary['label'])}</span></h2>
            <div class="right">{_esc(refresh_text)}</div>
          </div>
          <div class="data-health-summary {summary['status']}">
            <span>{_esc(summary['label'])}</span>
            <b>{_esc(summary['detail'])}</b>
          </div>
          <div class="data-health-grid">{cards_html}</div>
        </section>
        """
    )
    _md('<div class="data-health-refresh-grid">')
    refresh_cols = st.columns(len(rows))
    for idx, row in enumerate(rows):
        with refresh_cols[idx]:
            refresh_label = str(row.get("refresh_label", "Refresh lane"))
            refresh_key = str(row.get("refresh_key", f"data_health_refresh_{idx}"))
            lane_id = str(row.get("lane_id"))
            st.button(refresh_label, key=refresh_key, on_click=_refresh_data_lane, args=(str(row.get("lane_id")),), width="stretch")
            _md(
                f'<div class="lane-refresh-caption">{_esc(str(row.get("severity_symbol", "")))} | '
                f'{_esc(str(row.get("freshness", "-")))} | {_esc(str(row.get("sla", "")))} | '
                f'{_esc(_lane_completed_text(lane_id))}</div>'
            )
    _md("</div>")
    if st.button("Refresh all lanes", key="data_health_refresh_all_button", on_click=_refresh_loaded_data, width="stretch"):
        pass


def render_status():
    risk_on = regime.risk_on
    # FRED-derived metrics (None if FRED not configured)
    if getattr(regime, 'fred_used', False):
        fred_badge = '<span class="tile-delta" style="background:var(--accent-dim);color:var(--accent);border-color:var(--accent)">FRED</span>'
        # Compact sub: INDPRO + curve + (recession prob if present)
        bits = []
        if regime.indpro_yoy is not None:
            bits.append(f"INDPRO {regime.indpro_yoy:+.1%} YoY")
        if regime.curve_2s10s is not None:
            bits.append(f"2s10s {regime.curve_2s10s:+.2f}")
        if regime.recession_prob is not None and regime.recession_prob >= 5:
            bits.append(f"rec prob {regime.recession_prob:.0f}%")
        cycle_sub = " | ".join(bits) if bits else regime.note
    else:
        fred_badge = '<span class="tile-delta" style="opacity:0.6">PROXY</span>'
        cycle_sub = regime.note
    risk_label = "RISK-ON" if risk_on else "RISK-OFF"
    risk_tone = "up" if risk_on else "down"
    risk_dot = "var(--green)" if risk_on else "var(--red)"
    sub_risk = ("SPY > 10mo SMA" if risk_on else "SPY < 10mo SMA")

    # phase bar
    phase_bar_html = ""
    if phase_idx >= 0:
        bars = "".join(
            f'<div><div class="ph {"on" if i == phase_idx else ""}"></div>'
            f'<div class="lbl" style="margin-top:4px;color:{"var(--fg-dim)" if i == phase_idx else "var(--muted-2)"}">{lbl}</div></div>'
            for i, lbl in enumerate(["EARLY", "MID", "LATE", "RECESS"])
        )
        phase_bar_html = f'<div class="phase-bar">{bars}</div>'

    n_warn = bluf["warns_count"] + bluf["exits_count"]
    today = datetime.now(timezone.utc).date().isoformat()
    transition_count_24h = sum(1 for row in transitions if str(row.get("date", "")) == today)
    delta = f'<span class="tile-delta">{transition_count_24h} today</span>' if n_warn > 0 else ""

    yc_label = (
        "POSITIVE" if regime.yield_curve_positive
        else ("INVERTED" if regime.yield_curve_positive is False else "-")
    )

    session_row = session_range_tile(ohlcv.get(BENCH["US"]), BENCH["US"])
    session_tile_html = _macro_tile_html(session_row)
    macro_tiles_html = "".join(_macro_tile_html(row) for row in macro_tile_rows(ohlcv, fred_data=_fred_data))
    fred_macro_groups_html = ""
    for group in fred_macro_tile_groups(_fred_data):
        rows_html = "".join(_macro_tile_html(row, extra_class="fred-macro-tile") for row in group["rows"])
        fred_macro_groups_html += f"""
        <div class="fred-macro-group">
          <div class="fred-macro-group-label">{_esc(group['group'])}</div>
          <div class="fred-macro-grid">{rows_html}</div>
        </div>
        """

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Market state <span class="count">Live indicators</span></h2>
        <div class="right">UPDATED {datetime.now().strftime('%H:%M').upper()}</div>
      </div>
      <div class="status-row">

        <div class="tile">
          <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_regime'])}">Risk regime</span></div>
          <div class="tile-value {risk_tone}">
            <span class="dot" style="background:{risk_dot}"></span>
            {risk_label}
          </div>
          <div class="tile-sub">{sub_risk} | curve {yc_label.lower()}</div>
        </div>

        <div class="tile">
          <div class="tile-label">
            <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_phase'])}">Cycle phase</span>
            {fred_badge}
          </div>
          <div class="tile-value">
            <span class="dot" style="background:var(--amber)"></span>
            {regime.phase_hint}
          </div>
          <div class="tile-sub">{cycle_sub}</div>
          {phase_bar_html}
        </div>

        <div class="tile">
          <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_warnings'])}">Active warnings</span>{delta}</div>
          <div class="tile-value warn">
            <span class="dot" style="background:var(--amber)"></span>
            {n_warn}
          </div>
          <div class="tile-sub">{bluf['exits_count']} exit | {bluf['warns_count']} warn</div>
        </div>

        {session_tile_html}
        {macro_tiles_html}

      </div>
      <div class="fred-macro-context">
        <div class="fred-macro-title">Expanded FRED macro context</div>
        {fred_macro_groups_html}
      </div>
    </section>
    """
    _md(html)


def render_momentum_v2_screens():
    display_keys = list(MOMENTUM_V2_DISPLAY_LABELS.keys())
    display_col, screen_col = st.columns([1.15, 1])
    with display_col:
        selected_display = st.segmented_control(
            "Momentum v2 display",
            options=display_keys,
            format_func=lambda key: MOMENTUM_V2_DISPLAY_LABELS[key],
            key="momentum_v2_display",
        )
    with screen_col:
        selected_screen = st.segmented_control(
            "Momentum v2 screen",
            options=list(MOMENTUM_V2_SCREEN_LABELS.keys()),
            format_func=lambda key: MOMENTUM_V2_SCREEN_LABELS[key],
            key="momentum_v2_screen",
        )
    selected_display = selected_display if selected_display in MOMENTUM_V2_DISPLAY_LABELS else "C"
    selected_screen = selected_screen if selected_screen in MOMENTUM_V2_SCREEN_LABELS else "overview"
    try:
        created = pd.Timestamp.fromtimestamp(float(dashboard_compute_created_at))
        as_of = created.strftime("%Y-%m-%d %H:%M")
    except Exception:
        as_of = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = build_momentum_v2_rows(scored, phase=regime.phase_hint)
    _md(render_momentum_v2_display(
        selected_display,
        rows,
        as_of,
        screen=selected_screen,
        focus_ticker=st.session_state.drill_ticker,
    ))


def render_alerts():
    st.segmented_control(
        "Transition history",
        options=[25, 100, 500],
        format_func=lambda value: f"Latest {value}",
        key="transition_history_limit",
    )
    rows = ""
    for r in transitions[:8]:
        new_state = r.get("to", "")
        from_state = r.get("from", "-")
        dot_color = color_for_state(new_state)
        when = r.get("date", "")
        ticker = str(r.get("ticker", "")).upper()
        ticker_name = _ticker_identity_subtext(ticker)
        pulse_class = transition_row_pulse_class(r)
        sentiment_class, sentiment_label, sentiment_symbol = _transition_sentiment(r)
        rows += f"""
        <div class="alert-row {new_state} {pulse_class}" {drill_bridge_attrs(ticker, label=new_state)}>
          <span class="dot" style="background:{dot_color}"></span>
          <span class="t">{_esc(ticker)}<small>{_esc(ticker_name)}</small></span>
          <span class="transition-badge {sentiment_class}"><span>{sentiment_symbol}</span>{sentiment_label}</span>
          <span class="change">
            <span class="from">{from_state.replace('_', ' ')}</span>
            <span class="arrow">-></span>
            <span class="to">{new_state.replace('_', ' ')}</span>
          </span>
          <span class="when">{when}</span>
          <span class="chev">></span>
        </div>
        """
    if not rows:
        storage = state_storage_health()
        state_count = storage.get("by_ticker_count", 0)
        journal_path = storage.get("transition_journal", "data/state_transitions.jsonl")
        rows = (
            '<div class="alert-row empty-transition-history">'
            '<span class="dot" style="background:var(--muted-2)"></span>'
            '<span class="t">NONE<small>state memory active</small></span>'
            '<span class="transition-badge transition-neutral"><span>=</span>neutral</span>'
            f'<span class="change">No persisted transition records yet. The Pi has {state_count} current ticker states and is ready to append future changes to {_esc(str(journal_path))}.</span>'
            '<span class="when"></span><span class="chev"></span></div>'
        )

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Recent transitions <span class="count">{len(transitions)} of latest {transition_history_limit}</span></h2>
        <div class="right">{datetime.now().strftime('%H:%M').upper()}</div>
      </div>
      <div class="alerts">{rows}</div>
    </section>
    """
    _md(html)
    _render_drill_selector(
        "alert_drill",
        [str(r.get("ticker", "")).upper() for r in transitions[:8]],
        "DRILL-DOWN FROM RECENT TRANSITIONS",
    )


def render_picks():
    selected_picks = scored[scored["selected"]].sort_values(["S_score", "F_score", "mom_12_1"], ascending=[False, False, False])
    if selected_picks.empty:
        basket_rows = defensive_basket_rows(scored)
        cards_html = ""
        for row in basket_rows:
            ticker = str(row["ticker"])
            ticker_name = _ticker_identity_subtext(ticker)
            state = str(row["state"])
            available = bool(row["available"])
            pill_class = state if available and state in STATE_TIPS else "HOLD"
            pill_label = state.replace("_", " ") if available else "DATA PENDING"
            state_tip = _state_tip_for_row(ticker, row) if available else "Awaiting defensive data."
            unavailable_class = "" if available else " unavailable"
            s_score = row["s_score"]
            f_score = row["f_score"]
            s_text = "--" if s_score is None else f"{float(s_score):+.2f}"
            f_text = "--" if f_score is None else f"{float(f_score):+.2f}"
            s_class = "" if s_score is None else ("pos" if float(s_score) >= 0 else "neg")
            f_class = "" if f_score is None else ("pos" if float(f_score) >= 0 else "neg")
            s_tip = _metric_tip_for_row(ticker, row, "S") if available else "S-score unavailable until this defensive ticker is scored."
            f_tip = _metric_tip_for_row(ticker, row, "F") if available else "F-score unavailable until this defensive ticker is scored."
            cards_html += f"""
            <div class="pick defensive-card {pill_class}{unavailable_class}" {drill_bridge_attrs(ticker, label=str(row["role"])) if available else ""}>
              <div class="pick-top">
                <div>
                  <div class="pick-ticker">{ticker}<span class="ticker-name">{_esc(ticker_name)}</span></div>
                  <div class="pick-class">{_esc(str(row["role"]))}</div>
                </div>
                <span class="pill {pill_class}" data-tip="{_esc(state_tip)}">{pill_label}</span>
              </div>
              <div class="defensive-note">{_esc(str(row["note"]))}</div>
              <div class="pick-metrics">
                <div class="m"><span class="k tip-cue" data-tip="{_esc(s_tip)}">S</span><span class="v {s_class}">{s_text}</span></div>
                <div class="m"><span class="k tip-cue" data-tip="{_esc(f_tip)}">F</span><span class="v {f_class}">{f_text}</span></div>
              </div>
              <div class="pick-foot">
                <span>ROTATION</span>
                <span class="quad">DEFENSIVE</span>
              </div>
            </div>
            """
        _md(f"""
        <section class="section">
          <div class="section-head">
            <h2>Picks <span class="count">0 active</span></h2>
            <div class="right">NO PICKS MEET GATES</div>
          </div>
          <div class="empty-state">
            <div class="empty-state-copy">
              <div class="empty-kicker">RISK-OFF BASKET</div>
              <h3>No picks meet the gates</h3>
              <p>Momentum leadership is not passing all entry filters right now. Until a fresh leader clears the gates, the defensive rotation view focuses on TLT / GLD / BIL.</p>
            </div>
            <div class="picks-grid defensive-grid">{cards_html}</div>
          </div>
        </section>
        """)
        _render_drill_selector("defensive_drill", [str(row["ticker"]) for row in basket_rows if row["available"]], "DRILL-DOWN FROM DEFENSIVE BASKET")
        return

    cards_html = ""
    for pick_rank, (tkr, p) in enumerate(selected_picks.iterrows(), start=1):
        state = p["state"]
        s = p["S_score"]
        f = p["F_score"]
        grade = _grade_letter(s)
        mom = (p["mom_12_1"] or 0) * 100
        stage = p.get("stage") or "-"
        quad = (p.get("rrg_quadrant") or "-").upper()
        klass_lbl = p["class"]
        spark_color = "#26d65b" if mom >= 0 else "#ef4f4a"
        spark = svg_sparkline(
            ohlcv.get(tkr),
            spark_color,
            style=sparkline_mode(st.session_state.sparkline_style),
        ) if tkr in ohlcv else ""
        mom_class = "pos" if mom >= 0 else "neg"
        s_class = "pos" if s >= 0 else "neg"
        f_class = "pos" if f >= 0 else "neg"
        pulse_class = transition_pulse_class(tkr, transitions)
        state_tip = _state_tip_for_row(tkr, p)
        ticker_name = _ticker_identity_subtext(tkr)
        s_tip = _metric_tip_for_row(tkr, p, "S")
        f_tip = _metric_tip_for_row(tkr, p, "F")
        mom_tip = _metric_tip_for_row(tkr, p, "MOM")
        stage_tip = _metric_tip_for_row(tkr, p, "STAGE")
        rrg_tip = _metric_tip_for_row(tkr, p, "RRG")

        cards_html += f"""
        <div class="pick {state} {pulse_class}" {drill_bridge_attrs(tkr, label=klass_lbl)}>
          <div class="pick-top">
            <div>
              <div class="pick-ticker"><span class="pick-rank">#{pick_rank}</span>{tkr}<span class="ticker-name">{_esc(ticker_name)}</span></div>
              <div class="pick-class">{klass_lbl}</div>
            </div>
            <span class="pill {state}" data-tip="{_esc(state_tip)}">{state.replace('_', ' ')}</span>
          </div>
          {spark}
          <div class="pick-metrics">
            <div class="m"><span class="k tip-cue" data-tip="{_esc(s_tip)}">S</span><span class="v {s_class}">{s:+.2f}<span class="grade {grade}">{grade}</span></span></div>
            <div class="m"><span class="k tip-cue" data-tip="{_esc(f_tip)}">F</span><span class="v {f_class}">{f:+.2f}</span></div>
            <div class="m"><span class="k tip-cue" data-tip="{_esc(mom_tip)}">MOM</span><span class="v {mom_class}">{mom:+.1f}%</span></div>
            <div class="m"><span class="k tip-cue" data-tip="{_esc(stage_tip)}">STAGE</span><span class="v">{stage}</span></div>
          </div>
          <div class="pick-foot">
            <span class="tip-cue" data-tip="{_esc(rrg_tip)}">RRG</span>
            <span class="quad">{quad}</span>
          </div>
        </div>
        """

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Picks <span class="count">{len(selected_picks)} active</span></h2>
        <div class="right">SORTED BY S SCORE</div>
      </div>
      <div class="picks-grid">{cards_html}</div>
    </section>
    """
    _md(html)
    _render_drill_selector("pick_drill", selected_picks.index.tolist(), "DRILL-DOWN FROM PICKS")


def render_rrg():
    _md('<section class="section"><div class="section-head">'
                f'<h2>Relative Rotation Graph <span class="count">{st.session_state.klass}</span></h2>'
                '<div class="right">SELECT A TICKER FOR DETAIL</div></div></section>')

    # class selector (Streamlit native buttons styled by our CSS)
    cls_list = list(UNIVERSE_BY_CLASS.keys()) + ["ALL"]
    _md('<div class="rrg-class-controls-slot"></div>')
    cols = st.columns(len(cls_list))
    for c, cls in zip(cols, cls_list):
        if c.button(cls.upper(), key=f"cls_{cls}",
                    type="primary" if st.session_state.klass == cls else "secondary"):
            st.session_state.klass = cls
            st.rerun()

    # filter scored df
    if st.session_state.klass == "ALL":
        rrg_sub = scored.copy()
    else:
        rrg_sub = scored[scored["class"] == st.session_state.klass].copy()

    # quadrant counts
    quads = {"Leading": [], "Weakening": [], "Lagging": [], "Improving": []}
    for tkr, r in rrg_sub.iterrows():
        q = r.get("rrg_quadrant")
        if q in quads:
            quads[q].append(tkr)

    left_col, right_col = st.columns([2.2, 1])

    with left_col:
        if not rrg_sub.empty:
            st.iframe(
                rrg_plotly_click_bridge_html(rrg_chart_dark(rrg_sub, title="")),
                height=620,
            )
        else:
            st.info("No data for this class.")

    with right_col:
        for q, color_cls in [("Leading", "leading"), ("Weakening", "weakening"),
                              ("Lagging", "lagging"), ("Improving", "improving")]:
            tickers = quads[q]
            count = len(tickers)
            ticks = " / ".join(f"{ticker} | {_ticker_display_name(ticker)}" for ticker in tickers[:8]) if tickers else "-"
            _md(f'<div class="quad-card {color_cls}" {drill_bridge_attrs(tickers[0], label=q) if tickers else ""}>'
                f'<div class="qlbl tip-cue" data-tip="{_esc(INDICATOR_TIPS["tip_q_" + q.lower()])}">{q}</div>'
                f'<div class="qcount">{count}</div>'
                f'<div class="qtick">{ticks}</div>'
                f'</div>',)
            _render_drill_selector(f"rrg_drill_{q.lower()}", tickers[:8], "DRILL-DOWN FROM RRG")


def render_sector_spaghetti():
    fig = sector_spaghetti_chart(ohlcv, US_SECTORS, BENCH["US"])
    _md(
        """
        <section class="section" id="sector-spaghetti">
          <div class="section-head">
            <h2>Sector spaghetti chart <span class="count">US sectors</span></h2>
            <div class="right">12M RELATIVE STRENGTH VS SPY</div>
          </div>
        </section>
        """
    )
    if not fig.data:
        st.info("Sector relative-strength chart is unavailable until sector and SPY price data are loaded.")
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    ranked = []
    for trace in fig.data:
        trace_y = [] if trace.y is None else list(trace.y)
        y_values = [value for value in trace_y if value is not None and not pd.isna(value)]
        if not y_values:
            continue
        ranked.append((str(trace.name), float(y_values[-1])))
    ranked.sort(key=lambda item: item[1], reverse=True)
    if ranked:
        leaders = ", ".join(f"{name} ({value:.1f})" for name, value in ranked[:3])
        laggards = ", ".join(f"{name} ({value:.1f})" for name, value in ranked[-3:])
        _md(
            f"""
            <div class="chart-help spaghetti-help">
              <b>How to read it.</b> Each line starts at 100 and tracks relative strength versus SPY over roughly 12 months.
              Above 100 means that sector ETF outperformed SPY since the start of the window; below 100 means it lagged.
              Current leaders: {_esc(leaders)}. Current laggards: {_esc(laggards)}.
              Hover a line to see the ETF identity, date, and relative-strength value.
            </div>
            """
        )


def render_drill():
    sel = st.session_state.drill_ticker
    if sel not in ohlcv:
        return

    row = scored.loc[sel] if sel in scored.index else None
    if row is None:
        return

    state = row["state"]
    color = color_for_state(state)

    # picker
    pick_options = sorted(scored.index.tolist())
    new_sel = st.selectbox("DRILL-DOWN TICKER", pick_options,
                           index=pick_options.index(sel) if sel in pick_options else 0,
                           label_visibility="visible")
    if new_sel != sel:
        _go_to_drill(new_sel)
    st.radio(
        "CHART RANGE",
        DRILL_RANGE_OPTIONS,
        horizontal=True,
        key="drill_range",
    )
    selected_range = st.session_state.drill_range
    drill_ohlcv = filter_ohlcv_lookback(ohlcv[sel], selected_range)
    visible_since = drill_ohlcv.index.min()

    # header tiles
    head_html = f"""
    <section class="section" id="drill">
      <div class="section-head">
        <h2>Per-ticker drill-down <span class="count">{_esc(ticker_display_label(sel))} | {row['class']}</span></h2>
        <div class="right">{state.replace('_', ' ')}</div>
      </div>
      <div class="drill">
        <div class="drill-metrics">

          <div class="tile">
            <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_drill_composite'])}">Composite</span></div>
            <div class="tile-value {'up' if row['S_score'] >= 0 else 'down'}">{row['S_score']:+.3f}<span class="grade {_grade_letter(row['S_score'])}">{_grade_letter(row['S_score'])}</span></div>
            <div class="tile-sub">rank {int(row.get('rank_in_class') or 0)} in {row['class']}</div>
            <div class="tile-help">Weighted z-score across the 7 pillars (weights total 1.00). <b>Higher = better.</b> S &ge; +1.0 is grade A, &le; -1.5 is grade F. Hard veto if F &lt; -0.5&sigma;.</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_drill_flow'])}">Flow score</span></div>
            <div class="tile-value {'up' if row['F_score'] >= 0 else 'down'}">{row['F_score']:+.3f}</div>
            <div class="tile-sub">{'VETO' if row.get('veto') else 'OK'} | CMF {row.get('cmf21', 0) or 0:+.2f}</div>
            <div class="tile-help">Money flow z-score: CMF + OBV slope + ETF creations + block ratio + RVOL + short-interest delta when available. <b>F &gt; 0 = supportive flow evidence</b>; F &lt; -0.5&sigma; triggers a model veto.</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_drill_state'])}">State</span></div>
            <div class="tile-value" style="color:{color};font-size:1.1rem;">{state.replace('_', ' ')}</div>
            <div class="tile-sub">Stage {row.get('stage', '-')} | {(row.get('rrg_quadrant') or '-').upper()}</div>
            <div class="tile-help">State machine output. <b>STAGE 2 BULLISH</b> = strongest bullish evidence. <b>HOLD</b> = acceptable trend evidence. <b>WARNING</b> = deterioration evidence. <b>EXIT / BEARISH</b> = major risk gates failed. Hover the pill for the full gate definition.</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_drill_momentum'])}">12-1 Momentum</span></div>
            <div class="tile-value {'up' if (row.get('mom_12_1') or 0) >= 0 else 'down'}">{(row.get('mom_12_1') or 0)*100:+.1f}%</div>
            <div class="tile-sub">Mansfield RS {row.get('mansfield_rs', 0) or 0:+.1f}</div>
            <div class="tile-help">Jegadeesh-Titman classic: 12-month total return excluding the most recent month. The skip-1 removes short-term reversal noise. <b>Top decile is the winner basket.</b></div>
          </div>

        </div>
      </div>
    </section>
    """
    _md(head_html)
    _md(_ticker_report_html(sel, row))

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(price_chart_with_30wma(ohlcv[sel], sel, visible_since=visible_since),
                        width="stretch", config={"displayModeBar": False})
        _md(f'<div class="chart-help"><b>Weekly price vs 30-week average.</b> {_esc(_price_chart_narrative(sel, row, ohlcv[sel]))}</div>')
    with c2:
        st.plotly_chart(cmf_chart(ohlcv[sel], sel, visible_since=visible_since),
                        width="stretch", config={"displayModeBar": False})
        _md(f'<div class="chart-help"><b>Chaikin Money Flow.</b> {_esc(_cmf_chart_narrative(sel, row))}</div>')
    st.plotly_chart(obv_chart(ohlcv[sel], sel, visible_since=visible_since),
                    width="stretch", config={"displayModeBar": False})
    _md(f'<div class="chart-help"><b>Price vs OBV.</b> {_esc(_obv_chart_narrative(sel, row))}</div>')


def render_comparison_view():
    options = sorted(scored.index.tolist())
    initialize_comparison_tickers(
        st.session_state,
        scored,
        current_ticker=st.session_state.drill_ticker,
    )

    _md(
        f"""
        <section class="section" id="comparison-view">
          <div class="section-head">
            <h2>Comparison view <span class="count">2-4 tickers</span></h2>
            <div class="right">{len(scored)} scored tickers</div>
          </div>
        </section>
        """
    )
    _md('<div class="comparison-selector-slot"></div>')
    st.multiselect("COMPARE TICKERS",
        options,
        max_selections=4,
        key="comparison_tickers",
    )
    selected_compare = list(st.session_state.comparison_tickers)[:4]
    rows = comparison_card_rows(scored, selected_compare)
    if len(rows) < 2:
        st.info("Select at least two scored tickers to compare them side by side.")
        return

    cards = ""
    for row in rows:
        state = row["state"]
        ticker_name = _ticker_identity_subtext(row["ticker"])
        cards += f"""
        <div class="comparison-card {state}">
          <div class="comparison-head">
            <div>
              <div class="comparison-ticker">{_esc(row['ticker'])}<span class="ticker-name">{_esc(ticker_name)}</span></div>
              <div class="comparison-class">{_esc(row['class'])}</div>
            </div>
            <span class="state">{_esc(state.replace('_', ' '))}</span>
          </div>
          <div class="comparison-metrics">
            <div><span>S</span><b>{_esc(row['s_score'])}</b></div>
            <div><span>F</span><b>{_esc(row['f_score'])}</b></div>
            <div><span>MOM</span><b>{_esc(row['momentum'])}</b></div>
            <div><span>STAGE</span><b>{_esc(row['stage'])}</b></div>
            <div><span>RRG</span><b>{_esc(row['rrg'])}</b></div>
            <div><span>RANK</span><b>{_esc(row['rank'])}</b></div>
          </div>
          <div class="comparison-flags">
            <span>{_esc(row['selected'])}</span>
            <span>{_esc(row['veto'])}</span>
          </div>
        </div>
        """
    _md(f'<div class="comparison-grid">{cards}</div>')


def _full_table_sort_header(label: str, field: str, active_field: str, active_direction: str, tip: str = "") -> str:
    classes = "tip-cue sort-label" if tip else "sort-label"
    if field == active_field:
        classes += " sort-active"
        arrow = "&darr;" if active_direction == "desc" else "&uarr;"
        arrow_html = f'<span class="sort-arrow">{arrow}</span>'
    else:
        arrow_html = ""
    tip_attr = f' data-tip="{_esc(tip)}"' if tip else ""
    return f'<span class="{classes}"{tip_attr}>{_esc(label)}{arrow_html}</span>'


def render_full_table():
    toggle_col, field_col, direction_col, status_col = st.columns([2, 3, 2, 3])
    with toggle_col:
        if st.button(("HIDE" if st.session_state.table_open else "SHOW") + " FULL 7-PILLAR MATRIX",
                     key="table_toggle"):
            st.session_state.table_open = not st.session_state.table_open
            st.rerun()

    if not st.session_state.table_open:
        return

    sort_fields = list(FULL_TABLE_SORT_FIELDS.keys())
    sort_directions = list(FULL_TABLE_SORT_DIRECTIONS.keys())
    current_field, current_direction = normalize_full_table_sort(
        st.session_state.table_sort_field_choice,
        st.session_state.table_sort_direction_choice,
    )
    with field_col:
        selected_field = st.selectbox("Sort field",
            options=sort_fields,
            format_func=lambda key: FULL_TABLE_SORT_FIELDS[key],
            index=sort_fields.index(current_field),
            key="table_sort_field_choice",
        )
    with direction_col:
        selected_direction = st.segmented_control("Direction",
            options=sort_directions,
            format_func=lambda key: FULL_TABLE_SORT_DIRECTIONS[key],
            key="table_sort_direction_choice",
        )
    selected_field, selected_direction = normalize_full_table_sort(selected_field, selected_direction)
    st.session_state.table_sort_field = selected_field
    st.session_state.table_sort_direction = selected_direction
    st.session_state.table_sort = f"{selected_field}:{selected_direction}"
    with status_col:
        _md(
            f"""
            <div class="matrix-sort-summary">
              Sorted by <b>{_esc(FULL_TABLE_SORT_FIELDS[selected_field])}</b>
              <span>{_esc(FULL_TABLE_SORT_DIRECTIONS[selected_direction])}</span>
            </div>
            """
        )

    scored_sorted = sort_full_table_frame(scored, selected_field, selected_direction)

    rows_html = ""
    # 7 pillar booleans:
    # 1. mom_12_1 > 0
    # 2. faber == 1
    # 3. stage == 2 (Weinstein)
    # 4. antonacci == 1
    # 5. rrg_quadrant in {Leading, Improving}
    # 6. (cycle tilt - derive from class match, approximate) just use breadth > 50%
    # 7. F_score > 0 (institutional flow)

    for tkr, r in scored_sorted.iterrows():
        p1 = (r.get("mom_12_1") or 0) > 0
        p2 = (r.get("faber") or 0) == 1
        p3 = (r.get("stage") or 0) == 2
        p4 = (r.get("antonacci") or 0) == 1
        p5 = (r.get("rrg_quadrant") in ("Leading", "Improving"))
        p6 = (r.get("breadth_50d") or 0) >= 0.5
        p7 = (r.get("F_score") or 0) > 0
        pillars = [p1, p2, p3, p4, p5, p6, p7]

        s = r["S_score"]
        f = r["F_score"]
        mom = (r.get("mom_12_1") or 0) * 100
        state = r["state"]
        preview_html = table_row_rrg_preview_html(tkr, r)
        ticker_name = _ticker_identity_subtext(tkr)
        state_tip = _state_tip_for_row(tkr, r)

        p_tds = "".join(
            f'<td class="num"><span class="dot {"ok" if ok else "bad"}">{"Y" if ok else "N"}</span></td>'
            for ok in pillars
        )

        rows_html += f"""
        <tr>
          <td class="t table-ticker">{_esc(tkr)}<small>{_esc(ticker_name)}</small>{preview_html}</td>
          <td style="color:var(--muted)">{r['class']}</td>
          <td><span class="pill {state}" data-tip="{_esc(state_tip)}">{state.replace('_', ' ')}</span></td>
          {p_tds}
          <td class="num {'pos' if s >= 0 else 'neg'}">{s:+.2f}</td>
          <td class="num {'pos' if f >= 0 else 'neg'}">{f:+.2f}</td>
          <td class="num {'pos' if mom >= 0 else 'neg'}">{mom:+.1f}%</td>
        </tr>
        """

    pillars_th = "".join(
        f'<th class="num">{_full_table_sort_header(p, field, selected_field, selected_direction, INDICATOR_TIPS[k])}</th>' for p, field, k in
        [("MOM","mom_12_1","tip_MOM"),("FABER","faber","tip_col_FABER"),("STAGE2","stage","tip_col_STAGE2"),("ANT","antonacci","tip_col_ANT"),("RRG","rrg_quadrant","tip_RRG"),("BREADTH","breadth_50d","tip_col_BREADTH"),("FLOW","F_score","tip_col_FLOW")]
    )

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Full 7-pillar matrix <span class="count">{len(scored)} of {len(SCORED_TICKERS)} instruments</span></h2>
      </div>
      <div class="full-table">
        <table>
          <thead>
            <tr>
              <th>{_full_table_sort_header("Ticker", "ticker", selected_field, selected_direction)}</th>
              <th>{_full_table_sort_header("Class", "class", selected_field, selected_direction)}</th>
              <th>{_full_table_sort_header("State", "state", selected_field, selected_direction)}</th>
              {pillars_th}
              <th class="num">{_full_table_sort_header("S", "S_score", selected_field, selected_direction, INDICATOR_TIPS['tip_S'])}</th>
              <th class="num">{_full_table_sort_header("F", "F_score", selected_field, selected_direction, INDICATOR_TIPS['tip_F'])}</th>
              <th class="num">{_full_table_sort_header("MOM", "mom_12_1", selected_field, selected_direction, INDICATOR_TIPS['tip_MOM'])}</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </section>
    """
    _md(html)


def _portfolio_result_from_upload(uploaded_file):
    payload = uploaded_file.getvalue()
    filename = (uploaded_file.name or "").lower()
    if filename.endswith(".csv"):
        return parse_holdings_csv(payload)
    if filename.endswith((".xlsx", ".xls")):
        return parse_holdings_excel(payload)
    return parse_holdings_csv(payload)


def _saved_items(kind: str):
    return [item for item in load_saved_inputs(SAVED_INPUTS_PATH) if item.kind == kind]


def _find_saved_item(kind: str, name: str | None):
    if not name:
        return None
    for item in _saved_items(kind):
        if item.name.casefold() == str(name).casefold():
            return item
    return None


def _show_save_result(result) -> None:
    if result.ok:
        st.success(result.message)
    else:
        st.warning(result.message)


def _render_saved_input_controls(kind: str, label: str, loaded_key: str):
    items = _saved_items(kind)
    if not items:
        return None
    names = [""] + [item.name for item in items]
    selected = st.selectbox(f"Saved {label.lower()}", names, key=f"saved_{kind}_select")
    load_label = LOAD_WATCHLIST_LABEL if kind == "watchlist" else LOAD_PORTFOLIO_LABEL
    delete_label = DELETE_WATCHLIST_LABEL if kind == "watchlist" else DELETE_PORTFOLIO_LABEL
    c1, c2 = st.columns(2)
    with c1:
        if selected and st.button(load_label, key=f"load_saved_{kind}"):
            st.session_state[loaded_key] = selected
            loaded = _find_saved_item(kind, selected)
            if kind == "watchlist" and loaded is not None:
                st.session_state.custom_universe_mode = "Paste tickers"
                st.session_state.custom_universe_text = " ".join(loaded.tickers)
            st.rerun()
    with c2:
        if selected and st.button(delete_label, key=f"delete_saved_{kind}"):
            delete_saved_input(kind, selected, SAVED_INPUTS_PATH)
            st.session_state[loaded_key] = ""
            st.rerun()
    return _find_saved_item(kind, st.session_state.get(loaded_key))


def _render_save_portfolio_controls(result, default_name: str = "") -> None:
    if not result.holdings:
        return
    name = st.text_input("Save portfolio as", value=default_name, key="save_portfolio_name")
    if st.button(SAVE_PORTFOLIO_LABEL, key="save_portfolio_btn"):
        _show_save_result(save_portfolio(name, result.holdings, SAVED_INPUTS_PATH))


def _render_save_watchlist_controls(result, default_name: str = "") -> None:
    if not result.tickers:
        return
    name = st.text_input("Save watchlist as", value=default_name, key="save_watchlist_name")
    if st.button(SAVE_WATCHLIST_LABEL, key="save_watchlist_btn"):
        _show_save_result(save_watchlist(name, result.tickers, SAVED_INPUTS_PATH))


def _render_portfolio_analysis(result):
    for error in result.errors:
        prefix = f"Row {error.row_number}: " if error.row_number is not None else ""
        suffix = f" ({error.column})" if error.column else ""
        st.warning(f"{prefix}{error.message}{suffix}")

    if not result.holdings:
        return

    try:
        _, analysis, ad_hoc_result = _analysis_scored_frame_for_result(result)
    except ValueError as exc:
        st.error(str(exc))
        return

    _render_ad_hoc_status(ad_hoc_result)
    if analysis.missing_tickers:
        st.warning("Could not analyze because market data was unavailable: " + ", ".join(analysis.missing_tickers))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.dataframe(exposure_frame(analysis.state_exposure, "State"), hide_index=True, width="stretch")
    with c2:
        st.dataframe(exposure_frame(analysis.class_exposure, "Class"), hide_index=True, width="stretch")
    with c3:
        actions = analysis.action_tickers
        _md(
            f"""
            <div class="portfolio-actions">
              <div class="pa-row exit"><span>EXIT</span><b>{_esc(', '.join(actions['exit']) or '-')}</b></div>
              <div class="pa-row warn"><span>WARNING</span><b>{_esc(', '.join(actions['warning']) or '-')}</b></div>
              <div class="pa-row buy"><span>BULLISH</span><b>{_esc(', '.join(actions['bullish']) or '-')}</b></div>
            </div>
            """
        )

    st.dataframe(analysis_rows_frame(analysis), hide_index=True, width="stretch")

    pnl = analyze_position_pnl(result.holdings, latest_prices_from_ohlcv(ohlcv))
    if not pnl.rows:
        return
    with st.expander("P&L tracker", expanded=False):
        if pnl.missing_tickers:
            st.caption("P&L inputs missing for: " + ", ".join(pnl.missing_tickers))
        st.dataframe(pnl_summary_frame(pnl), hide_index=True, width="stretch")
        st.dataframe(pnl_rows_frame(pnl), hide_index=True, width="stretch")


def render_portfolio_analyzer():
    if st.session_state.portfolio_single_source != st.session_state.drill_ticker:
        st.session_state.portfolio_single_ticker = st.session_state.drill_ticker
        st.session_state.portfolio_single_submitted_ticker = st.session_state.drill_ticker
        st.session_state.portfolio_single_source = st.session_state.drill_ticker

    _md(
        f"""
        <section class="section" id="portfolio-analyzer">
          <div class="section-head">
            <h2>Portfolio analyzer <span class="count">Positions and tickers</span></h2>
            <div class="right">{len(scored)} scored tickers</div>
          </div>
        </section>
        """
    )

    loaded = _render_saved_input_controls("portfolio", "PORTFOLIO", "loaded_portfolio_name")
    if loaded is not None:
        st.caption(f"Loaded portfolio: {loaded.name}")
        _render_portfolio_analysis(PortfolioInputResult(holdings=loaded.holdings, errors=[]))

    mode = st.radio(
        "Analyzer input",
        ["Ticker", "Portfolio"],
        horizontal=True,
        label_visibility="collapsed",
        key="portfolio_analyzer_mode",
    )

    if mode == "Ticker":
        with st.form("portfolio_single_ticker_form", clear_on_submit=False):
            input_col, action_col = st.columns([3, 1])
            with input_col:
                ticker = st.text_input(
                    "Ticker",
                    key="portfolio_single_ticker",
                    placeholder="XLK",
                )
            with action_col:
                _md('<div class="form-action-spacer"></div>')
                submitted = st.form_submit_button("ANALYZE TICKER", type="primary", width="stretch")
        if submitted:
            st.session_state.portfolio_single_submitted_ticker = ticker

        submitted_ticker = st.session_state.get("portfolio_single_submitted_ticker", ticker)
        if submitted_ticker:
            result = parse_single_ticker(submitted_ticker)
            _render_portfolio_analysis(result)
            _render_save_portfolio_controls(result, default_name=submitted_ticker.upper())
        return

    uploaded = st.file_uploader(
        "Portfolio file",
        type=["csv", "xlsx", "xls"],
        key="portfolio_upload",
    )
    if uploaded is not None:
        result = _portfolio_result_from_upload(uploaded)
        _render_portfolio_analysis(result)
        default_name = Path(uploaded.name or "portfolio").stem
        _render_save_portfolio_controls(result, default_name=default_name)


def _custom_universe_result_from_upload(uploaded_file):
    return parse_custom_universe_file(uploaded_file.getvalue(), uploaded_file.name or "")


def _custom_universe_scored_frame_for_result(result):
    analysis = analyze_custom_universe(result.tickers, scored)
    ad_hoc_result = None
    if not analysis.missing_tickers:
        return scored, analysis, ad_hoc_result

    missing = tuple(sorted(set(analysis.missing_tickers)))
    refresh_token = st.session_state.get("data_refresh_token")
    ohlcv_result = _load_ad_hoc_data(missing, period="3y", refresh_token=refresh_token)
    ad_hoc_ohlcv = {**ohlcv, **ohlcv_result.data}
    ad_hoc_result = score_ad_hoc_tickers(
        missing,
        ad_hoc_ohlcv,
        phase=regime.phase_hint,
        bench_ticker=BENCH["US"],
        bil_ticker=BENCH["TBILL"],
    )
    if ad_hoc_result.scored.empty:
        return scored, analysis, ad_hoc_result

    analysis_scored = pd.concat([scored, ad_hoc_result.scored], axis=0)
    return analysis_scored, analyze_custom_universe(result.tickers, analysis_scored), ad_hoc_result


def _render_custom_universe_analysis(result):
    for error in result.errors:
        prefix = f"Row {error.row_number}: " if error.row_number is not None else ""
        suffix = f" ({error.column})" if error.column else ""
        token = f": {error.token}" if error.token else ""
        st.warning(f"{prefix}{error.message}{token}{suffix}")

    if result.duplicate_tickers:
        st.warning("Duplicate tickers ignored: " + ", ".join(result.duplicate_tickers))

    if not result.tickers:
        return

    try:
        _, analysis, ad_hoc_result = _custom_universe_scored_frame_for_result(result)
    except ValueError as exc:
        st.error(str(exc))
        return

    _render_ad_hoc_status(ad_hoc_result)
    if analysis.missing_tickers:
        st.warning("Could not analyze because market data was unavailable: " + ", ".join(analysis.missing_tickers))

    _md(
        f"""
        <div class="custom-universe-summary">
          <div><span>AVAILABLE</span><b>{len(analysis.available_tickers)}</b></div>
          <div><span>MISSING</span><b>{len(analysis.missing_tickers)}</b></div>
          <div><span>INPUT</span><b>{len(result.tickers)}</b></div>
        </div>
        """
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.dataframe(summary_counts_frame(analysis.class_counts, "Class"), hide_index=True, width="stretch")
    with c2:
        st.dataframe(summary_counts_frame(analysis.state_counts, "State"), hide_index=True, width="stretch")
    with c3:
        actions = analysis.action_tickers
        _md(
            f"""
            <div class="portfolio-actions">
              <div class="pa-row exit"><span>EXIT</span><b>{_esc(', '.join(actions['exit']) or '-')}</b></div>
              <div class="pa-row warn"><span>WARNING</span><b>{_esc(', '.join(actions['warning']) or '-')}</b></div>
              <div class="pa-row buy"><span>BULLISH</span><b>{_esc(', '.join(actions['bullish']) or '-')}</b></div>
            </div>
            """
        )

    st.dataframe(custom_universe_rows_frame(analysis), hide_index=True, width="stretch")
    _render_drill_selector("custom_universe_drill", analysis.available_tickers[:8], "DRILL-DOWN FROM CUSTOM UNIVERSE")


def render_custom_universe_builder():
    _md(
        f"""
        <section class="section" id="custom-universe-builder">
          <div class="section-head">
            <h2>Custom universe <span class="count">Watchlist builder</span></h2>
            <div class="right">{len(scored)} scored tickers</div>
          </div>
        </section>
        """
    )

    loaded = _render_saved_input_controls("watchlist", "WATCHLIST", "loaded_watchlist_name")
    if loaded is not None:
        st.caption(f"Loaded watchlist: {loaded.name}")
        _render_custom_universe_analysis(parse_custom_universe_text(" ".join(loaded.tickers)))

    mode = st.radio(
        "Custom universe input",
        ["Paste tickers", "Upload file"],
        horizontal=True,
        label_visibility="collapsed",
        key="custom_universe_mode",
    )

    if mode == "Paste tickers":
        with st.form("custom_universe_paste_form", clear_on_submit=False):
            tickers = st.text_area(
                "Custom tickers",
                key="custom_universe_text",
                placeholder="XLK XLF SOXX NVDA",
                height=90,
            )
            submitted = st.form_submit_button("ANALYZE CUSTOM TICKERS", type="primary", width="stretch")
        if submitted:
            st.session_state.custom_universe_submitted_text = tickers
        submitted_text = st.session_state.get("custom_universe_submitted_text", "") or tickers
        if submitted_text:
            result = parse_custom_universe_text(submitted_text)
            _render_custom_universe_analysis(result)
            _render_save_watchlist_controls(result)
        return

    uploaded = st.file_uploader(
        "Custom universe file",
        type=["csv", "xlsx", "xls"],
        key="custom_universe_upload",
    )
    if uploaded is not None:
        result = _custom_universe_result_from_upload(uploaded)
        _render_custom_universe_analysis(result)
        default_name = Path(uploaded.name or "watchlist").stem
        _render_save_watchlist_controls(result, default_name=default_name)


def _load_backtest_metadata():
    if not BACKTEST_METADATA_PATH.exists():
        return None
    try:
        return json.loads(BACKTEST_METADATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _artifact_hash_matches(path: Path, expected_hash: str | None) -> bool:
    if not path.exists() or not expected_hash:
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected_hash


def _load_backtest_states(metadata):
    if not metadata:
        return None
    if not _artifact_hash_matches(BACKTEST_STATES_PATH, metadata.get("states_sha256")):
        return None
    try:
        return pd.read_csv(BACKTEST_STATES_PATH, index_col=0, parse_dates=True)
    except Exception:
        return None


def _read_csv_artifact(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def render_calibration_lab():
    _md(
        """
        <section class="section" id="calibration-lab">
          <div class="section-head">
            <h2>Calibration lab <span class="count">Research artifacts</span></h2>
            <div class="right">RESEARCH EVIDENCE</div>
          </div>
        </section>
        """
    )

    metadata = _load_backtest_metadata() or {}
    calibration_metadata = {}
    if CALIBRATION_METADATA_PATH.exists():
        try:
            calibration_metadata = json.loads(CALIBRATION_METADATA_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            st.warning(f"Could not read calibration metadata artifact: {exc}")

    baseline_hash = metadata.get("baseline_config_artifact_sha256") or calibration_metadata.get(
        "baseline_config_artifact_sha256"
    )
    report_hash = metadata.get("calibration_10y_report_sha256") or calibration_metadata.get(
        "report_sha256"
    )
    summary_hash = metadata.get("calibration_10y_summary_sha256") or calibration_metadata.get(
        "summary_sha256"
    )
    candidates_hash = metadata.get(
        "calibration_10y_candidates_sha256"
    ) or calibration_metadata.get("candidates_sha256")
    candidate_config_hash = shared_artifact_hash(
        metadata.get("calibration_10y_candidate_config_sha256"),
        calibration_metadata.get("candidate_config_sha256"),
    )
    metadata_hash = metadata.get("calibration_10y_metadata_sha256")
    baseline_config_exists = CALIBRATION_BASELINE_CONFIG_PATH.exists()
    status_rows = calibration_artifact_status_rows(
        baseline_config_path=CALIBRATION_BASELINE_CONFIG_PATH,
        report_path=CALIBRATION_REPORT_PATH,
        summary_path=CALIBRATION_SUMMARY_PATH,
        candidates_path=CALIBRATION_CANDIDATES_PATH,
        candidate_config_path=CALIBRATION_CANDIDATE_CONFIG_PATH,
        metadata_path=CALIBRATION_METADATA_PATH,
        baseline_hash=baseline_hash,
        report_hash=report_hash,
        summary_hash=summary_hash,
        candidates_hash=candidates_hash,
        candidate_config_hash=candidate_config_hash,
        metadata_hash=metadata_hash,
    )
    baseline_status = status_rows[0]["Status"]
    baseline_verified = baseline_status == "VERIFIED"
    candidate_status = status_rows[3]["Status"]
    candidate_config_status = status_rows[4]["Status"]
    metadata_status = status_rows[5]["Status"]
    candidate_artifact_verified = candidate_status == "VERIFIED" and metadata_status == "VERIFIED"
    candidate_config_verified = (
        candidate_config_status == "VERIFIED" and metadata_status == "VERIFIED"
    )
    split_summary = metadata.get("calibration_split_summary") or calibration_metadata.get(
        "calibration_split_summary"
    )

    st.dataframe(pd.DataFrame(status_rows), hide_index=True, width="stretch")

    if split_summary:
        split_status = str(split_summary.get("status", "unknown"))
        requested_years = str(split_summary.get("requested_years", 10))
        minimum_accepted_years = str(split_summary.get("minimum_accepted_years", "n/a"))
        effective_calibration_years = str(
            split_summary.get("effective_calibration_years", "n/a")
        )
        coverage_years = str(split_summary.get("coverage_years", "n/a"))
        history_window_status = str(split_summary.get("history_window_status", "unknown"))
        history_window_reason = str(split_summary.get("history_window_reason") or "")
        reason_line = (
            f"<br />Reason: {_esc(history_window_reason)}."
            if history_window_reason
            else ""
        )
        _md(
            f"""
            <div class="chart-help">
              <b>Walk-forward split status:</b>
              <code>{_esc(split_status)}</code>.
              Requested window: <code>{_esc(requested_years)}</code> years.
              Minimum accepted: <code>{_esc(minimum_accepted_years)}</code> years.
              Effective calibration: <code>{_esc(effective_calibration_years)}</code> years.
              Coverage used: <code>{_esc(coverage_years)}</code> years.
              History window: <code>{_esc(history_window_status)}</code>.
              {reason_line}
            </div>
            """
        )
    else:
        _md(
            """
            <div class="chart-help">
              Walk-forward split metadata will appear here after the manual runner writes
              calibration metadata. The dashboard does not run calibration on page load.
            </div>
            """
        )

    if baseline_config_exists:
        if not baseline_verified:
            _md(
                """
                <div class="chart-help">
                  <b>Hash status:</b> <code>UNVERIFIED</code>.
                  The frozen baseline config file exists and is shown below, but the current
                  metadata does not contain a matching hash for this artifact.
                </div>
                """
            )
        with st.expander("Frozen baseline config", expanded=False):
            try:
                st.json(json.loads(CALIBRATION_BASELINE_CONFIG_PATH.read_text(encoding="utf-8")))
            except Exception as exc:
                st.warning(f"Could not read frozen baseline config artifact: {exc}")
    else:
        _md(
            """
            <div class="chart-help">
              Frozen baseline config pending. Run <code>python scripts/run_backtest.py</code>
              to refresh the baseline artifact before calibration.
            </div>
            """
        )

    if CALIBRATION_REPORT_PATH.exists():
        with st.expander("Calibration report", expanded=False):
            st.markdown(CALIBRATION_REPORT_PATH.read_text(encoding="utf-8"))
    else:
        _md(
            """
            <div class="chart-help">
              Full calibration report pending. A manual research run will generate
              <code>docs/calibration_10y_report.md</code> after baseline and calibrated
              out-of-sample runs are complete.
            </div>
            """
        )

    summary = _read_csv_artifact(CALIBRATION_SUMMARY_PATH)
    if not summary.empty:
        st.dataframe(summary, hide_index=True, width="stretch")

    candidates = (
        _read_csv_artifact(CALIBRATION_CANDIDATES_PATH)
        if candidate_artifact_verified
        else pd.DataFrame()
    )
    if not candidates.empty and candidate_artifact_verified:
        with st.expander("Calibration candidates", expanded=False):
            st.dataframe(candidates, hide_index=True, width="stretch")
    elif CALIBRATION_CANDIDATES_PATH.exists() and candidate_status == "UNVERIFIED":
        _md(
            """
            <div class="chart-help">
              Calibration candidate artifact hash is <code>UNVERIFIED</code>.
              Run <code>python scripts/run_backtest.py</code> to refresh candidate evidence.
            </div>
            """
        )

    if candidate_config_verified:
        with st.expander("Calibrated candidate config", expanded=False):
            try:
                st.json(json.loads(CALIBRATION_CANDIDATE_CONFIG_PATH.read_text(encoding="utf-8")))
            except Exception as exc:
                st.warning(f"Could not read calibrated candidate config artifact: {exc}")
    elif CALIBRATION_CANDIDATE_CONFIG_PATH.exists() and candidate_config_status == "UNVERIFIED":
        _md(
            """
            <div class="chart-help">
              Calibrated candidate config artifact hash is <code>UNVERIFIED</code>.
              Run <code>python scripts/run_backtest.py</code> to refresh calibrated rerun gate evidence.
            </div>
            """
        )

    expanded_metadata = {}
    if CALIBRATION_EXPANDED_METADATA_PATH.exists():
        try:
            expanded_metadata = json.loads(
                CALIBRATION_EXPANDED_METADATA_PATH.read_text(encoding="utf-8")
            )
        except Exception as exc:
            st.warning(f"Could not read expanded calibration metadata artifact: {exc}")
    expanded_artifact_hashes = expanded_metadata.get("artifacts", {})
    expanded_metadata_hash = metadata.get("calibration_expanded_metadata_sha256")
    expanded_status_rows = expanded_calibration_artifact_status_rows(
        report_path=CALIBRATION_EXPANDED_REPORT_PATH,
        candidates_path=CALIBRATION_EXPANDED_CANDIDATES_PATH,
        sector_overrides_path=CALIBRATION_SECTOR_OVERRIDES_PATH,
        metadata_path=CALIBRATION_EXPANDED_METADATA_PATH,
        report_hash=expanded_artifact_hashes.get("report_sha256"),
        candidates_hash=expanded_artifact_hashes.get("candidates_sha256"),
        sector_overrides_hash=expanded_artifact_hashes.get("sector_overrides_sha256"),
        metadata_hash=expanded_metadata_hash,
    )
    _md(
        """
        <div class="chart-help">
          <b>Expanded calibration:</b> Research-only threshold, filter, and
          sector-specific rule evidence. These artifacts do not change live scoring.
        </div>
        """
    )
    st.dataframe(pd.DataFrame(expanded_status_rows), hide_index=True, width="stretch")
    expanded_report_status = expanded_status_rows[0]["Status"]
    expanded_candidates_status = expanded_status_rows[1]["Status"]
    sector_overrides_status = expanded_status_rows[2]["Status"]
    expanded_metadata_status = expanded_status_rows[3]["Status"]
    expanded_report_verified = (
        expanded_report_status == "VERIFIED" and expanded_metadata_status == "VERIFIED"
    )
    expanded_candidates_verified = (
        expanded_candidates_status == "VERIFIED" and expanded_metadata_status == "VERIFIED"
    )
    sector_overrides_verified = (
        sector_overrides_status == "VERIFIED" and expanded_metadata_status == "VERIFIED"
    )

    if CALIBRATION_EXPANDED_REPORT_PATH.exists():
        if not expanded_report_verified:
            _md(
                """
                <div class="chart-help">
                  Expanded calibration report or metadata hash is <code>UNVERIFIED</code>.
                  Run the offline backtest refresh command to update expanded evidence.
                </div>
                """
            )
        if expanded_report_status == "VERIFIED" and expanded_metadata_status == "VERIFIED":
            with st.expander("Expanded calibration report", expanded=False):
                st.markdown(CALIBRATION_EXPANDED_REPORT_PATH.read_text(encoding="utf-8"))

    expanded_candidates = (
        _read_csv_artifact(CALIBRATION_EXPANDED_CANDIDATES_PATH)
        if expanded_candidates_verified
        else pd.DataFrame()
    )
    if not expanded_candidates.empty:
        with st.expander("Expanded calibration candidates", expanded=False):
            st.dataframe(expanded_candidates, hide_index=True, width="stretch")
    elif CALIBRATION_EXPANDED_CANDIDATES_PATH.exists() and expanded_candidates_status == "UNVERIFIED":
        _md(
            """
            <div class="chart-help">
              Expanded calibration candidate artifact hash is <code>UNVERIFIED</code>.
              Run the offline backtest refresh command to update expanded evidence.
            </div>
            """
        )

    sector_overrides = (
        _read_csv_artifact(CALIBRATION_SECTOR_OVERRIDES_PATH)
        if sector_overrides_verified
        else pd.DataFrame()
    )
    if not sector_overrides.empty:
        with st.expander("Sector-specific research overrides", expanded=False):
            st.dataframe(sector_overrides, hide_index=True, width="stretch")
    elif CALIBRATION_SECTOR_OVERRIDES_PATH.exists() and sector_overrides_status == "UNVERIFIED":
        _md(
            """
            <div class="chart-help">
              Sector-specific override artifact hash is <code>UNVERIFIED</code>.
              Run the offline backtest refresh command to update expanded evidence.
            </div>
            """
        )


def _read_validation_summary(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def render_evidence_gate_lab():
    _md(
        """
        <section class="section" id="evidence-gate-lab">
          <div class="section-head">
            <h2>Evidence gates <span class="count">Macro and provider research</span></h2>
            <div class="right">FAIL-CLOSED RESEARCH</div>
          </div>
        </section>
        """
    )

    fred_decision = evaluate_promotion_gate(
        ticket="Macro evidence gate",
        source="FRED macro",
        summary=_read_validation_summary(FRED_VALIDATION_SUMMARY_PATH),
        validation_report_path="docs/fred_macro_validation_report.md",
    )
    massive_decision = evaluate_promotion_gate(
        ticket="Provider evidence gate",
        source="Massive provider data",
        summary=_read_validation_summary(MASSIVE_VALIDATION_SUMMARY_PATH),
        validation_report_path="docs/massive_provider_validation_report.md",
    )
    decisions = [fred_decision, massive_decision]
    gate_rows = promotion_gate_decisions_frame(decisions)
    gate_rows = gate_rows.rename(columns={"Ticket": "Gate"})
    live_promotion_allowed = any(decision.live_promotion_allowed for decision in decisions)

    _md(
        f"""
        <div class="chart-help">
          <b>Live promotion allowed:</b> <code>{_esc(str(live_promotion_allowed))}</code>.
          These gates surface validation status only; any promoted rule still requires
          a separate reviewed patch and rollback plan.
        </div>
        """
    )
    st.dataframe(gate_rows, hide_index=True, width="stretch")

    if EVIDENCE_GATE_REPORT_PATH.exists():
        with st.expander("Evidence gate report", expanded=False):
            st.markdown(EVIDENCE_GATE_REPORT_PATH.read_text(encoding="utf-8"))
    else:
        _md(
            """
            <div class="chart-help">
              Evidence gate report pending. Run
              <code>python scripts/evaluate_evidence_gates.py</code> from the repo root
              after validation summaries are refreshed.
            </div>
            """
        )


def _render_backtest_lab_content():
    _md(
        """
        <section class="section" id="backtest-lab">
          <div class="section-head">
            <h2>Backtest lab <span class="count">Manual artifacts</span></h2>
            <div class="right">OFFLINE REPORT VIEWER</div>
          </div>
        </section>
        """
    )

    metadata = _load_backtest_metadata()
    report_ready = bool(
        metadata
        and _artifact_hash_matches(BACKTEST_REPORT_PATH, metadata.get("report_sha256"))
    )
    equity_ready = bool(
        metadata
        and _artifact_hash_matches(BACKTEST_EQUITY_PATH, metadata.get("equity_sha256"))
    )

    if metadata:
        generated_at = metadata.get("generated_at_utc", "unknown")
        _md(f'<div class="chart-help"><b>Artifact set:</b> generated at <code>{_esc(str(generated_at))}</code>.</div>')

    if report_ready:
        st.markdown("#### Manual backtest report")
        st.markdown(BACKTEST_REPORT_PATH.read_text(encoding="utf-8"))
    else:
        _md(
            """
            <div class="chart-help">
              <b>No backtest report artifact found.</b>
              Run <code>python scripts/run_backtest.py</code> from the repo root to generate
              <code>docs/backtest_report.md</code> and <code>docs/backtest_equity.csv</code>.
              The app never runs the backtest automatically on page load.
            </div>
            """
        )

    if equity_ready:
        try:
            equity = pd.read_csv(BACKTEST_EQUITY_PATH, index_col="date", parse_dates=True)
        except Exception as exc:
            st.warning(f"Could not read backtest equity artifact: {exc}")
            return
        if equity.empty:
            st.warning("Backtest equity artifact is empty.")
            return
        _md(
            """
            <div class="chart-help">
              <b>Normalized equity.</b> Each series starts at 1.0 so the methodology
              and benchmarks can be compared on the same base.
            </div>
            """
        )
        st.line_chart(normalized_equity_frame(equity), width="stretch")
        _md(
            """
            <div class="chart-help">
              <b>Drawdown.</b> Percent below each series running high; lower readings
              show the depth of the underwater period.
            </div>
            """
        )
        st.line_chart(drawdown_frame(equity), width="stretch")
    else:
        _md(
            """
            <div class="chart-help">
              Equity chart unavailable until <code>docs/backtest_equity.csv</code> is generated.
            </div>
            """
        )


def render_backtest_lab():
    with st.expander("Backtest lab", expanded=False):
        _render_backtest_lab_content()


def _trade_result_from_upload(uploaded_file):
    payload = uploaded_file.getvalue()
    filename = (uploaded_file.name or "").lower()
    if filename.endswith(".csv"):
        return parse_trade_history_csv(payload)
    if filename.endswith((".xlsx", ".xls")):
        return parse_trade_history_excel(payload)
    return parse_trade_history_csv(payload)


def _render_trade_input_errors(result: TradeInputResult) -> None:
    for error in result.errors:
        prefix = f"Row {error.row_number}: " if error.row_number is not None else ""
        suffix = f" ({error.column})" if error.column else ""
        st.warning(f"{prefix}{error.message}{suffix}")


def _render_personal_trade_backtest_content():
    _md(
        """
        <section class="section" id="personal-trade-backtest">
          <div class="section-head">
            <h2>Personal trade backtest <span class="count">Trade history</span></h2>
            <div class="right">OFFLINE ALIGNMENT</div>
          </div>
        </section>
        """
    )

    metadata = _load_backtest_metadata()
    states = _load_backtest_states(metadata)
    if states is None:
        _md(
            """
            <div class="chart-help">
              <b>Methodology-state artifact unavailable.</b>
              Run <code>python scripts/run_backtest.py</code> to generate
              <code>docs/backtest_states.csv</code>; uploaded trades are not sent anywhere.
            </div>
            """
        )
        return

    uploaded = st.file_uploader(
        "Trade history file",
        type=["csv", "xlsx", "xls"],
        key="personal_trade_history_upload",
    )
    if uploaded is None:
        _md(
            """
            <div class="chart-help">
              Upload a trade-history CSV/XLS/XLSX with date, ticker, side, shares, and price columns.
              The comparison uses the latest historical methodology state at or before each trade date.
            </div>
            """
        )
        return

    result = _trade_result_from_upload(uploaded)
    _render_trade_input_errors(result)
    if not result.trades:
        return
    trade_backtest = evaluate_trade_history(result.trades, states)
    st.dataframe(trade_alignment_summary_frame(trade_backtest), hide_index=True, width="stretch")
    st.dataframe(trade_alignment_frame(trade_backtest), hide_index=True, width="stretch")


def render_personal_trade_backtest():
    with st.expander("Personal trade backtest", expanded=False):
        _render_personal_trade_backtest_content()


def _debrief_summary_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    rename = {
        "action": "Action",
        "horizon": "Horizon",
        "decision_count": "Decisions",
        "available_count": "Matured",
        "hit_rate": "Hit Rate",
        "average_forward_return": "Avg Forward Return",
    }
    frame = frame.rename(columns=rename)
    for column in ["Hit Rate", "Avg Forward Return"]:
        if column in frame:
            frame[column] = frame[column].map(lambda value: "-" if pd.isna(value) else f"{float(value) * 100:.1f}%")
    return frame


def _debrief_candidate_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    rename = {
        "run_id": "Run",
        "ticker": "Ticker",
        "action": "Action",
        "horizon": "Horizon",
        "forward_return": "Forward Return",
        "state": "State",
        "s_score": "S",
        "f_score": "F",
        "rationale": "Rationale",
    }
    frame = frame.rename(columns=rename)
    if "Forward Return" in frame:
        frame["Forward Return"] = frame["Forward Return"].map(lambda value: f"{float(value) * 100:.1f}%")
    return frame


def _debrief_macro_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    rename = {
        "macro_group": "Macro Group",
        "macro_label": "Macro",
        "macro_series": "Series",
        "macro_condition": "Condition",
        "action": "Action",
        "horizon": "Horizon",
        "decision_count": "Decisions",
        "available_count": "Matured",
        "hit_rate": "Hit Rate",
        "average_forward_return": "Avg Forward Return",
        "average_max_drawdown": "Avg Max Drawdown",
    }
    frame = frame.rename(columns=rename)
    for column in ["Hit Rate", "Avg Forward Return", "Avg Max Drawdown"]:
        if column in frame:
            frame[column] = frame[column].map(lambda value: "-" if pd.isna(value) else f"{float(value) * 100:.1f}%")
    display_columns = [
        "Macro Group",
        "Macro",
        "Series",
        "Condition",
        "Action",
        "Horizon",
        "Decisions",
        "Matured",
        "Hit Rate",
        "Avg Forward Return",
        "Avg Max Drawdown",
    ]
    return frame[[column for column in display_columns if column in frame.columns]]


def _latest_ohlcv_signature(ohlcv_payload) -> tuple[tuple[str, str, int], ...]:
    signature = []
    for ticker, frame in sorted((str(symbol), data) for symbol, data in ohlcv_payload.items()):
        try:
            index = pd.DatetimeIndex(pd.to_datetime(frame.index)).dropna()
            latest = str(pd.Timestamp(index.max()).date()) if len(index) else "missing"
            rows = int(len(frame))
        except Exception:
            latest = "missing"
            rows = 0
        signature.append((ticker.upper(), latest, rows))
    return tuple(signature)


def _journal_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _debrief_cache_key(ohlcv_payload, *, limit: int) -> tuple:
    return (
        str(DEFAULT_JOURNAL_PATH),
        _journal_mtime_ns(DEFAULT_JOURNAL_PATH),
        int(limit),
        _latest_ohlcv_signature(ohlcv_payload),
    )


def render_debrief_lab():
    _md(
        """
        <section class="section" id="debrief-lab">
          <div class="section-head">
            <h2>Debrief lab <span class="count">Run outcomes</span></h2>
            <div class="right">LOCAL JOURNAL</div>
          </div>
        </section>
        """
    )

    try:
        cache_key = _debrief_cache_key(ohlcv, limit=100)
        cached = st.session_state.get("debrief_lab_cache")
        cache_hit = isinstance(cached, dict) and cached.get("key") == cache_key
        if cache_hit:
            payload = cached["payload"]
        else:
            with PERF_AUDIT.section("debrief_lab_compute"):
                records = debrief_journal(DEFAULT_JOURNAL_PATH, ohlcv, limit=100)
                summary_rows = summarize_debriefs(records)
                macro_rows = summarize_debriefs_by_macro_condition(records, horizon="4w")
                candidate_rows = threshold_review_candidates(records, horizon="4w", min_abs_return=0.02)
                outcome_rows = debrief_outcome_rows(records)
                report_markdown = build_debrief_markdown_report(
                    records,
                    summary_rows=summary_rows,
                    macro_rows=macro_rows,
                    candidate_rows=candidate_rows,
                )
                payload = {
                    "records": records,
                    "summary_rows": summary_rows,
                    "macro_rows": macro_rows,
                    "candidate_rows": candidate_rows,
                    "outcome_rows": outcome_rows,
                    "report_markdown": report_markdown,
                }
                st.session_state.debrief_lab_cache = {"key": cache_key, "payload": payload}
        records = payload["records"]
        summary_rows = payload["summary_rows"]
        macro_rows = payload["macro_rows"]
        candidate_rows = payload["candidate_rows"]
        outcome_rows = payload["outcome_rows"]
        report_markdown = payload["report_markdown"]
        log_event(APP_LOGGER, "debrief_lab_rendered",
            cache_hit=cache_hit,
            record_count=len(records),
            summary_count=len(summary_rows),
            macro_count=len(macro_rows),
            candidate_count=len(candidate_rows),
            outcome_count=len(outcome_rows),
        )
        summary = _debrief_summary_frame(summary_rows)
        macro_summary = _debrief_macro_frame(macro_rows)
        candidates = _debrief_candidate_frame(candidate_rows)
    except Exception as exc:
        st.warning(f"Run debrief unavailable: {exc}")
        return

    if summary.empty:
        _md(
            """
            <div class="chart-help">
              <b>No matured run outcomes yet.</b>
              The dashboard is recording decisions now; forward windows need trading days to mature before hit rates appear.
            </div>
            """
        )
        return

    export_left, export_right = st.columns(2)
    with export_left:
        st.download_button(
            "Download outcome CSV",
            data=pd.DataFrame(outcome_rows).to_csv(index=False),
            file_name="run_debrief_outcomes.csv",
            mime="text/csv",
            width="stretch",
        )
    with export_right:
        st.download_button(
            "Download Markdown report",
            data=report_markdown,
            file_name="run_debrief_report.md",
            mime="text/markdown",
            width="stretch",
        )

    st.dataframe(summary, hide_index=True, width="stretch")
    if not macro_summary.empty:
        with st.expander("Macro-conditioned outcomes", expanded=False):
            st.dataframe(macro_summary, hide_index=True, width="stretch")
    if candidates.empty:
        _md(
            """
            <div class="chart-help">
              No 4-week threshold-review candidates yet.
            </div>
            """
        )
    else:
        with st.expander("Threshold review candidates", expanded=False):
            st.dataframe(candidates, hide_index=True, width="stretch")


def render_footer():
    flow_status_label = "NEUTRAL" if provider_flow_feeds_stubbed() else "LIVE"
    html = f"""
    <div class="footer">
      <span>{len(scored)} INSTRUMENTS | 7 PILLARS | PROVIDER FLOW {flow_status_label} | DATA CACHE 60min</span>
      <span>{APP_VERSION} | {st.session_state.theme.upper()}</span>
    </div>
    </div>
    """  # closes <div class="app">
    _md(html)


# =============================== compose page ====================================

def _render_timed(section_name: str, render_fn):
    with PERF_AUDIT.section(section_name):
        return render_fn()


_render_timed("render_header", render_header)
_render_timed("render_header_controls", render_header_controls)
_render_timed("render_drill_click_bridge", render_drill_click_bridge)
_render_timed("render_view_preferences", render_view_preferences)
_render_timed("render_explainer", render_explainer)
_render_timed("render_component_docs", render_component_docs)
_render_timed("render_bluf", render_bluf)
_render_timed("render_data_health", render_data_health)
_render_timed("render_status", render_status)
_render_timed("render_momentum_v2_screens", render_momentum_v2_screens)
_render_timed("render_alerts", render_alerts)
_render_timed("render_picks", render_picks)
_render_timed("render_rrg", render_rrg)
_render_timed("render_sector_spaghetti", render_sector_spaghetti)
_render_timed("render_ticker_analyzer", render_ticker_analyzer)
_render_timed("render_drill", render_drill)
_render_timed("render_comparison_view", render_comparison_view)
_render_timed("render_portfolio_analyzer", render_portfolio_analyzer)
_render_timed("render_custom_universe_builder", render_custom_universe_builder)
_render_timed("render_calibration_lab", render_calibration_lab)
_render_timed("render_evidence_gate_lab", render_evidence_gate_lab)
_render_timed("render_debrief_lab", render_debrief_lab)
_render_timed("render_full_table", render_full_table)
_render_timed("render_personal_trade_backtest", render_personal_trade_backtest)
_render_timed("render_backtest_lab", render_backtest_lab)
_render_timed("render_footer", render_footer)
_mark_data_refresh_completed(ohlcv_result)
_PERF_FINAL_SNAPSHOT = session_snapshot(st.session_state)
log_event(APP_LOGGER, "dashboard_performance_audit",
    rerun_kind=_PERF_RERUN.kind,
    changed_keys=_PERF_RERUN.changed_keys,
    sections_ms=PERF_AUDIT.durations_ms,
    provider=ohlcv_result.provider,
    scored_count=len(scored),
    reused_compute_snapshot=_REUSED_COMPUTE_SNAPSHOT,
    data_refresh_lane=st.session_state.get("data_refresh_lane"),
    data_refresh_requested_at=st.session_state.get("data_refresh_requested_at"),
    ohlcv_fetched_count=len(getattr(ohlcv_result, "data", {}) or {}),
    fresh_cache_hit_count=len(getattr(ohlcv_result, "fresh_cache_hits", ()) or ()),
    stale_cache_hit_count=len(getattr(ohlcv_result, "stale_cache_hits", ()) or ()),
    missing_ohlcv_count=len(getattr(ohlcv_result, "missing", ()) or ()),
    provider_warning_count=len(getattr(ohlcv_result, "warnings", ()) or ()),
    cache_refresh_forced=bool(getattr(ohlcv_result, "cache_refresh_forced", False)),
    fred_series_count=len(_fred_data),
)
st.session_state.performance_last_snapshot = _PERF_FINAL_SNAPSHOT
