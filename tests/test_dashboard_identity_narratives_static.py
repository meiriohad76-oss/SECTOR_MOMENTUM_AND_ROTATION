from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_uses_shared_ticker_identity_helpers_on_major_surfaces():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.ticker_identity import TICKER_DISPLAY_NAMES, ticker_display_label, ticker_display_name" in app_source
    assert "ticker_display_label(ticker)" in app_source
    assert "ticker_display_label(sel)" in app_source
    assert "_ticker_identity_subtext(tkr)" in app_source
    assert '_ticker_identity_subtext(row["ticker"])' in app_source
    assert "_ticker_identity_subtext(it[\"t\"])" in app_source
    assert "<span class=\"ticker-name\">" in app_source
    assert "<small>{_esc(ticker_name)}</small>" in app_source


def test_pick_metric_tooltips_are_value_specific_not_generic():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    helper = app_source[app_source.index("def _metric_tip_for_row(") : app_source.index("def _state_tip_for_row(")]
    picks = app_source[app_source.index("def render_picks():") : app_source.index("def render_rrg():")]

    assert "composite S-score is {score}" in helper
    assert "flow F-score is {flow}" in helper
    assert "12-1 momentum is {mom}" in helper
    assert "Weinstein Stage is {stage}" in helper
    assert 'data-tip="{_esc(s_tip)}"' in picks
    assert 'data-tip="{_esc(f_tip)}"' in picks
    assert 'data-tip="{_esc(mom_tip)}"' in picks
    assert 'data-tip="{_esc(stage_tip)}"' in picks
    assert 'data-tip="{_esc(rrg_tip)}"' in picks


def test_ticker_report_explains_score_state_layering_and_chart_narratives():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    report_helper = app_source[
        app_source.index("def _ticker_report_html(") : app_source.index("def _provider_status_list_html(")
    ]
    drill = app_source[app_source.index("def render_drill():") : app_source.index("def render_comparison_view():")]

    assert "Score and state relationship" in report_helper
    assert "different layers" in report_helper
    assert "cross-sectional evidence against peers" in report_helper
    assert "_price_chart_narrative(sel, row, ohlcv[sel])" in drill
    assert "_cmf_chart_narrative(sel, row)" in drill
    assert "_obv_chart_narrative(sel, row)" in drill


def test_tooltip_css_wraps_long_value_specific_explanations():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "overflow-wrap: anywhere;" in css
    assert ".ticker-name" in css
    assert ".alert-row .t small" in css
    assert ".table-ticker small" in css
