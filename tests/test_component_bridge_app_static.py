from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_applies_control_bridge_actions_before_visual_snapshot():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "apply_control_bridge_query_actions" in app_source
    assert "refresh_market_data(_load_data)" in app_source
    assert "_apply_control_bridge_actions()" in app_source
    assert app_source.index("_apply_control_bridge_actions()") < app_source.index(
        "_density_class = density_class(st.session_state.view_density)"
    )
    assert app_source.index("_apply_control_bridge_actions()") < app_source.index(
        "_PERF_START_SNAPSHOT = session_snapshot(st.session_state)"
    )


def test_app_renders_native_header_controls():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    header_section = app_source[
        app_source.index("def render_header_controls():") : app_source.index("def render_bluf():")
    ]

    assert "st.button(\"REFRESH\"" in header_section
    assert "on_click=_refresh_loaded_data" in header_section
    assert "st.button(theme_label" in header_section
    assert "on_click=toggle_theme" in header_section
    assert '"VIEW",' in header_section
    assert '"PALETTE",' in header_section
    assert "floating_control_bridge_html(" not in header_section
    assert "drill_click_bridge_html()" not in header_section


def test_app_adds_whole_card_drill_attributes_to_clickable_surfaces():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "drill_bridge_attrs(" in app_source
    assert '<div class="pick {state} {pulse_class}" {drill_bridge_attrs(tkr, label=klass_lbl)}>' in app_source
    assert '<div class="alert-row {new_state} {pulse_class}" {drill_bridge_attrs(ticker, label=new_state)}>' in app_source
    assert '<div class="quad-card {color_cls}" {drill_bridge_attrs(tickers[0], label=q) if tickers else ""}>' in app_source


def test_app_renders_rrg_plotly_click_bridge_component():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    rrg_section = app_source[app_source.index("def render_rrg():") : app_source.index("def render_sector_spaghetti():")]

    assert "rrg_plotly_click_bridge_html(" in rrg_section
    assert "st.iframe(" in rrg_section
    assert 'height=620' in rrg_section
    assert "st.plotly_chart(\n                rrg_chart_dark" not in rrg_section
