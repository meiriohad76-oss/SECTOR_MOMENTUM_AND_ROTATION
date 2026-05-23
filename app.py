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
from src.data import fetch_ohlcv_result, _select_ohlcv_provider
from src.evidence_gates import evaluate_promotion_gate, promotion_gate_decisions_frame
from src.flow import compute_flow_signals, flow_composite_z, STUB_MODE
from src.indicators import compute_all_indicators
from src.macro import assess_regime
from src.macro_tiles import MACRO_CONTEXT_SYMBOLS, fred_macro_snapshot, fred_macro_tile_groups, macro_tile_rows, session_range_tile
from src.navigation import initialize_drill_ticker, select_drill_ticker
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
from src.scoring import compute_composite, apply_state_machine, recent_transitions
from src.structured_logging import configure_structured_logging, log_event
from src.table_preview import table_row_rrg_preview_html
from src.transition_pulse import transition_pulse_class, transition_row_pulse_class
from src.ui_states import defensive_basket_rows, loading_skeleton_slots
from src.universe import ALL_TICKERS, SCORED_TICKERS, UNIVERSE_BY_CLASS, BENCH
from src.universe import US_SECTORS
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


APP_VERSION = "v2.4.9"
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
    "bluf_exit":     "Tickers requiring action this week. Sell on Monday open. Triggered by close below 30wMA, Mansfield RS negative, Antonacci absolute failed, RRG entered Lagging, CMF below -0.10, or sustained ETF redemptions.",
    "bluf_warning":  "Tickers showing early bearish signals. Tighten stops, no new adds. Triggered by RRG dropping to Weakening, breadth below 50%, distribution-day cluster, or OBV/price bearish divergence.",
    "bluf_buy":      "Stage 2 candidates passing every strict gate: price above 30-week SMA with positive slope, Mansfield RS positive, RRG in Leading quadrant, sector breadth ≥ 60%, CMF above +0.05, and positive ETF primary flow.",
    # Status tiles
    "tip_regime":     "Faber 10-month SMA on SPY. Portfolio-level forward circuit breaker. SPY > SMA historically associated with positive forward equity returns; SPY < SMA precedes the worst drawdowns (2000, 2008, 2020). Flip to RISK-OFF triggers defensive rotation to TLT/GLD/BIL.",
    "tip_phase":     "Business-cycle phase per Stovall/Fidelity. Predicts which sector basket will lead the next 3-6 months. EARLY: cyclicals (XLY, XLF, XLRE, XLI, XLK). MID: tech / industrials. LATE: energy + defensives (XLE, XLB, XLP, XLV). RECESSION: pure defensives (XLP, XLU, XLV).",
    "tip_warnings":  "Tickers currently in EXIT or WARNING state. Watch the week-over-week change to gauge market deterioration. Spikes here often precede broader risk-off.",
    # Pick card metrics
    "tip_S":     "Composite forward-outlook score. Weighted z-score across the 7 pillars; the higher this is for a ticker, the stronger the system's forward call. A hard veto fires if F < -0.5sigma. Forward horizon is roughly the worst-case across pillars (1 week to 6 months).",
    "tip_F":     "Institutional money flow z-score (forward indicator). Combines CMF, OBV slope, ETF creations, block-trade direction, RVOL, short-interest delta. Smart money positioning leads price by ~1-3 weeks (Chordia-Swaminathan 2000). F < -0.5sigma kills the trade regardless of price signals.",
    "tip_MOM":     "12-1 momentum (Jegadeesh-Titman 1993): 12-month return excluding the most recent month. Predicts forward 3-12 month relative performance. Top-decile winners have historically beaten bottom-decile losers by ~1%/month for the next year. The most-studied predictive anomaly in finance.",
    "tip_STAGE":     "Weinstein Stage. Predicts next 4-26 weeks of behavior. Stage 1 = basing (setup forming). Stage 2 = ADVANCE (forward outperformance expected). Stage 3 = TOPPING (pullback risk rising). Stage 4 = DECLINE (forward underperformance expected). The MA + slope + RS combination historically continues until the next stage transition.",
    "tip_RRG":     "Relative Rotation Graph quadrant. Predicts the next rotation phase. Improving -> Leading (entry signal, 4-12 wk fwd outperformance). Leading -> Weakening (rotate out, momentum fading). Weakening -> Lagging (full breakdown expected). Lagging -> Improving (Stage-1 basing in progress).",
    # Quadrant cards
    "tip_q_leading":   "Outperforming the benchmark with rising relative momentum. Best buy zone.",
    "tip_q_weakening": "Still outperforming but momentum decaying. Tighten stops; rotation candidate.",
    "tip_q_lagging":   "Underperforming with declining momentum. Avoid or short.",
    "tip_q_improving": "Underperforming but momentum turning up. Watch — early entry zone.",
    # Full table column headers
    "tip_col_FABER":   "Time-series momentum filter. 1 if monthly close > 10-month SMA, else 0. Faber 2007. The binary 'is this asset in its own uptrend' switch.",
    "tip_col_STAGE2":  "1 if Weinstein Stage = 2 (advance), else 0. Requires all three: P > 30wMA, slope > 0, Mansfield RS > 0.",
    "tip_col_ANT":     "Antonacci absolute momentum. 1 if asset's 12mo return > BIL T-bill return. The catastrophic-loss circuit breaker — kept the system out of 2008.",
    "tip_col_BREADTH": "Sector breadth proxy. 1 if % of recent 50 sessions above 50dMA ≥ 50%. A clean way to confirm trend internals.",
    "tip_col_FLOW":    "Pillar-7 flow check. 1 if F > 0 (institutional flow positive). The independent confirmation that price movement is backed by real money.",
    # Drill-down tiles
    "tip_drill_composite": "Master S-score for this ticker (this is the ranking metric).",
    "tip_drill_flow":      "Institutional flow F-score. VETO fires when F < -0.5σ regardless of price-based pillars.",
    "tip_drill_state":     "Current state machine output. See state pill tooltips for definition.",
    "tip_drill_momentum":  "12-1 momentum, Mansfield 52-week relative strength shown alongside.",
}

