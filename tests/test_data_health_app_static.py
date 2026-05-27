from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_renders_data_health_panel_before_market_state():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.data_health import dashboard_health_summary, data_health_rows" in app_source
    assert "provider_flow_health_statuses" in app_source
    assert "provider_flow_feeds_stubbed" in app_source
    assert "def render_data_health():" in app_source
    assert "Data and dashboard health" in app_source
    assert "Refresh all lanes" in app_source
    assert "REFRESH DATA NOW" not in app_source
    assert "data-health-panel" in app_source
    assert "data-health-card" in app_source
    assert "data-health-provider-list" in app_source
    assert "data-health-role" in app_source
    assert "RENDERED · {last_update}" in app_source
    assert "60M CACHE" in app_source
    assert "_render_timed(\"render_data_health\", render_data_health)" in app_source
    assert app_source.index('_render_timed("render_bluf", render_bluf)') < app_source.index(
        '_render_timed("render_data_health", render_data_health)'
    )
    assert app_source.index('_render_timed("render_data_health", render_data_health)') < app_source.index(
        '_render_timed("render_status", render_status)'
    )


def test_data_health_uses_provider_statuses_to_determine_flow_stub_state():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    health_section = app_source[
        app_source.index("def render_data_health():") : app_source.index("def render_status():")
    ]

    assert "provider_statuses = provider_flow_health_statuses()" in health_section
    assert "provider_flow_stubbed=provider_flow_feeds_stubbed(provider_statuses)" in health_section
    assert "provider_flow_statuses=provider_statuses" in health_section


def test_refresh_action_clears_all_dashboard_data_caches_and_compute_snapshot():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    refresh_section = app_source[
        app_source.index("def _refresh_data_lane(") : app_source.index("def _apply_control_bridge_actions")
    ]

    assert 'if lane_id in {"all", "market_ohlcv"}:' in refresh_section
    assert "refresh_market_data(_load_data)" in refresh_section
    assert "refresh_market_data(_load_ad_hoc_data)" in refresh_section
    assert 'if lane_id in {"all", "fred_macro"}:' in refresh_section
    assert "refresh_market_data(_load_fred)" in refresh_section
    assert 'st.session_state.pop("dashboard_compute_snapshot", None)' in refresh_section
    assert "data_refresh_requested_at" in refresh_section
    assert "data_refresh_token" in refresh_section
    assert "fred_refresh_token" in refresh_section
    assert "flow_refresh_token" in refresh_section
    assert "data_refresh_lane" in refresh_section
    assert "data_refresh_completed_at" in app_source
    assert "data_refresh_completed_request_at" in app_source
    assert "data_refresh_completed_by_lane" in app_source
    assert 'log_event(APP_LOGGER, "data_lane_refresh_completed"' in app_source
    assert 'log_event(APP_LOGGER, "data_lane_refresh_requested"' in refresh_section


def test_refresh_token_forces_provider_reload_without_reusing_persistent_cache():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    load_section = app_source[
        app_source.index("def _load_data(") : app_source.index("def _refresh_loaded_data() -> None:")
    ]
    compute_section = app_source[
        app_source.index("with PERF_AUDIT.section(\"load_data\")") : app_source.index(
            "with PERF_AUDIT.section(\"compute_signals\")"
        )
    ]

    assert "refresh_token: str | None = None" in load_section
    assert "force_refresh=bool(refresh_token)" in load_section
    assert 'refresh_token = st.session_state.get("data_refresh_token")' in compute_section
    assert 'fred_refresh_token = st.session_state.get("fred_refresh_token")' in compute_section
    assert '_load_data("3y", refresh_token=refresh_token)' in compute_section
    assert "_load_fred(refresh_token=fred_refresh_token)" in app_source


def test_data_health_css_supports_status_cards():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".data-health-panel" in css
    assert ".data-health-summary" in css
    assert ".data-health-grid" in css
    assert ".data-health-card" in css
    assert ".data-health-role" in css
    assert ".data-health-card.stale" in css
    assert ".data-health-card.warning" in css
    assert ".data-health-provider-list" in css
    assert ".data-health-provider-list li.warning" in css
    assert ".data-health-refresh-grid" in css
    assert ".lane-refresh-caption" in css
    assert '.element-container:has(.data-health-refresh-grid) + div[data-testid="stHorizontalBlock"]' in css
    assert 'div[class*="st-key-data_health_refresh_market_ohlcv"] div[data-testid="stButton"] > button' in css


def test_data_health_card_subline_includes_optional_coverage_context():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    health_section = app_source[
        app_source.index("def render_data_health():") : app_source.index("def render_status():")
    ]

    assert "coverage = str(row.get(\"coverage\") or \"\")" in health_section
    assert "subline = f\"latest {latest_text}\"" in health_section
    assert "if coverage:" in health_section
    assert "subline += f\" | {coverage}\"" in health_section


def test_data_health_panel_renders_lane_refresh_buttons_from_rows():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    health_section = app_source[
        app_source.index("def render_data_health():") : app_source.index("def render_status():")
    ]

    assert "data-health-refresh-grid" in health_section
    assert "for idx, row in enumerate(rows):" in health_section
    assert "refresh_label = str(row.get(\"refresh_label\"" in health_section
    assert "refresh_key = str(row.get(\"refresh_key\"" in health_section
    assert "st.button(refresh_label" in health_section
    assert 'on_click=_refresh_data_lane' in health_section
    assert 'args=(str(row.get("lane_id")),)' in health_section
    assert "lane-refresh-caption" in health_section
    assert "severity_symbol" in health_section
    assert "_lane_completed_text(" in health_section
    assert 'st.button("Refresh all lanes"' in health_section
    assert 'key="data_health_refresh_all_button"' in health_section
