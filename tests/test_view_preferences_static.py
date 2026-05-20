from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_view_preferences_are_initialized_and_rendered_near_header():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "initialize_preferences(st.session_state)" in app_source
    assert "render_header_controls()\nrender_view_preferences()" in app_source
    assert "render_bluf()" in app_source


def test_app_uses_preferences_for_bluf_density_and_sparklines():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "density_class(st.session_state.view_density)" in app_source
    assert 'document.documentElement.classList.add("{_density_class}")' in app_source
    assert '<div class="app {shell_class}">' not in app_source
    assert "should_render_bluf(st.session_state.bluf_mode)" in app_source
    assert "is_compact_bluf(st.session_state.bluf_mode)" in app_source
    assert "Use drill controls below for detail." in app_source
    assert "sparkline_mode(st.session_state.sparkline_style)" in app_source


def test_css_contains_compact_density_rules():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "html.density-compact .section" in css
    assert ".bluf.compact" in css
    assert "html.density-compact .pick-spark" in css