STATE_TIPS = {
    "STAGE_2_BULLISH":  "FORWARD CALL: expected to outperform its class over the next 4-26 weeks. All entry gates pass (price > 30wMA + slope > 0 + Mansfield RS > 0 + RRG Leading + breadth >= 60% + CMF > 0.05 + ETF flow positive). Historically the highest-edge state.",
    "HOLD":             "FORWARD CALL: trend likely intact for next 4-13 weeks but missing one strict gate (e.g., RRG not Leading, or breadth slightly low). Existing positions are safe; no new entries.",
    "WARNING":          "FORWARD CALL: 5-15% pullback or trend break in the next 2-6 weeks is more likely than continuation. Triggered by RRG -> Weakening 2+ wks, OR breadth < 50%, OR sustained CMF < 0, OR OBV/price bearish divergence, OR 4+ distribution days. Tighten stops.",
    "EXIT":             "FORWARD CALL: 10-30% drawdown over the next 4-13 weeks is the median outcome if the breakdown holds. Triggered by close < 30wMA, OR Mansfield RS < 0, OR Antonacci failed, OR RRG -> Lagging, OR CMF < -0.10, OR ETF redemptions > 1.5% AUM. Sell on Monday open.",
    "BEARISH_STAGE_4":  "FORWARD CALL: continued decline expected. Median Stage-4 duration is 10-22 weeks. Gates confirmed: price < 30wMA + MA slope negative + RRG Lagging 3+ wks + CMF confirmed negative. Avoid long; short candidate.",
    "STAGE_1_BASING":   "FORWARD CALL: possible Stage-2 setup forming over the next 4-13 weeks if remaining gates fill. Recovered from Stage 4: price reclaimed 30wMA but slope still flat AND CMF turned positive. Watchlist.",
}


def _esc(s: str) -> str:
    """HTML-attr-safe escape for tooltip text."""
    return (s.replace('&', '&amp;').replace('"', '&quot;')
             .replace('<', '&lt;').replace('>', '&gt;'))

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

<p><b>Forward-looking signal system.</b> The Sentiment Board monitors {len(SCORED_TICKERS)} instruments across US sectors, industries, countries, factors, themes, crypto exposures, and mega-cap stocks, then applies a 7-pillar methodology to <b>predict</b> which sectors will lead and which will break down. Every score, state, and signal you see on this page is a forward call, not a current-state description. The pillars are leading indicators by construction — each one has decades of out-of-sample evidence that <i>past readings predict forward returns</i>.</p>

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

<h3>The 7 pillars — weights and forward horizons</h3>
<p>Weights sum to 1.00. "Forward horizon" is the empirically-supported window over which each pillar's signal is predictive.</p>
<table>
<thead><tr><th>#</th><th>Pillar</th><th>What it predicts</th><th>Horizon</th><th class="weight">Weight</th></tr></thead>
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
<p>A high S-score is overridden if <code>F &lt; -0.5&sigma;</code>. Price moves without real money behind them historically reverse — flow rejection is the system's main protection against pure-momentum traps.</p>

<h3>Letter grade (forward outlook ranking)</h3>
<table>
<thead><tr><th>Grade</th><th>S-score range</th><th>Forward outlook</th></tr></thead>
<tbody>
<tr><td><span class="grade A">A</span></td><td><code>S &ge; +1.0</code></td><td>Top decile <b>predicted outperformance</b> over the relevant horizon (1wk-6mo)</td></tr>
<tr><td><span class="grade B">B</span></td><td><code>0.0 &le; S &lt; +1.0</code></td><td>Modestly bullish forward call</td></tr>
<tr><td><span class="grade C">C</span></td><td><code>-1.0 &lt; S &lt; 0.0</code></td><td>No edge in either direction</td></tr>
<tr><td><span class="grade D">D</span></td><td><code>-1.5 &le; S &le; -1.0</code></td><td>Mild forward <b>underperformance</b> expected</td></tr>
<tr><td><span class="grade F">F</span></td><td><code>S &lt; -1.5</code></td><td>Bottom decile <b>predicted underperformance</b>; avoid or short</td></tr>
</tbody>
</table>

<h3>State machine — forward calls</h3>
<table>
<thead><tr><th>State</th><th>Forward outlook</th></tr></thead>
<tbody>
<tr><td><span class="pill STAGE_2_BULLISH">STAGE 2 BULLISH</span></td><td><b>Expected outperformance</b> over next 4-26 weeks. All entry gates passed.</td></tr>
<tr><td><span class="pill HOLD">HOLD</span></td><td>Trend intact for next 4-13 weeks; existing positions safe.</td></tr>
<tr><td><span class="pill WARNING">WARNING</span></td><td><b>5-15% pullback or trend break</b> in next 2-6 weeks is more likely than continuation.</td></tr>
<tr><td><span class="pill EXIT">EXIT</span></td><td><b>10-30% drawdown</b> over next 4-13 weeks is the median outcome.</td></tr>
<tr><td><span class="pill BEARISH_STAGE_4">BEARISH STAGE 4</span></td><td><b>Continued decline expected.</b> Median Stage-4 duration is 10-22 weeks.</td></tr>
<tr><td><span class="pill STAGE_1_BASING">STAGE 1 BASING</span></td><td>Possible <b>Stage-2 setup forming</b> over next 4-13 weeks if remaining gates fill.</td></tr>
</tbody>
</table>

<h3>Empirical evidence per pillar</h3>
<p>Forward-prediction evidence supporting each pillar. Citations in full bibliography at <code>docs/sector-rotation-methodology.md</code> &sect;11.</p>
<table>
<thead><tr><th>Pillar</th><th>Evidence of forward predictive power</th></tr></thead>
<tbody>
<tr><td>12-1 Momentum</td><td>Jegadeesh-Titman 1993; 30+ years of out-of-sample data (Asness et al. 2013, AQR; alphaarchitect.com 2024). Top-minus-bottom decile spread averages <b>~1% per month over the next year</b>. The most-studied anomaly in finance.</td></tr>
<tr><td>Mansfield RS / Weinstein Stage 2</td><td>Weinstein 1988; 30+ years of practitioner use. Stage-2 breakouts on weekly charts historically continue an average 6-9 months before Stage 3 confirmation.</td></tr>
<tr><td>Faber 10mo SMA</td><td>Faber 2007 (SSRN 962461); updated 2013 & 2020. SMA10 timing on S&P 500 + 4 other asset classes returned <b>~10.5% vs 9.9% buy-and-hold from 1973-2012</b> with HALF the drawdown — drawdown reduction is the documented edge.</td></tr>
<tr><td>Antonacci Dual Momentum</td><td>Antonacci 2014. Absolute-momentum filter kept the model in T-bills through 2008, capping drawdown at <b>~20% vs S&P 500's -55%</b>. Direct demonstration of forward downside protection.</td></tr>
<tr><td>RRG (RS-Ratio + RS-Momentum)</td><td>de Kempenaer 2004-present (relativerotationgraphs.com). Improving -> Leading transitions historically precede outperformance phases by 4-12 weeks; visible on Bloomberg terminals since 2011.</td></tr>
<tr><td>Business-Cycle Tilt</td><td>Stovall 1996; Fidelity Business Cycle Approach (2014, updated annually). Forward sector returns by phase published with cycle-by-cycle data going back to 1962.</td></tr>
<tr><td>Institutional Flow</td><td>Chordia-Swaminathan 2000 (JoF) and Lee-Swaminathan 2000 (JoF): volume-confirmed momentum substantially outperforms pure-price momentum. CMF/OBV divergences historically lead price by <b>1-3 weeks</b> on breakdowns.</td></tr>
</tbody>
</table>

