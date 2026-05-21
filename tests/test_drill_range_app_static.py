from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_drill_range_options_and_session_default_are_defined():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'DRILL_RANGE_OPTIONS = ("3M", "6M", "1Y", "3Y", "MAX")' in app_source
    assert 'if "drill_range" not in st.session_state:' in app_source
    assert 'st.session_state.drill_range = "1Y"' in app_source


def test_drill_range_filters_existing_ohlcv_before_charts():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "filter_ohlcv_lookback" in app_source
    assert "st.radio(" in app_source
    assert '"CHART RANGE"' in app_source
    assert "index=DRILL_RANGE_OPTIONS.index" not in app_source
    assert "selected_range = st.session_state.drill_range" in app_source
    assert "drill_ohlcv = filter_ohlcv_lookback(ohlcv[sel], selected_range)" in app_source
    assert "visible_since = drill_ohlcv.index.min()" in app_source
    assert "price_chart_with_30wma(ohlcv[sel], sel, visible_since=visible_since)" in app_source
    assert "cmf_chart(ohlcv[sel], sel, visible_since=visible_since)" in app_source
    assert "obv_chart(ohlcv[sel], sel, visible_since=visible_since)" in app_source
