from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_comparison_view_app_wiring():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        "from src.comparison_view import (\n"
        "    comparison_card_rows,\n"
        "    initialize_comparison_tickers,\n"
        ")"
    ) in app_source
    assert "def render_comparison_view():" in app_source
    assert "initialize_comparison_tickers(" in app_source
    assert "comparison_default_tickers(" not in app_source
    assert 'st.multiselect("COMPARE TICKERS"' in app_source
    assert '<div class="comparison-selector-slot"></div>' in app_source
    assert app_source.index('<div class="comparison-selector-slot"></div>') < app_source.index(
        'st.multiselect("COMPARE TICKERS"'
    )
    comparison_widget_section = app_source[
        app_source.index('st.multiselect("COMPARE TICKERS"') : app_source.index(
            "selected_compare = list(st.session_state.comparison_tickers)[:4]"
        )
    ]
    assert "default=" not in comparison_widget_section
    assert "selected_compare = list(st.session_state.comparison_tickers)[:4]" in app_source
    assert "comparison_card_rows(scored, selected_compare)" in app_source
    render_order = [
        '_render_timed("render_drill", render_drill)',
        '_render_timed("render_comparison_view", render_comparison_view)',
        '_render_timed("render_portfolio_analyzer", render_portfolio_analyzer)',
    ]
    positions = [app_source.index(call) for call in render_order]

    assert positions == sorted(positions)


def test_comparison_view_css_present_and_responsive():
    css_source = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".comparison-grid {" in css_source
    assert ".comparison-card {" in css_source
    assert ".comparison-metrics {" in css_source
    assert ".comparison-card .state" in css_source
    assert ".comparison-selector-slot" in css_source
    assert 'div[class*="st-key-comparison_tickers"]' in css_source
    assert ".comparison-metrics b {\n  display: block;\n  margin-top: 4px;\n  color: var(--ticker-label);" in css_source
    assert ".comparison-metrics span,\n.comparison-flags span {\n  display: block;\n  color: var(--fg-dim);" in css_source
    assert ".comparison-card .state {\n  color: var(--ticker-label);" in css_source
    assert "@media (max-width: 1100px)" in css_source
    assert ".comparison-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in css_source
    assert "@media (max-width: 760px)" in css_source
    assert ".comparison-grid { grid-template-columns: 1fr; }" in css_source
