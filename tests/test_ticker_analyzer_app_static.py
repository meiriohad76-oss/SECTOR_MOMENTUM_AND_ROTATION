from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_exposes_first_class_ticker_analyzer():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'if "methodology_ticker_input" not in st.session_state:' in app_source
    assert "def render_ticker_analyzer():" in app_source
    assert '<section class="section" id="ticker-analyzer">' in app_source
    assert '<h2>Analyze ticker <span class="count">methodology snapshot</span></h2>' in app_source
    assert 'st.text_input("Ticker to analyze"' in app_source
    assert "parse_single_ticker(ticker_text)" in app_source
    assert "analyze_holdings(result.holdings, scored)" in app_source
    assert "analysis_rows_frame(analysis)" in app_source
    assert "VIEW FULL DRILL-DOWN" in app_source
    assert "_go_to_drill(ticker)" in app_source


def test_ticker_analyzer_renders_before_drill_and_portfolio_sections():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    render_order = [
        '_render_timed("render_ticker_analyzer", render_ticker_analyzer)',
        '_render_timed("render_drill", render_drill)',
        '_render_timed("render_comparison_view", render_comparison_view)',
        '_render_timed("render_portfolio_analyzer", render_portfolio_analyzer)',
    ]
    positions = [app_source.index(call) for call in render_order]

    assert positions == sorted(positions)

