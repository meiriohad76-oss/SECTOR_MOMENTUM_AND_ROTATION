from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_view_preferences_are_initialized_and_rendered_near_header():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "initialize_preferences(st.session_state)" in app_source
    assert 'PREFERENCE_PROFILES_PATH = APP_ROOT / "data" / "preference_profiles.json"' in app_source
    assert "load_preference_profiles(PREFERENCE_PROFILES_PATH)" in app_source
    assert "apply_preference_profile(st.session_state" in app_source
    assert "save_preference_profile(" in app_source
    assert "delete_preference_profile(" in app_source
    assert '_render_timed("render_header_controls", render_header_controls)' in app_source
    assert '_render_timed("render_view_preferences", render_view_preferences)' in app_source
    assert app_source.index('_render_timed("render_header_controls", render_header_controls)') < app_source.index(
        '_render_timed("render_view_preferences", render_view_preferences)'
    )
    assert "render_bluf()" in app_source


def test_preference_profile_actions_use_callbacks_not_post_widget_mutation():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def render_view_preferences():")
    end = app_source.index("def render_header_controls():")
    section = app_source[start:end]

    assert "on_click=_load_preference_profile" in section
    assert "on_click=_save_preference_profile" in section
    assert "on_click=_delete_preference_profile" in section
    assert 'if st.button("Load"' not in section
    assert 'if st.button("Save"' not in section
    assert 'if st.button("Delete"' not in section
    assert "st.rerun()" not in section


def test_preference_profile_ui_has_no_data_scoring_or_alert_side_effects():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def render_view_preferences():")
    end = app_source.index("def render_header_controls():")
    section = app_source[start:end]

    assert "fetch_ohlcv(" not in section
    assert "fetch_ohlcv_result(" not in section
    assert "compute_composite(" not in section
    assert "apply_state_machine(" not in section
    assert "send_transition_alerts(" not in section
    assert "append_dashboard_run(" not in section
    assert "save_watchlist(" not in section
    assert "save_portfolio(" not in section
    assert "requests." not in section
    assert "log_event(" not in section
    assert "webpush" not in section.lower()
    assert "subscription" not in section.lower()
    assert "LOG_SHIP" not in section


def test_app_uses_preferences_for_bluf_density_and_sparklines():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "density_class(st.session_state.view_density)" in app_source
    assert "palette_key(st.session_state.color_palette)" in app_source
    assert "palette_css_variables(st.session_state.color_palette, st.session_state.theme)" in app_source
    assert 'f"<style>{_CSS}{_EXTRA}{_palette_css}</style>"' in app_source
    assert 'document.documentElement.classList.add("{_density_class}")' in app_source
    assert 'document.documentElement.setAttribute("data-palette","{_palette_key}")' in app_source
    assert '<div class="app {shell_class}">' not in app_source
    assert "should_render_bluf(st.session_state.bluf_mode)" in app_source
    assert "is_compact_bluf(st.session_state.bluf_mode)" in app_source
    assert "sparkline_mode(st.session_state.sparkline_style)" in app_source
    assert "PALETTE_OPTIONS" in app_source
    assert 'st.radio(\n                "Palette",' in app_source


def test_bluf_copy_does_not_reference_removed_card_click_drilldowns():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "Click any action card" not in app_source
    assert "Use drill controls below" not in app_source


def test_css_contains_compact_density_rules():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "html.density-compact .section" in css
    assert ".bluf.compact" in css
    assert "html.density-compact .pick-spark" in css


def test_css_contains_custom_palette_tokens():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert '[data-palette="solarized"]' in css
    assert '[data-palette="nord"]' in css
    assert '[data-palette="mono"]' in css
