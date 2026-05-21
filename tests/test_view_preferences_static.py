from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_view_preferences_are_initialized_and_rendered_near_header():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "initialize_preferences(st.session_state)" in app_source
    assert '_render_timed("render_header_controls", render_header_controls)' in app_source
    assert '_render_timed("render_view_preferences", render_view_preferences)' in app_source
    assert app_source.index('_render_timed("render_header_controls", render_header_controls)') < app_source.index(
        '_render_timed("render_view_preferences", render_view_preferences)'
    )
    assert "render_bluf()" in app_source


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
    assert "Use drill controls below for detail." in app_source
    assert "sparkline_mode(st.session_state.sparkline_style)" in app_source
    assert "PALETTE_OPTIONS" in app_source
    assert 'st.radio(\n                "Palette",' in app_source


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