<p style="margin-top: 18px;"><b>Critical caveat:</b> Past predictive power does not guarantee future predictive power. Each pillar has documented failure modes (momentum crashes per Daniel-Moskowitz 2016, "myth of sector rotation" per Molchanov-Stangl 2018). The system layers seven different pillars precisely because no single signal is reliable on its own. The hard flow-veto and the multi-pillar consensus requirement are designed to reduce the false-positive rate.</p>

<h3>References</h3>
<p>Full methodology with formulas and academic citations: <code>docs/sector-rotation-methodology.md</code> &middot; PDF version in <code>docs/sector-rotation-methodology.pdf</code> &middot; Backlog: <code>docs/BACKLOG.md</code>.</p>

</div>
"""


# =============================== page config =====================================

st.set_page_config(
    page_title="Sentiment Board",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================== load css ========================================

APP_ROOT = Path(__file__).resolve().parent
_STATIC = APP_ROOT / "static"
_CSS = (_STATIC / "style.css").read_text(encoding="utf-8")
BACKTEST_REPORT_PATH = APP_ROOT / "docs" / "backtest_report.md"
BACKTEST_EQUITY_PATH = APP_ROOT / "docs" / "backtest_equity.csv"
BACKTEST_STATES_PATH = APP_ROOT / "docs" / "backtest_states.csv"
BACKTEST_METADATA_PATH = APP_ROOT / "docs" / "backtest_metadata.json"
CALIBRATION_BASELINE_CONFIG_PATH = APP_ROOT / "docs" / "calibration_10y_baseline_config.json"
CALIBRATION_REPORT_PATH = APP_ROOT / "docs" / "calibration_10y_report.md"
CALIBRATION_SUMMARY_PATH = APP_ROOT / "docs" / "calibration_10y_summary.csv"
CALIBRATION_CANDIDATES_PATH = APP_ROOT / "docs" / "calibration_10y_candidates.csv"
CALIBRATION_METADATA_PATH = APP_ROOT / "docs" / "calibration_10y_metadata.json"
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

if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "klass" not in st.session_state:
    st.session_state.klass = "US Sectors"
if "drill_ticker" not in st.session_state:
    st.session_state.drill_ticker = "XLK"
if "drill_range" not in st.session_state:
    st.session_state.drill_range = "1Y"
elif st.session_state.drill_range not in DRILL_RANGE_OPTIONS:
    st.session_state.drill_range = "1Y"
if "portfolio_single_ticker" not in st.session_state:
    st.session_state.portfolio_single_ticker = st.session_state.drill_ticker
if "portfolio_single_source" not in st.session_state:
    st.session_state.portfolio_single_source = st.session_state.drill_ticker
if "custom_universe_text" not in st.session_state:
    st.session_state.custom_universe_text = ""
if "table_open" not in st.session_state:
    st.session_state.table_open = True
if "table_sort" not in st.session_state:
    st.session_state.table_sort = "S_score:desc"
initialize_preferences(st.session_state)
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


# =============================== data load (cached) ==============================

@st.cache_data(ttl=3600, show_spinner=False)
def _load_data(period: str = "3y"):
    tickers = DATA_SYMBOLS
    if _browser_qa_mode_enabled():
        return fetch_ohlcv_result(tickers, period=period, provider="yfinance")
    return fetch_ohlcv_result(tickers, period=period)


def provider_status_banner_html(ohlcv_result):
    if not (ohlcv_result.used_stale_cache or ohlcv_result.missing or ohlcv_result.warnings):
        return ""
    label = "Provider degraded" if ohlcv_result.used_stale_cache else "Provider gap"
    details = " ".join(_esc(message) for message in ohlcv_result.warnings)
    if not details:
        details = "Market data provider returned a partial response."
    return f"""
    <div class="provider-status-banner" role="status">
      <span class="label">{_esc(label)}</span>
      <span>{details}</span>
    </div>
    """


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


@st.cache_data(ttl=21600, show_spinner=False)  # FRED updates monthly/weekly, cache 6h
def _load_fred() -> dict:
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


def _record_dashboard_run(scored_df, bluf_payload, regime_obj, transitions_rows, ohlcv_payload, fred_snapshot) -> None:
    metadata = {
        "phase": regime_obj.phase_hint,
        "risk_on": regime_obj.risk_on,
        "fred_used": regime_obj.fred_used,
        "regime_note": regime_obj.note,
        "fred_macro_snapshot": fred_snapshot,
        "transition_count_14d": len(transitions_rows),
        "benchmarks": {"us": BENCH["US"], "tbill": BENCH["TBILL"]},
        "missing_ohlcv": sorted(set(DATA_SYMBOLS) - set(ohlcv_payload)),
        "bluf_counts": {
            "exits": bluf_payload.get("exits_count", 0),
            "warnings": bluf_payload.get("warns_count", 0),
            "buys": bluf_payload.get("buys_count", 0),
        },
    }
    git_sha = _current_git_sha()
    provider = _select_ohlcv_provider(None)
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
    )
    if result.ok:
        st.session_state.run_journal_last_run_id = result.run_id
        st.session_state.run_journal_last_fingerprint = fingerprint
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
    render_provider_status_banner(ohlcv_result)
    _render_browser_qa_provider_banner()
else:
    loading_placeholder = st.empty()
    render_loading_state(loading_placeholder, "Loading market data", card_count=4)
    try:
        with PERF_AUDIT.section("load_data"):
            ohlcv_result = _load_data("3y")
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
            _fred_data = _load_fred()
            regime = assess_regime(ohlcv[bench_ticker], ohlcv.get("^TNX"), ohlcv.get("^IRX"), fred_cache=_fred_data)
            scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
            scored = apply_state_machine(scored)
            _COMPUTE_SNAPSHOT_CREATED_AT = datetime.now().timestamp()
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


# =============================== derive view-model ===============================

def _state_color_var(state: str) -> str:
    return {
        "STAGE_2_BULLISH":  "var(--st-stage2)",
        "HOLD":             "var(--st-hold)",
        "WARNING":          "var(--st-warn)",
        "EXIT":             "var(--st-exit)",
        "BEARISH_STAGE_4":  "var(--st-bear)",
        "STAGE_1_BASING":   "var(--st-basing)",
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
        return " · ".join(bits[:3])

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
        return " · ".join(bits[:3])

    def _note_buy(row):
        bits = [f"S {row['S_score']:+.2f}"]
        if (row.get("F_score") or 0) > 0:
            bits.append(f"F {row['F_score']:+.2f}")
        if (row.get("mom_12_1") or 0) > 0:
            bits.append(f"mom +{row['mom_12_1']*100:.0f}%")
        return " · ".join(bits[:3])

    def _pack(sub_df, note_fn, kind, label, eta, state):
        items = []
        sub_sorted = sub_df.sort_values("S_score", ascending=(kind == "exit"))
        for tkr, r in sub_sorted.head(4).iterrows():
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
transitions = recent_transitions(n=14)
transitions = _browser_qa_transitions(scored) + transitions
if not _REUSED_COMPUTE_SNAPSHOT:
    _record_dashboard_run(scored, bluf, regime, transitions, ohlcv, fred_macro_snapshot(_fred_data))

# Phase index for the phase bar
PHASE_IDX = {"EARLY": 0, "MID": 1, "LATE": 2, "RECESSION": 3, "UNKNOWN": -1}
phase_idx = PHASE_IDX.get(regime.phase_hint, -1)


# =============================== render helpers ==================================


def _go_to_drill(ticker: str) -> None:
    if select_drill_ticker(st.session_state, st.query_params, ticker, AVAILABLE_TICKERS):
        st.rerun()


def _render_drill_buttons(prefix: str, tickers: list[str], max_columns: int = 4) -> None:
    drill_tickers = [ticker for ticker in dict.fromkeys(tickers) if ticker in scored.index]
    if not drill_tickers:
        return
    _md('<div class="drill-buttons-slot"></div>')
    cols = st.columns(min(len(drill_tickers), max_columns))
    for idx, ticker in enumerate(drill_tickers):
        with cols[idx % len(cols)]:
            if st.button(f"DRILL {ticker}", key=f"{prefix}_{idx}_{ticker}", use_container_width=True):
                _go_to_drill(ticker)


def render_explainer():
    with st.expander("📖  HOW THIS WORKS — system, data flow, pillars, gates", expanded=False):
        _md(SYSTEM_EXPLAINER_HTML)


def render_component_docs():
    with st.expander("COMPONENT DOCS", expanded=False):
        _md(component_docs_html(DASHBOARD_COMPONENT_DOCS))


def render_header():
    now = datetime.now()
    last_update = now.strftime("%H:%M")
    as_of = now.strftime("%a %b %d %Y · %H:%M %Z").upper().strip(" ·").strip()
    next_refresh = "00:60:00"
    html = f"""
    <div class="app">
      <header class="header">
        <div class="brand">
          <span class="brand-mark"></span>
          SENTIMENT&nbsp;BOARD
        </div>
        <div class="meta">
          <span><span class="live-dot"></span>LIVE · {last_update}</span>
          <span class="sep">·</span>
          <span>{as_of}</span>
          <span class="sep">·</span>
          <span>next <span class="val">{next_refresh}</span></span>
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
                use_container_width=True,
                on_click=_load_preference_profile,
                args=(selected_profile_name,),
            )
        with p4:
            st.button(
                "Save",
                key="preference_profile_save",
                use_container_width=True,
                on_click=_save_preference_profile,
            )
        with p5:
            st.button(
                "Delete",
                key="preference_profile_delete",
                disabled=selected_profile is None,
                use_container_width=True,
                on_click=_delete_preference_profile,
                args=(selected_profile_name,),
            )
        if st.session_state.get("preference_profile_error"):
            st.warning(st.session_state.preference_profile_error)
        elif st.session_state.get("preference_profile_message"):
            st.caption(st.session_state.preference_profile_message)


