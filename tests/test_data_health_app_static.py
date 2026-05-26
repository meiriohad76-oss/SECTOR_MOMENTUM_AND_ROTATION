from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_renders_data_health_panel_before_market_state():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.data_health import dashboard_health_summary, data_health_rows" in app_source
    assert "def render_data_health():" in app_source
    assert "Data and dashboard health" in app_source
    assert "REFRESH DATA NOW" in app_source
    assert "data-health-panel" in app_source
    assert "data-health-card" in app_source
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


def test_refresh_action_clears_all_dashboard_data_caches_and_compute_snapshot():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    refresh_section = app_source[
        app_source.index("def _refresh_loaded_data() -> None:") : app_source.index("def _apply_control_bridge_actions")
    ]

    assert "refresh_market_data(_load_data)" in refresh_section
    assert "refresh_market_data(_load_ad_hoc_data)" in refresh_section
    assert "refresh_market_data(_load_fred)" in refresh_section
    assert 'st.session_state.pop("dashboard_compute_snapshot", None)' in refresh_section
    assert "data_refresh_requested_at" in refresh_section
    assert "data_refresh_token" in refresh_section


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
    assert '_load_data("3y", refresh_token=refresh_token)' in compute_section


def test_data_health_css_supports_status_cards():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".data-health-panel" in css
    assert ".data-health-summary" in css
    assert ".data-health-grid" in css
    assert ".data-health-card" in css
    assert ".data-health-role" in css
    assert ".data-health-card.stale" in css
    assert ".data-health-card.warning" in css
