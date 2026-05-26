from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_header_controls_render_after_header_and_bottom_controls_removed():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    header_section = app_source[
        app_source.index("def render_header_controls():") : app_source.index("def render_bluf():")
    ]

    assert '_render_timed("render_header", render_header)' in app_source
    assert '_render_timed("render_header_controls", render_header_controls)' in app_source
    assert app_source.index('_render_timed("render_header", render_header)') < app_source.index(
        '_render_timed("render_header_controls", render_header_controls)'
    )
    assert "ctrl_col1, ctrl_col2, _ = st.columns([1, 1, 18])" not in app_source
    assert "_load_data.clear()" not in app_source
    assert '<div class="header-controls-slot"></div>' in header_section
    assert 'st.button("Refresh"' in header_section
    assert "on_click=_refresh_loaded_data" in header_section
    assert "st.button(theme_label" in header_section
    assert "on_click=toggle_theme" in header_section
    assert '"VIEW",' in header_section
    assert '"DENSITY",' in header_section
    assert '"SPARK",' in header_section
    assert '"PALETTE",' in header_section
    assert "floating_control_bridge_html(" not in header_section
    assert "drill_click_bridge_html()" not in header_section


def test_header_controls_css_targets_custom_bridge_and_clickable_cards():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "[data-drill-ticker]" in css
    assert "cursor: pointer;" in css
    assert "[data-drill-ticker]:focus-visible" in css


def test_header_refresh_button_forces_readable_nested_streamlit_text():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert 'div[data-testid="stButton"] > button[kind="secondary"]' in css
    assert 'div[data-testid="stButton"] > button[kind="secondary"] p' in css
    assert 'div[data-testid="stButton"] > button[kind="secondary"] span' in css
    assert "color: var(--ticker-label) !important;" in css


def test_header_native_controls_align_and_use_readable_labels():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert 'div[class*="st-key-header_refresh_data_button"] div[data-testid="stButton"]' in css
    assert 'div[class*="st-key-header_theme_toggle"] div[data-testid="stButton"]' in css
    assert "margin-top: 28px;" in css
    assert "width: min(720px, calc(100vw - 32px));" in css
    assert "min-width: 74px;" in css
    assert "flex: 1 1 0 !important;" in css
    assert 'div[data-testid="stSelectbox"] label' in css
    assert 'div[data-testid="stSelectbox"] label p' in css
    assert 'div[data-testid="stSelectbox"] label span' in css
    assert 'div[data-testid="stSelectbox"] [data-baseweb="select"] > div' in css
    assert "background: var(--panel) !important;" in css
    assert "-webkit-text-fill-color: var(--ticker-label) !important;" in css
    assert "color: var(--ticker-label) !important;" in css