def render_header_controls():
    _md('<div class="header-controls-slot"></div>')
    ctrl_col1, ctrl_col2 = st.columns(2)
    with ctrl_col1:
        st.button(
            "↻",
            key="refresh_btn",
            help="Refresh data",
            use_container_width=True,
            on_click=refresh_market_data,
            args=(_load_data,),
        )
    with ctrl_col2:
        icon = "☀" if st.session_state.theme == "dark" else "☾"
        st.button(
            icon,
            key="theme_btn",
            help="Toggle theme",
            use_container_width=True,
            on_click=toggle_theme,
            args=(st.session_state,),
        )


def render_bluf():
    if not should_render_bluf(st.session_state.bluf_mode):
        return
    compact = is_compact_bluf(st.session_state.bluf_mode)
    instruction = "Use drill controls below for detail." if compact else "Click any action card → drill-down."
    sub = (
        f"Forward calls: {bluf['exits_count']} tickers expected to underperform soon, "
        f"{bluf['warns_count']} showing topping signals, "
        f"{bluf['buys_count']} predicted to lead the next 4-26 weeks. "
        f"Universe: {len(scored)} instruments. "
        f"Risk regime is {('on' if regime.risk_on else 'off')} ({regime.phase_hint.lower()} cycle). "
        f"{instruction}"
    )
    compact_class = " compact" if compact else ""
    head_html = f"""
    <section class="section">
      <div class="bluf{compact_class}">
        <div class="bluf-head">
          <div class="bluf-eyebrow">
            <span class="pill-tiny">BLUF</span>
            <span>BOTTOM LINE · FORWARD OUTLOOK · {datetime.now().strftime('%H:%M')}</span>
            <span class="stamp">{'RISK-ON' if regime.risk_on else 'RISK-OFF'}</span>
          </div>
        </div>
        <div class="bluf-headline">
          <span class="exit-num tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_exit'])}">{bluf['exits_count']}</span> <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_exit'])}">EXIT</span>
          <span class="sep">·</span>
          <span class="warn-num tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_warning'])}">{bluf['warns_count']}</span> <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['bluf_warning'])}">WARNINGS</span>
          <span class="sep">·</span>
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
        items_html = "".join(
            f'<li><span class="t">{it["t"]}</span><span class="n">{it["note"]}</span></li>'
            for it in a["tickers"]
        ) or '<li><span class="t">—</span><span class="n">none</span></li>'
        card_html = f"""
        <div class="action-card {a['kind']}">
          <div class="action-head">
            <div class="action-label">{a['label']}</div>
            <div class="action-eta">{a['eta']}</div>
          </div>
          <span class="pill {a['state']}" data-tip="{_esc(STATE_TIPS.get(a['state'], ""))}">{a['state'].replace('_', ' ')}</span>
          <ul class="action-list">{items_html}</ul>
        </div>
        """
        cards.append(card_html)
    _md(head_html + "".join(cards) + "</div></div></section>")


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
        cycle_sub = " · ".join(bits) if bits else regime.note
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
    delta = '<span class="tile-delta">+2 24H</span>' if n_warn > 0 else ""

    yc_label = (
        "POSITIVE" if regime.yield_curve_positive
        else ("INVERTED" if regime.yield_curve_positive is False else "—")
    )

    session_row = session_range_tile(ohlcv.get(BENCH["US"]), BENCH["US"])
    session_tile_html = f"""
    <div class="tile macro-tile">
      <div class="tile-label">{_esc(session_row['label'])}<span class="tile-delta">{_esc(session_row['symbol'])}</span></div>
      <div class="tile-value {session_row['tone']}">{_esc(session_row['value'])}</div>
      <div class="tile-sub">{_esc(session_row['change'])} / {_esc(session_row['subtitle'])}</div>
    </div>
    """
    macro_tiles_html = ""
    for row in macro_tile_rows(ohlcv):
        macro_tiles_html += f"""
        <div class="tile macro-tile">
          <div class="tile-label">{_esc(row['label'])}<span class="tile-delta">{_esc(row['symbol'])}</span></div>
          <div class="tile-value {row['tone']}">{_esc(row['value'])}</div>
          <div class="tile-sub">{_esc(row['change'])} Â· {_esc(row['subtitle'])}</div>
        </div>
        """
    fred_macro_groups_html = ""
    for group in fred_macro_tile_groups(_fred_data):
        rows_html = ""
        for row in group["rows"]:
            rows_html += f"""
            <div class="tile macro-tile fred-macro-tile">
              <div class="tile-label">{_esc(row['label'])}<span class="tile-delta">{_esc(row['series_id'])}</span></div>
              <div class="tile-value {row['tone']}">{_esc(row['value'])}</div>
              <div class="tile-sub">{_esc(row['change'])} / {_esc(row['subtitle'])}</div>
            </div>
            """
        fred_macro_groups_html += f"""
        <div class="fred-macro-group">
          <div class="fred-macro-group-label">{_esc(group['group'])}</div>
          <div class="fred-macro-grid">{rows_html}</div>
        </div>
        """

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Market state <span class="count">8 indicators</span></h2>
        <div class="right">UPDATED {datetime.now().strftime('%H:%M').upper()}</div>
      </div>
      <div class="status-row">

        <div class="tile">
          <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_regime'])}">Risk regime</span></div>
          <div class="tile-value {risk_tone}">
            <span class="dot" style="background:{risk_dot}"></span>
            {risk_label}
          </div>
          <div class="tile-sub">{sub_risk} · curve {yc_label.lower()}</div>
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
          <div class="tile-sub">{bluf['exits_count']} exit · {bluf['warns_count']} warn</div>
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


def render_alerts():
    rows = ""
    for r in transitions[:8]:
        new_state = r.get("to", "")
        from_state = r.get("from", "—")
        dot_color = color_for_state(new_state)
        when = r.get("date", "")
        ticker = str(r.get("ticker", "")).upper()
        pulse_class = transition_row_pulse_class(r)
        rows += f"""
        <div class="alert-row {new_state} {pulse_class}">
          <span class="dot" style="background:{dot_color}"></span>
          <span class="t">{_esc(ticker)}</span>
          <span class="change">
            <span class="from">{from_state.replace('_', ' ')}</span>
            <span class="arrow">→</span>
            <span class="to">{new_state.replace('_', ' ')}</span>
          </span>
          <span class="when">{when}</span>
          <span class="chev">›</span>
        </div>
        """
    if not rows:
        rows = '<div class="alert-row"><span class="dot" style="background:var(--muted-2)"></span><span class="t">—</span><span class="change">no state changes yet — state machine starts logging on first run</span><span class="when"></span><span class="chev"></span></div>'

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Recent transitions <span class="count">{len(transitions)} in last 14d</span></h2>
        <div class="right">{datetime.now().strftime('%H:%M').upper()}</div>
      </div>
      <div class="alerts">{rows}</div>
    </section>
    """
    _md(html)
    _render_drill_buttons(
        "alert_drill",
        [str(r.get("ticker", "")).upper() for r in transitions[:8]],
    )


