from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def test_app_wires_momentum_v2_display_selector_and_renderer():
    assert "render_momentum_v2_screens" in APP
    assert "st.segmented_control" in APP
    assert "momentum_v2_display" in APP
    assert "momentum_v2_screen" in APP
    assert "MOMENTUM_V2_DISPLAY_LABELS" in APP
    assert "MOMENTUM_V2_SCREEN_LABELS" in APP
    assert "render_momentum_v2_display" in APP


def test_app_renders_momentum_v2_before_legacy_signal_sections():
    mv2_pos = APP.index('_render_timed("render_momentum_v2_screens", render_momentum_v2_screens)')
    alerts_pos = APP.index('_render_timed("render_alerts", render_alerts)')
    picks_pos = APP.index('_render_timed("render_picks", render_picks)')

    assert mv2_pos < alerts_pos < picks_pos
