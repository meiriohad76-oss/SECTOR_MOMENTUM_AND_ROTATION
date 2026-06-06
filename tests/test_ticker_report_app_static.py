from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_drill_renders_complete_single_ticker_report_before_charts():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_drill = app_source[
        app_source.index("def render_drill():") : app_source.index("def render_comparison_view():")
    ]

    assert "def _ticker_report_html(" in app_source
    assert "_md(_ticker_report_html(sel, row))" in render_drill
    assert render_drill.index("_md(_ticker_report_html(sel, row))") < render_drill.index("# Charts")


def test_ticker_report_contains_verdict_triggers_pillars_and_invalidation():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    report_helper = app_source[
        app_source.index("def _ticker_report_html(") : app_source.index("def _provider_status_list_html(")
    ]

    assert "Complete ticker report" in report_helper
    assert "Plain-English verdict" in report_helper
    assert "Trigger checklist" in report_helper
    assert "7-pillar methodology matrix" in report_helper
    assert "What would change the call" in report_helper
    assert "Evidence window" in report_helper
    assert "Stage 2 buy gates" in report_helper
    assert "Risk / exit triggers" in report_helper


def test_ticker_report_gate_helpers_normalize_pandas_boolean_results():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    helper_block = app_source[
        app_source.index("def _normalize_gate_passed(") : app_source.index("def _ticker_report_html(")
    ]

    assert "def _normalize_gate_passed(" in helper_block
    assert "return bool(passed)" in helper_block
    assert "_normalize_gate_passed(passed)" in helper_block
    assert "passed is True" not in helper_block
    assert "passed is False" not in helper_block


def test_ticker_report_uses_actual_indicator_values():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    report_helper = app_source[
        app_source.index("def _ticker_report_html(") : app_source.index("def _provider_status_list_html(")
    ]

    for field in (
        "S_score",
        "F_score",
        "mom_12_1",
        "stage",
        "faber",
        "antonacci",
        "rrg_quadrant",
        "rs_ratio",
        "rs_momentum",
        "breadth_50d",
        "cmf21",
        "etf_flow_5d_pct",
        "block_up_ratio",
        "cycle_tilt",
    ):
        assert f'row.get("{field}")' in report_helper


def test_ticker_report_css_is_responsive_and_readable():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    for selector in (
        ".ticker-report",
        ".ticker-report-grid",
        ".ticker-report-table",
        ".trigger-pass",
        ".trigger-fail",
        ".trigger-neutral",
    ):
        assert selector in css
    desktop_grid = css[css.index(".ticker-report-grid {") : css.index(".ticker-report-verdict")]
    assert "grid-template-columns: 1.1fr 1fr;" in desktop_grid
    assert ".ticker-report-grid { grid-template-columns: 1fr; }" in css