def render_picks():
    selected_picks = scored[scored["selected"]].sort_values(["class", "rank_in_class"])
    if selected_picks.empty:
        basket_rows = defensive_basket_rows(scored)
        cards_html = ""
        for row in basket_rows:
            ticker = str(row["ticker"])
            state = str(row["state"])
            available = bool(row["available"])
            pill_class = state if available and state in STATE_TIPS else "HOLD"
            pill_label = state.replace("_", " ") if available else "DATA PENDING"
            unavailable_class = "" if available else " unavailable"
            s_score = row["s_score"]
            f_score = row["f_score"]
            s_text = "--" if s_score is None else f"{float(s_score):+.2f}"
            f_text = "--" if f_score is None else f"{float(f_score):+.2f}"
            s_class = "" if s_score is None else ("pos" if float(s_score) >= 0 else "neg")
            f_class = "" if f_score is None else ("pos" if float(f_score) >= 0 else "neg")
            cards_html += f"""
            <div class="pick defensive-card {pill_class}{unavailable_class}">
              <div class="pick-top">
                <div>
                  <div class="pick-ticker">{ticker}</div>
                  <div class="pick-class">{_esc(str(row["role"]))}</div>
                </div>
                <span class="pill {pill_class}" data-tip="{_esc(STATE_TIPS.get(state, "Awaiting defensive data."))}">{pill_label}</span>
              </div>
              <div class="defensive-note">{_esc(str(row["note"]))}</div>
              <div class="pick-metrics">
                <div class="m"><span class="k">S</span><span class="v {s_class}">{s_text}</span></div>
                <div class="m"><span class="k">F</span><span class="v {f_class}">{f_text}</span></div>
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
        _render_drill_buttons("defensive_drill", [str(row["ticker"]) for row in basket_rows if row["available"]])
        return

    cards_html = ""
    for tkr, p in selected_picks.iterrows():
        state = p["state"]
        s = p["S_score"]
        f = p["F_score"]
        grade = _grade_letter(s)
        mom = (p["mom_12_1"] or 0) * 100
        stage = p.get("stage") or "—"
        quad = (p.get("rrg_quadrant") or "—").upper()
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

        cards_html += f"""
        <div class="pick {state} {pulse_class}">
          <div class="pick-top">
            <div>
              <div class="pick-ticker">{tkr}</div>
              <div class="pick-class">{klass_lbl}</div>
            </div>
            <span class="pill {state}" data-tip="{_esc(STATE_TIPS.get(state, ""))}">{state.replace('_', ' ')}</span>
          </div>
          {spark}
          <div class="pick-metrics">
            <div class="m"><span class="k tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_S'])}">S</span><span class="v {s_class}">{s:+.2f}<span class="grade {grade}">{grade}</span></span></div>
            <div class="m"><span class="k tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_F'])}">F</span><span class="v {f_class}">{f:+.2f}</span></div>
            <div class="m"><span class="k tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_MOM'])}">MOM</span><span class="v {mom_class}">{mom:+.1f}%</span></div>
            <div class="m"><span class="k tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_STAGE'])}">STAGE</span><span class="v">{stage}</span></div>
          </div>
          <div class="pick-foot">
            <span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_RRG'])}">RRG</span>
            <span class="quad">{quad}</span>
          </div>
        </div>
        """

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Picks <span class="count">{len(selected_picks)} active</span></h2>
        <div class="right">SORTED BY COMPOSITE</div>
      </div>
      <div class="picks-grid">{cards_html}</div>
    </section>
    """
    _md(html)
    _render_drill_buttons("pick_drill", selected_picks.index.tolist())


