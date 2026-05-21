from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_custom_universe_builder_without_new_fetch_path():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.custom_universe import" in app_source
    assert "def render_custom_universe_builder():" in app_source
    assert "parse_custom_universe_text(" in app_source
    assert "parse_custom_universe_file(" in app_source
    assert "analyze_custom_universe(result.tickers, scored)" in app_source
    assert "custom_universe_rows_frame(analysis)" in app_source
    assert "fetch_ohlcv(result.tickers" not in app_source
    assert "apply_state_machine(result.tickers" not in app_source


def test_custom_universe_renders_between_portfolio_and_backtest_labs():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    render_order = [
        '_render_timed("render_portfolio_analyzer", render_portfolio_analyzer)',
        '_render_timed("render_custom_universe_builder", render_custom_universe_builder)',
        '_render_timed("render_backtest_lab", render_backtest_lab)',
    ]
    positions = [app_source.index(call) for call in render_order]

    assert positions == sorted(positions)


def test_custom_universe_section_has_stable_styling_hook():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    css_source = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert 'id="custom-universe-builder"' in app_source
    assert "custom-universe-summary" in app_source
    assert ".custom-universe-summary" in css_source
    assert "@media (max-width: 760px)" in css_source
    assert ".custom-universe-summary { grid-template-columns: 1fr; }" in css_source
