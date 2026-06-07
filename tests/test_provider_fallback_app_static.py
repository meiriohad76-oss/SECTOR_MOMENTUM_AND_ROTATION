from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_uses_fetch_result_and_renders_provider_status_banner():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    ui_states_source = (ROOT / "src" / "ui_states.py").read_text(encoding="utf-8")

    assert "from src.data import fetch_ohlcv_result, _select_ohlcv_provider" in app_source
    assert "provider_status_banner_html as build_provider_status_banner_html" in app_source
    assert "def provider_status_banner_html(ohlcv_result)" in app_source
    assert "return build_provider_status_banner_html(ohlcv_result)" in app_source
    assert "def render_provider_status_banner(ohlcv_result) -> None:" in app_source
    assert "return fetch_ohlcv_result(tickers, period=period, force_refresh=bool(refresh_token))" in app_source
    assert 'ohlcv_result = _load_data("3y", refresh_token=refresh_token)' in app_source
    assert "render_provider_status_banner(ohlcv_result)" in app_source
    assert "ohlcv = ohlcv_result.data" in app_source
    assert "used_stale_cache" in ui_states_source
    assert "provider_retry_count" in ui_states_source
    assert "Provider recovered" in ui_states_source
    assert "provider-status-banner" in ui_states_source


def test_app_live_scoring_path_uses_online_provider_results_not_static_artifacts():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    load_section = app_source[
        app_source.index("def _load_data(") : app_source.index("def _refresh_loaded_data()")
    ]
    compute_section = app_source[
        app_source.index('with PERF_AUDIT.section("load_data"):') : app_source.index("AVAILABLE_TICKERS =")
    ]

    assert "return fetch_ohlcv_result(tickers, period=period, force_refresh=bool(refresh_token))" in load_section
    assert "return _browser_qa_ohlcv_result(tickers, period=period)" in load_section
    assert "BROWSER_QA_ALLOW_FIXTURES" in app_source
    assert 'ohlcv_result = _load_data("3y", refresh_token=refresh_token)' in compute_section
    assert "ohlcv = ohlcv_result.data" in compute_section
    assert "compute_all_indicators(scoring_ohlcv, bench_ticker, bil_ticker)" in compute_section
    assert "compute_flow_signals(scoring_ohlcv)" in compute_section
    assert "_load_fred(refresh_token=fred_refresh_token)" in compute_section
    assert "assess_regime(" in compute_section
    assert "compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)" in compute_section
    assert "apply_state_machine(scored)" in compute_section
    assert "pd.read_csv" not in compute_section
    assert "read_text(" not in compute_section
    assert "docs/" not in compute_section
    assert "browser_qa_ohlcv_result" not in compute_section


def test_provider_flow_footer_and_provenance_do_not_label_config_warnings_as_live():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    provenance_section = app_source[
        app_source.index("def _momentum_v2_data_provenance") : app_source.index("def render_momentum_v2_screens")
    ]
    footer_section = app_source[
        app_source.index("def render_footer():") : app_source.index("# =============================== compose page")
    ]

    assert 'optional_flow_rows = [row for row in flow_rows if row.get("id") != "ohlcv_derived"]' in provenance_section
    assert "live provider feeds" in provenance_section
    assert "def _provider_flow_mode_is_live(row: dict) -> bool:" in app_source
    assert '"live ok" in mode or mode == "enabled"' in app_source
    assert "_provider_flow_mode_is_live(row)" in provenance_section
    assert 'flow_status_label = _provider_flow_footer_label(provider_flow_health_statuses())' in footer_section
    assert "def _provider_flow_footer_label(statuses) -> str:" in footer_section
    assert 'if not optional_rows or provider_flow_feeds_stubbed(statuses):' in footer_section
    assert "_provider_flow_mode_is_live(row)" in footer_section
    assert 'return "PARTIAL"' in footer_section
    assert 'return "WARNING"' in footer_section
    assert 'str(row.get("mode", "")).lower() == "live ok"' not in app_source


def test_provider_status_banner_css_exists():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".provider-status-banner" in css
    assert ".provider-status-banner .label" in css
