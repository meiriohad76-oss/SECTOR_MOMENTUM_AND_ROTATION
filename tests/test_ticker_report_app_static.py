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


def test_ticker_report_flow_gate_ignores_invalid_provider_ratios():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    value_helpers = app_source[
        app_source.index("def _display_value(") : app_source.index("def _ticker_identity_subtext(")
    ]
    report_helper = app_source[
        app_source.index("def _ticker_report_html(") : app_source.index("def _provider_status_list_html(")
    ]

    assert "def _valid_ratio_value(" in value_helpers
    assert "return number if 0.0 <= number <= 1.0 else None" in value_helpers
    assert "def _flow_confirmation_passed(row)" in value_helpers
    assert 'block_value = _valid_ratio_value(row.get("block_up_ratio"))' in report_helper
    assert "flow_confirmation = _flow_confirmation_passed(row)" in report_helper
    assert "No flow veto; at least one valid flow confirmation positive" in report_helper
    assert "Missing or invalid provider enrichments show as n/a" in report_helper


def test_ticker_report_explains_rrg_warning_and_exit_distinction_with_values():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    value_helpers = app_source[
        app_source.index("def _ticker_report_buy_meanings(") : app_source.index("def _forecast_horizon_for_state(")
    ]
    report_helper = app_source[
        app_source.index("def _ticker_report_html(") : app_source.index("def _provider_status_list_html(")
    ]

    assert "RRG buy gate fails: RS-Ratio" in value_helpers
    assert "is above 100 but RS-Momentum" in value_helpers
    assert "is below 100, so relative leadership is fading" in value_helpers
    assert "Rotation is a warning, not an exit" in value_helpers
    assert "Weakening means leadership is fading, but the exit rule waits for Lagging" in value_helpers
    assert "Strict buy gate wants RRG = Leading" in report_helper
    assert 'risk_meanings["rotation"]' in report_helper


def test_ticker_report_uses_value_specific_trigger_and_risk_narratives():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    value_helpers = app_source[
        app_source.index("def _ticker_report_buy_meanings(") : app_source.index("def _forecast_horizon_for_state(")
    ]
    report_helper = app_source[
        app_source.index("def _ticker_report_html(") : app_source.index("def _provider_status_list_html(")
    ]

    assert "Relative strength passes: Mansfield RS is" in value_helpers
    assert "Breadth passes:" in value_helpers
    assert "Money flow passes: CMF is" in value_helpers
    assert "Hard veto passes: F-score is" in value_helpers
    assert "No distribution exit: CMF is" in value_helpers
    assert "block-ratio data is unavailable or invalid and is ignored" in value_helpers
    assert 'buy_meanings["trend"]' in report_helper
    assert 'buy_meanings["strength"]' in report_helper
    assert 'buy_meanings["flow"]' in report_helper
    assert 'risk_meanings["distribution"]' in report_helper


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


def test_tooltips_are_viewport_safe():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    bridge_source = (ROOT / "src" / "component_bridge.py").read_text(encoding="utf-8")

    assert "width: min(420px, calc(100vw - 48px));" in css
    assert "overflow-wrap: break-word;" in css
    assert '[data-tip-edge="left"]::after' in css
    assert '[data-tip-edge="right"]::after' in css
    assert "viewport_tooltip_bridge_html" in app_source
    assert "render_viewport_tooltip_bridge" in app_source
    assert '_render_timed("render_viewport_tooltip_bridge", render_viewport_tooltip_bridge)' in app_source
    assert "sector-dashboard-tooltip" in bridge_source
    assert "doc.body.appendChild(tooltip)" in bridge_source
    assert "position: fixed;" in bridge_source
    assert "max-width: calc(100vw - 32px);" in bridge_source
    assert "clamp(centered, margin, parentWindow.innerWidth - width - margin)" in bridge_source
    assert "html.sector-js-tooltips [data-tip]::after" in css
    assert "#sector-dashboard-tooltip" in css
    assert 'closest("[data-tip]")' in app_source
