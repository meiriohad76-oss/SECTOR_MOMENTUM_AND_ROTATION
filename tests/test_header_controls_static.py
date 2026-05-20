from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_header_controls_render_after_header_and_bottom_controls_removed():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_header()\nrender_header_controls()" in app_source
    assert "ctrl_col1, ctrl_col2, _ = st.columns([1, 1, 18])" not in app_source
    assert "_load_data.clear()" not in app_source
    assert "refresh_market_data(_load_data)" in app_source
    assert "toggle_theme(st.session_state)" in app_source


def test_header_controls_css_targets_streamlit_wrapper():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".element-container:has(.header-controls-slot) + div[data-testid=\"stHorizontalBlock\"]" in css
    assert "padding-right: 96px;" in css
    assert "position: fixed;" in css
    assert "top: 12px;" in css
    assert "right: 28px;" in css
