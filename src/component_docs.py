"""Generated component documentation for the Streamlit dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class ComponentDoc:
    name: str
    section: str
    render_function: str
    data_inputs: tuple[str, ...]
    states: tuple[str, ...]
    qa: tuple[str, ...]


DASHBOARD_COMPONENT_DOCS: tuple[ComponentDoc, ...] = (
    ComponentDoc(
        name="Header",
        section="Shell",
        render_function="render_header",
        data_inputs=("clock", "app version", "current theme"),
        states=("render timestamp", "cache window label"),
        qa=("static app wiring", "responsive CSS"),
    ),
    ComponentDoc(
        name="Header controls",
        section="Shell",
        render_function="render_header_controls",
        data_inputs=("cached data loader", "session theme"),
        states=("manual refresh", "theme toggle"),
        qa=("controls unit tests", "static app wiring"),
    ),
    ComponentDoc(
        name="View options",
        section="Shell",
        render_function="render_view_preferences",
        data_inputs=("preference constants",),
        states=("BLUF mode", "density", "sparkline style", "palette"),
        qa=("preference unit tests", "run-journal fingerprint guard"),
    ),
    ComponentDoc(
        name="Methodology explainer",
        section="Documentation",
        render_function="render_explainer",
        data_inputs=("methodology HTML",),
        states=("collapsed expander",),
        qa=("static app wiring",),
    ),
    ComponentDoc(
        name="Component docs",
        section="Documentation",
        render_function="render_component_docs",
        data_inputs=("component catalog",),
        states=("collapsed expander", "generated inventory"),
        qa=("component docs tests",),
    ),
    ComponentDoc(
        name="BLUF",
        section="Decision surface",
        render_function="render_bluf",
        data_inputs=("scored snapshot", "regime", "BLUF view-model"),
        states=("compact mode", "hidden mode", "action counts"),
        qa=("static app wiring", "run-journal coverage"),
    ),
    ComponentDoc(
        name="Data health",
        section="Decision surface",
        render_function="render_data_health",
        data_inputs=("OHLCV metadata", "FRED macro snapshot", "compute timestamp", "provider-flow config"),
        states=("healthy", "warning", "stale", "manual refresh"),
        qa=("data health tests", "dashboard static tests"),
    ),
    ComponentDoc(
        name="Market state",
        section="Decision surface",
        render_function="render_status",
        data_inputs=("regime", "transition rows", "macro OHLCV", "FRED macro snapshot"),
        states=("risk-on", "risk-off", "data pending", "expanded FRED context"),
        qa=("macro tile tests", "session range tests", "run-journal static tests"),
    ),
    ComponentDoc(
        name="Alerts",
        section="Decision surface",
        render_function="render_alerts",
        data_inputs=("state transitions", "scored snapshot"),
        states=("warning", "exit", "bearish", "flow-only"),
        qa=("alert tests", "transition pulse tests"),
    ),
    ComponentDoc(
        name="Picks",
        section="Decision surface",
        render_function="render_picks",
        data_inputs=("selected scored rows", "sparkline OHLCV"),
        states=("active picks", "empty state", "transition pulse"),
        qa=("visual helper tests", "transition pulse static tests"),
    ),
    ComponentDoc(
        name="Relative rotation graph",
        section="Charts",
        render_function="render_rrg",
        data_inputs=("scored snapshot", "universe classes"),
        states=("class filter", "quadrant counts", "empty class"),
        qa=("navigation tests", "visual tests"),
    ),
    ComponentDoc(
        name="Sector spaghetti chart",
        section="Charts",
        render_function="render_sector_spaghetti",
        data_inputs=("loaded sector OHLCV", "SPY benchmark"),
        states=("available chart", "data pending"),
        qa=("sector spaghetti tests",),
    ),
    ComponentDoc(
        name="Analyze ticker",
        section="Analysis",
        render_function="render_ticker_analyzer",
        data_inputs=("typed ticker", "scored snapshot"),
        states=("valid ticker", "invalid ticker", "missing scored ticker", "drill-down handoff"),
        qa=("ticker analyzer static tests", "performance audit tests"),
    ),
    ComponentDoc(
        name="Per-ticker drill-down",
        section="Charts",
        render_function="render_drill",
        data_inputs=("selected ticker", "ticker OHLCV", "scored row"),
        states=("ticker select", "chart range", "missing ticker"),
        qa=("drill range tests", "navigation tests"),
    ),
    ComponentDoc(
        name="Comparison view",
        section="Analysis",
        render_function="render_comparison_view",
        data_inputs=("scored snapshot",),
        states=("2-4 selected tickers", "empty selection"),
        qa=("comparison view tests",),
    ),
    ComponentDoc(
        name="Portfolio analyzer",
        section="Analysis",
        render_function="render_portfolio_analyzer",
        data_inputs=("single ticker", "uploaded holdings", "saved portfolios", "loaded OHLCV prices"),
        states=("ticker mode", "file mode", "missing tickers", "saved inputs", "P&L tracker"),
        qa=("portfolio tests", "saved input tests", "P&L tracker tests"),
    ),
    ComponentDoc(
        name="Custom universe builder",
        section="Analysis",
        render_function="render_custom_universe_builder",
        data_inputs=("pasted tickers", "uploaded ticker file", "saved watchlists"),
        states=("paste mode", "file mode", "unknown tickers", "saved inputs"),
        qa=("custom universe tests", "saved input tests"),
    ),
    ComponentDoc(
        name="Backtest lab",
        section="Research",
        render_function="render_backtest_lab",
        data_inputs=("manual backtest report", "equity artifact", "metadata hash"),
        states=("artifact ready", "artifact missing", "hash mismatch"),
        qa=("backtest static tests", "backtest unit tests"),
    ),
    ComponentDoc(
        name="Calibration lab",
        section="Research",
        render_function="render_calibration_lab",
        data_inputs=(
            "frozen baseline config",
            "calibration report",
            "summary artifacts",
            "candidate config artifact",
            "expanded calibration artifacts",
        ),
        states=(
            "baseline pending",
            "hash unverified",
            "hash verified",
            "report pending",
            "candidate table",
            "candidate config",
            "accepted shortened history",
            "final-holdout evidence",
            "sector-specific overrides",
        ),
        qa=("calibration dashboard model tests", "calibration dashboard static tests", "backtest unit tests"),
    ),
    ComponentDoc(
        name="Evidence gates",
        section="Research",
        render_function="render_evidence_gate_lab",
        data_inputs=("FRED validation summary", "Massive validation summary", "evidence gate report"),
        states=("blocked no candidates", "ready for review", "fail closed"),
        qa=("evidence gate tests", "dashboard static tests"),
    ),
    ComponentDoc(
        name="Personal trade backtest",
        section="Research",
        render_function="render_personal_trade_backtest",
        data_inputs=("uploaded trade history", "methodology state artifact", "metadata hash"),
        states=("artifact ready", "artifact missing", "trade parse errors", "alignment table"),
        qa=("personal trade tests", "static app wiring"),
    ),
    ComponentDoc(
        name="Debrief lab",
        section="Research",
        render_function="render_debrief_lab",
        data_inputs=("local run journal", "loaded OHLCV", "FRED macro snapshot metadata"),
        states=("matured outcomes", "macro-conditioned outcomes", "no outcomes", "threshold candidates"),
        qa=("run debrief tests", "dashboard static tests", "macro debrief tests"),
    ),
    ComponentDoc(
        name="Full matrix",
        section="Matrix",
        render_function="render_full_table",
        data_inputs=("scored snapshot", "table preview data"),
        states=("desktop hover preview", "responsive overflow"),
        qa=("table preview tests", "mobile responsive tests"),
    ),
    ComponentDoc(
        name="Footer",
        section="Shell",
        render_function="render_footer",
        data_inputs=("scored count", "stub mode", "theme"),
        states=("version stamp", "read-only marker"),
        qa=("performance audit render timing",),
    ),
)


def documented_render_functions(docs: Iterable[ComponentDoc]) -> set[str]:
    """Return the render functions covered by a docs catalog."""
    return {doc.render_function for doc in docs}


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values)


def component_docs_rows(docs: Iterable[ComponentDoc]) -> list[dict[str, str]]:
    """Return a table-friendly component inventory."""
    return [
        {
            "Component": doc.name,
            "Section": doc.section,
            "Render Function": doc.render_function,
            "Data Inputs": _join(doc.data_inputs),
            "States": _join(doc.states),
            "QA": _join(doc.qa),
        }
        for doc in docs
    ]


def component_docs_html(docs: Iterable[ComponentDoc]) -> str:
    """Render compact Storybook-style cards from the component catalog."""
    cards = []
    for doc in docs:
        cards.append(
            f"""
            <article class="component-doc-card">
              <div class="component-doc-kicker">{escape(doc.section)}</div>
              <h3>{escape(doc.name)}</h3>
              <div class="component-doc-source">{escape(doc.render_function)}</div>
              <dl>
                <dt>Inputs</dt><dd>{escape(_join(doc.data_inputs))}</dd>
                <dt>States</dt><dd>{escape(_join(doc.states))}</dd>
                <dt>QA</dt><dd>{escape(_join(doc.qa))}</dd>
              </dl>
            </article>
            """
        )
    return f"""
    <section class="section" id="component-docs">
      <div class="section-head">
        <h2>Component docs <span class="count">{len(cards)} components</span></h2>
        <div class="right">Storybook-style inventory</div>
      </div>
      <div class="component-doc-grid">
        {''.join(cards)}
      </div>
    </section>
    """