def render_rrg():
    _md('<section class="section"><div class="section-head">'
                f'<h2>Relative Rotation Graph <span class="count">{st.session_state.klass}</span></h2>'
                '<div class="right">DRILL BUTTONS → TICKER DETAIL</div></div></section>')

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
            st.plotly_chart(
                rrg_chart_dark(rrg_sub, title=""),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.info("No data for this class.")

    with right_col:
        for q, color_cls in [("Leading", "leading"), ("Weakening", "weakening"),
                              ("Lagging", "lagging"), ("Improving", "improving")]:
            tickers = quads[q]
            count = len(tickers)
            ticks = " · ".join(tickers) if tickers else "—"
            _md(f'<div class="quad-card {color_cls}">'
                f'<div class="qlbl tip-cue" data-tip="{_esc(INDICATOR_TIPS["tip_q_" + q.lower()])}">{q}</div>'
                f'<div class="qcount">{count}</div>'
                f'<div class="qtick">{ticks}</div>'
                f'</div>',)
            _render_drill_buttons(f"rrg_drill_{q.lower()}", tickers[:8], max_columns=2)


def render_sector_spaghetti():
    fig = sector_spaghetti_chart(ohlcv, US_SECTORS, BENCH["US"])
    _md(
        """
        <section class="section" id="sector-spaghetti">
          <div class="section-head">
            <h2>Sector spaghetti chart <span class="count">B-111 · US sectors</span></h2>
            <div class="right">12M RELATIVE STRENGTH VS SPY</div>
          </div>
        </section>
        """
    )
    if not fig.data:
        st.info("Sector relative-strength chart is unavailable until sector and SPY price data are loaded.")
        return
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


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
        <h2>Per-ticker drill-down <span class="count">{sel} · {row['class']}</span></h2>
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
            <div class="tile-sub">{'VETO' if row.get('veto') else 'OK'} · CMF {row.get('cmf21', 0) or 0:+.2f}</div>
            <div class="tile-help">Institutional money flow z-score: CMF + OBV slope + ETF creations + block ratio + RVOL + short-interest delta. <b>F &gt; 0 = real money entering</b>; F &lt; -0.5&sigma; kills the trade.</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_drill_state'])}">State</span></div>
            <div class="tile-value" style="color:{color};font-size:1.1rem;">{state.replace('_', ' ')}</div>
            <div class="tile-sub">Stage {row.get('stage', '—')} · {(row.get('rrg_quadrant') or '—').upper()}</div>
            <div class="tile-help">State machine output. <b>STAGE 2 BULLISH</b> = active buy. <b>HOLD</b> = position safe. <b>WARNING</b> = tighten stops. <b>EXIT / BEARISH</b> = sell now or short. Hover the pill for the full gate definition.</div>
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

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(price_chart_with_30wma(ohlcv[sel], sel, visible_since=visible_since),
                        use_container_width=True, config={"displayModeBar": False})
        _md('<div class="chart-help"><b>Weinstein Stage 2 visual check.</b> Want price (solid line) above the dashed <b>30-week SMA</b>, with the MA sloping <b>upward</b>. Stage 2 confirmed when both hold AND Mansfield RS &gt; 0. Price crossing below the MA on a weekly close is the canonical EXIT trigger.</div>')
    with c2:
        st.plotly_chart(cmf_chart(ohlcv[sel], sel, visible_since=visible_since),
                        use_container_width=True, config={"displayModeBar": False})
        _md('<div class="chart-help"><b>Chaikin Money Flow (21d) — volume-weighted accumulation/distribution.</b> Above <span style="color:var(--green)">+0.10</span> = strong accumulation (institutional buying). Below <span style="color:var(--red)">-0.10</span> = strong distribution. Sustained negative CMF during a Stage-2 advance is an early Stage-3 topping warning.</div>')
    st.plotly_chart(obv_chart(ohlcv[sel], sel, visible_since=visible_since),
                    use_container_width=True, config={"displayModeBar": False})
    _md('<div class="chart-help"><b>Price vs OBV — bearish divergence detector.</b> When price (left axis) makes a new high but OBV (right axis) does <b>not</b>, institutional money isn\'t following the rally. One of the cleanest pre-breakdown signals. Bullish divergence (OBV new high, price not) often marks Stage-1 accumulation bottoms.</div>')


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
            <h2>Comparison view <span class="count">B-115 · 2-4 tickers</span></h2>
            <div class="right">{len(scored)} scored tickers</div>
          </div>
        </section>
        """
    )
    st.multiselect("COMPARE TICKERS",
        options,
        default=[ticker for ticker in st.session_state.comparison_tickers if ticker in options][:4],
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
        cards += f"""
        <div class="comparison-card {state}">
          <div class="comparison-head">
            <div>
              <div class="comparison-ticker">{_esc(row['ticker'])}</div>
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


def render_full_table():
    toggle_col, sort_col, _ = st.columns([2, 3, 5])
    with toggle_col:
        if st.button(("▾ HIDE" if st.session_state.table_open else "▸ SHOW") + "  FULL 7-PILLAR MATRIX",
                     key="table_toggle"):
            st.session_state.table_open = not st.session_state.table_open
            st.rerun()

    if not st.session_state.table_open:
        return

    SORT_OPTIONS = {
        "S_score:desc":     "S (composite) — high to low",
        "S_score:asc":      "S (composite) — low to high",
        "F_score:desc":     "F (flow) — high to low",
        "F_score:asc":      "F (flow) — low to high",
        "mom_12_1:desc":    "Momentum — high to low",
        "mom_12_1:asc":     "Momentum — low to high",
        "state:asc":        "State (BULLISH → BEARISH)",
        "class:asc":        "Asset class",
        "ticker:asc":       "Ticker (A → Z)",
    }
    with sort_col:
        choice = st.selectbox(
            "Sort by",
            options=list(SORT_OPTIONS.keys()),
            format_func=lambda k: SORT_OPTIONS[k],
            index=list(SORT_OPTIONS.keys()).index(st.session_state.table_sort),
            key="sort_choice",
            label_visibility="collapsed",
        )
        if choice != st.session_state.table_sort:
            st.session_state.table_sort = choice
            st.rerun()

    # Sort the scored df according to the chosen column
    col, direction = st.session_state.table_sort.split(":")
    ascending = (direction == "asc")
    if col == "state":
        # custom order from best to worst
        state_order = ["STAGE_2_BULLISH", "HOLD", "STAGE_1_BASING", "WARNING", "EXIT", "BEARISH_STAGE_4"]
        scored_sorted = scored.copy()
        scored_sorted["_state_rank"] = scored_sorted["state"].map(
            {s: i for i, s in enumerate(state_order)}
        ).fillna(99)
        scored_sorted = scored_sorted.sort_values("_state_rank", ascending=True).drop(columns=["_state_rank"])
    elif col == "ticker":
        scored_sorted = scored.sort_index(ascending=ascending)
    elif col == "class":
        scored_sorted = scored.sort_values(["class", "S_score"], ascending=[ascending, False])
    else:
        scored_sorted = scored.sort_values(col, ascending=ascending, na_position="last")

    rows_html = ""
    # 7 pillar booleans:
    # 1. mom_12_1 > 0
    # 2. faber == 1
    # 3. stage == 2 (Weinstein)
    # 4. antonacci == 1
    # 5. rrg_quadrant in {Leading, Improving}
    # 6. (cycle tilt — derive from class match, approximate)  → just use breadth > 50%
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

        p_tds = "".join(
            f'<td class="num"><span class="dot {"ok" if ok else "bad"}">{"●" if ok else "○"}</span></td>'
            for ok in pillars
        )

        rows_html += f"""
        <tr>
          <td class="t table-ticker">{_esc(tkr)}{preview_html}</td>
          <td style="color:var(--muted)">{r['class']}</td>
          <td><span class="pill {state}" data-tip="{_esc(STATE_TIPS.get(state, ""))}">{state.replace('_', ' ')}</span></td>
          {p_tds}
          <td class="num {'pos' if s >= 0 else 'neg'}">{s:+.2f}</td>
          <td class="num {'pos' if f >= 0 else 'neg'}">{f:+.2f}</td>
          <td class="num {'pos' if mom >= 0 else 'neg'}">{mom:+.1f}%</td>
        </tr>
        """

    pillars_th = "".join(
        f'<th class="num"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS[k])}">{p}</span></th>' for p, k in
        [("MOM","tip_MOM"),("FABER","tip_col_FABER"),("STAGE2","tip_col_STAGE2"),("ANT","tip_col_ANT"),("RRG","tip_RRG"),("BREADTH","tip_col_BREADTH"),("FLOW","tip_col_FLOW")]
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
              <th>Ticker</th>
              <th>Class</th>
              <th>State</th>
              {pillars_th}
              <th class="num"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_S'])}">S</span></th>
              <th class="num"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_F'])}">F</span></th>
              <th class="num"><span class="tip-cue" data-tip="{_esc(INDICATOR_TIPS['tip_MOM'])}">MOM</span></th>
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
        analysis = analyze_holdings(result.holdings, scored)
    except ValueError as exc:
        st.error(str(exc))
        return

    if analysis.missing_tickers:
        st.warning("Missing from scored universe: " + ", ".join(analysis.missing_tickers))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.dataframe(exposure_frame(analysis.state_exposure, "State"), hide_index=True, use_container_width=True)
    with c2:
        st.dataframe(exposure_frame(analysis.class_exposure, "Class"), hide_index=True, use_container_width=True)
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

    st.dataframe(analysis_rows_frame(analysis), hide_index=True, use_container_width=True)

    pnl = analyze_position_pnl(result.holdings, latest_prices_from_ohlcv(ohlcv))
    if not pnl.rows:
        return
    with st.expander("P&L tracker (B-131)", expanded=False):
        if pnl.missing_tickers:
            st.caption("P&L inputs missing for: " + ", ".join(pnl.missing_tickers))
        st.dataframe(pnl_summary_frame(pnl), hide_index=True, use_container_width=True)
        st.dataframe(pnl_rows_frame(pnl), hide_index=True, use_container_width=True)


def render_portfolio_analyzer():
    if st.session_state.portfolio_single_source != st.session_state.drill_ticker:
        st.session_state.portfolio_single_ticker = st.session_state.drill_ticker
        st.session_state.portfolio_single_source = st.session_state.drill_ticker

    _md(
        f"""
        <section class="section" id="portfolio-analyzer">
          <div class="section-head">
            <h2>Portfolio analyzer <span class="count">B-130 · read-only</span></h2>
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
        ticker = st.text_input(
            "Ticker",
            key="portfolio_single_ticker",
            placeholder="XLK",
        )
        if ticker:
            result = parse_single_ticker(ticker)
            _render_portfolio_analysis(result)
            _render_save_portfolio_controls(result, default_name=ticker.upper())
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
        analysis = analyze_custom_universe(result.tickers, scored)
    except ValueError as exc:
        st.error(str(exc))
        return

    if analysis.missing_tickers:
        st.warning("Missing from scored universe: " + ", ".join(analysis.missing_tickers))

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
        st.dataframe(summary_counts_frame(analysis.class_counts, "Class"), hide_index=True, use_container_width=True)
    with c2:
        st.dataframe(summary_counts_frame(analysis.state_counts, "State"), hide_index=True, use_container_width=True)
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

    st.dataframe(custom_universe_rows_frame(analysis), hide_index=True, use_container_width=True)
    _render_drill_buttons("custom_universe_drill", analysis.available_tickers[:8])


def render_custom_universe_builder():
    _md(
        f"""
        <section class="section" id="custom-universe-builder">
          <div class="section-head">
            <h2>Custom universe <span class="count">B-105 · read-only</span></h2>
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
        tickers = st.text_area(
            "Custom tickers",
            key="custom_universe_text",
            placeholder="XLK XLF SOXX NVDA",
            height=90,
        )
        result = parse_custom_universe_text(tickers)
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


def _artifact_status_label(path: Path, expected_hash: str | None = None) -> str:
    if expected_hash is not None:
        return "READY" if _artifact_hash_matches(path, expected_hash) else "PENDING"
    return "READY" if path.exists() else "PENDING"


def render_calibration_lab():
    _md(
        """
        <section class="section" id="calibration-lab">
          <div class="section-head">
            <h2>Calibration lab <span class="count">B-163 · research artifacts</span></h2>
            <div class="right">READ-ONLY EVIDENCE</div>
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
    baseline_config_exists = CALIBRATION_BASELINE_CONFIG_PATH.exists()
    baseline_verified = bool(baseline_hash) and _artifact_hash_matches(
        CALIBRATION_BASELINE_CONFIG_PATH, baseline_hash
    )
    baseline_status = (
        "VERIFIED" if baseline_verified else "UNVERIFIED" if baseline_config_exists else "PENDING"
    )
    split_summary = metadata.get("calibration_split_summary") or calibration_metadata.get(
        "calibration_split_summary"
    )

    status_rows = [
        {
            "Artifact": "Frozen baseline config",
            "Path": "docs/calibration_10y_baseline_config.json",
            "Status": baseline_status,
        },
        {
            "Artifact": "Calibration report",
            "Path": "docs/calibration_10y_report.md",
            "Status": _artifact_status_label(CALIBRATION_REPORT_PATH),
        },
        {
            "Artifact": "Calibration summary",
            "Path": "docs/calibration_10y_summary.csv",
            "Status": _artifact_status_label(CALIBRATION_SUMMARY_PATH),
        },
        {
            "Artifact": "Calibration candidates",
            "Path": "docs/calibration_10y_candidates.csv",
            "Status": _artifact_status_label(CALIBRATION_CANDIDATES_PATH),
        },
        {
            "Artifact": "Calibration metadata",
            "Path": "docs/calibration_10y_metadata.json",
            "Status": _artifact_status_label(CALIBRATION_METADATA_PATH),
        },
    ]
    st.dataframe(pd.DataFrame(status_rows), hide_index=True, use_container_width=True)

    if split_summary:
        _md(
            f"""
            <div class="chart-help">
              <b>Walk-forward split status:</b>
              <code>{_esc(str(split_summary.get("status", "unknown")))}</code>.
              Requested window: <code>{_esc(str(split_summary.get("requested_years", 10)))}</code> years.
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
              Full 10-year calibration report pending. Future B-163 slices will generate
              <code>docs/calibration_10y_report.md</code> after baseline and calibrated
              out-of-sample runs are complete.
            </div>
            """
        )

    summary = _read_csv_artifact(CALIBRATION_SUMMARY_PATH)
    if not summary.empty:
        st.dataframe(summary, hide_index=True, use_container_width=True)

    candidates = _read_csv_artifact(CALIBRATION_CANDIDATES_PATH)
    if not candidates.empty:
        with st.expander("Calibration candidates", expanded=False):
            st.dataframe(candidates, hide_index=True, use_container_width=True)


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
            <h2>Evidence gates <span class="count">B-158 / B-160</span></h2>
            <div class="right">FAIL-CLOSED RESEARCH</div>
          </div>
        </section>
        """
    )

    fred_decision = evaluate_promotion_gate(
        ticket="B-158",
        source="FRED macro",
        summary=_read_validation_summary(FRED_VALIDATION_SUMMARY_PATH),
        validation_report_path="docs/fred_macro_validation_report.md",
    )
    massive_decision = evaluate_promotion_gate(
        ticket="B-160",
        source="Massive provider data",
        summary=_read_validation_summary(MASSIVE_VALIDATION_SUMMARY_PATH),
        validation_report_path="docs/massive_provider_validation_report.md",
    )
    decisions = [fred_decision, massive_decision]
    gate_rows = promotion_gate_decisions_frame(decisions)
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
    st.dataframe(gate_rows, hide_index=True, use_container_width=True)

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


def render_backtest_lab():
    _md(
        """
        <section class="section" id="backtest-lab">
          <div class="section-head">
            <h2>Backtest lab <span class="count">B-011 · manual artifacts</span></h2>
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
        with st.expander("Manual backtest report", expanded=False):
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
        st.line_chart(normalized_equity_frame(equity), use_container_width=True)
        _md(
            """
            <div class="chart-help">
              <b>Drawdown.</b> Percent below each series running high; lower readings
              show the depth of the underwater period.
            </div>
            """
        )
        st.line_chart(drawdown_frame(equity), use_container_width=True)
    else:
        _md(
            """
            <div class="chart-help">
              Equity chart unavailable until <code>docs/backtest_equity.csv</code> is generated.
            </div>
            """
        )


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


def render_personal_trade_backtest():
    _md(
        """
        <section class="section" id="personal-trade-backtest">
          <div class="section-head">
            <h2>Personal trade backtest <span class="count">B-132 · trade history</span></h2>
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
    st.dataframe(trade_alignment_summary_frame(trade_backtest), hide_index=True, use_container_width=True)
    st.dataframe(trade_alignment_frame(trade_backtest), hide_index=True, use_container_width=True)


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


def render_debrief_lab():
    _md(
        """
        <section class="section" id="debrief-lab">
          <div class="section-head">
            <h2>Debrief lab <span class="count">B-153 · run outcomes</span></h2>
            <div class="right">LOCAL JOURNAL</div>
          </div>
        </section>
        """
    )

    try:
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
            use_container_width=True,
        )
    with export_right:
        st.download_button(
            "Download Markdown report",
            data=report_markdown,
            file_name="run_debrief_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.dataframe(summary, hide_index=True, use_container_width=True)
    if not macro_summary.empty:
        with st.expander("Macro-conditioned outcomes", expanded=False):
            st.dataframe(macro_summary, hide_index=True, use_container_width=True)
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
            st.dataframe(candidates, hide_index=True, use_container_width=True)


def render_footer():
    html = f"""
    <div class="footer">
      <span>{len(scored)} INSTRUMENTS · 7 PILLARS · STUB MODE {'ON' if STUB_MODE else 'OFF'} · CACHE TTL 60min</span>
      <span>{APP_VERSION} · {st.session_state.theme.upper()} · MEIRI / READ-ONLY</span>
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
_render_timed("render_view_preferences", render_view_preferences)
_render_timed("render_explainer", render_explainer)
_render_timed("render_component_docs", render_component_docs)
_render_timed("render_bluf", render_bluf)
_render_timed("render_status", render_status)
_render_timed("render_alerts", render_alerts)
_render_timed("render_picks", render_picks)
_render_timed("render_rrg", render_rrg)
_render_timed("render_sector_spaghetti", render_sector_spaghetti)
_render_timed("render_drill", render_drill)
_render_timed("render_comparison_view", render_comparison_view)
_render_timed("render_portfolio_analyzer", render_portfolio_analyzer)
_render_timed("render_custom_universe_builder", render_custom_universe_builder)
_render_timed("render_backtest_lab", render_backtest_lab)
_render_timed("render_calibration_lab", render_calibration_lab)
_render_timed("render_evidence_gate_lab", render_evidence_gate_lab)
_render_timed("render_personal_trade_backtest", render_personal_trade_backtest)
_render_timed("render_debrief_lab", render_debrief_lab)
_render_timed("render_full_table", render_full_table)
_render_timed("render_footer", render_footer)
_PERF_FINAL_SNAPSHOT = session_snapshot(st.session_state)
log_event(APP_LOGGER, "dashboard_performance_audit",
    rerun_kind=_PERF_RERUN.kind,
    changed_keys=_PERF_RERUN.changed_keys,
    sections_ms=PERF_AUDIT.durations_ms,
    provider=ohlcv_result.provider,
    scored_count=len(scored),
    reused_compute_snapshot=_REUSED_COMPUTE_SNAPSHOT,
)
st.session_state.performance_last_snapshot = _PERF_FINAL_SNAPSHOT
