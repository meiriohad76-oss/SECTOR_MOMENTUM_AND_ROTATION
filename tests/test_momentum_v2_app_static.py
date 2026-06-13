from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def test_app_wires_momentum_v2_display_selector_and_renderer():
    assert "render_momentum_v2_screens" in APP
    assert "st.segmented_control" in APP
    assert "momentum_v2_display" in APP
    assert "momentum_v2_screen" in APP
    assert "MOMENTUM_V2_DISPLAY_LABELS" in APP
    assert "MOMENTUM_V2_SCREEN_LABELS" in APP
    assert "MOMENTUM_V2_A_SORT_FIELDS" in APP
    assert "MOMENTUM_V2_A_SORT_DIRECTIONS" in APP
    assert "render_momentum_v2_display" in APP
    assert "_momentum_v2_data_provenance(as_of)" in APP
    assert "data_provenance=_momentum_v2_data_provenance(as_of)" in APP
    assert 'st.selectbox(\n                "Heatmap sort column"' in APP
    assert 'st.segmented_control(\n                "Heatmap sort direction"' in APP
    assert "display_a_sort_field=heatmap_sort_field" in APP
    assert "display_a_sort_direction=heatmap_sort_direction" in APP


def test_app_momentum_v2_provenance_uses_live_compute_objects():
    helper = APP[APP.index("def _momentum_v2_data_provenance") : APP.index("def render_momentum_v2_screens")]

    assert "ohlcv_result" in helper
    assert "provider_by_ticker" in helper
    assert "source_by_ticker" in helper
    assert "_fred_data" in helper
    assert "regime.fred_used" in helper
    assert "provider_flow_health_statuses()" in helper
    assert "rows from scored dataframe" in helper
    assert "fixture" not in helper.lower()


def test_app_renders_momentum_v2_before_legacy_signal_sections():
    mv2_pos = APP.index('_render_timed("render_momentum_v2_screens", render_momentum_v2_screens)')
    alerts_pos = APP.index('_render_timed("render_alerts", render_alerts)')
    picks_pos = APP.index('_render_timed("render_picks", render_picks)')

    assert mv2_pos < alerts_pos < picks_pos
