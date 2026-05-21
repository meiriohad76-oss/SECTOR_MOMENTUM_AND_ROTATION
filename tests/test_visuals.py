from __future__ import annotations

import pandas as pd
import pytest

from src.visuals import (
    filter_ohlcv_lookback,
    price_chart_with_30wma,
    relative_strength_lines_frame,
    sector_spaghetti_chart,
    svg_sparkline,
)


def _price_frame():
    return pd.DataFrame({"close": [10, 11, 12, 11, 13, 14]})


def _ohlcv(closes, dates):
    return pd.DataFrame({"close": closes, "adj_close": closes}, index=dates)


def test_svg_sparkline_off_returns_empty_markup():
    assert svg_sparkline(_price_frame(), "#26d65b", style="off") == ""


def test_svg_sparkline_line_style_omits_area_fill():
    html = svg_sparkline(_price_frame(), "#26d65b", style="line")

    assert "<svg" in html
    assert 'fill="url(#' not in html
    assert 'stroke="#26d65b"' in html


def test_svg_sparkline_filled_style_keeps_area_fill():
    html = svg_sparkline(_price_frame(), "#26d65b", style="filled")

    assert 'fill="url(#' in html
    assert 'stroke="#26d65b"' in html


def test_relative_strength_lines_frame_normalizes_each_sector_to_100():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {
        "SPY": _ohlcv([100, 100, 100, 100], dates),
        "XLK": _ohlcv([50, 55, 60, 65], dates),
        "XLF": _ohlcv([20, 18, 22, 24], dates),
    }

    frame = relative_strength_lines_frame(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert list(frame.columns) == ["XLK", "XLF"]
    assert frame.iloc[0].to_dict() == {"XLK": 100.0, "XLF": 100.0}
    assert frame.iloc[-1]["XLK"] == pytest.approx(130.0)
    assert frame.iloc[-1]["XLF"] == pytest.approx(120.0)


def test_relative_strength_lines_frame_sorts_by_latest_relative_strength():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {
        "SPY": _ohlcv([100, 100, 100, 100], dates),
        "XLK": _ohlcv([50, 51, 52, 53], dates),
        "XLF": _ohlcv([20, 22, 24, 28], dates),
    }

    frame = relative_strength_lines_frame(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert list(frame.columns) == ["XLF", "XLK"]


def test_relative_strength_lines_frame_sorts_by_each_column_last_valid_value():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {
        "SPY": _ohlcv([100, 100, 100, 100], dates),
        "XLK": _ohlcv([50, 55, 60], dates[:3]),
        "XLF": _ohlcv([20, 21, 22, 23], dates),
    }

    frame = relative_strength_lines_frame(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert list(frame.columns) == ["XLK", "XLF"]
    assert frame["XLK"].dropna().iloc[-1] == pytest.approx(120.0)
    assert frame["XLF"].dropna().iloc[-1] == pytest.approx(115.0)


def test_relative_strength_lines_frame_skips_one_point_histories():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {
        "SPY": _ohlcv([100, 100, 100, 100], dates),
        "XLK": _ohlcv([65], dates[-1:]),
        "XLF": _ohlcv([20, 21, 22, 23], dates),
    }

    frame = relative_strength_lines_frame(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert list(frame.columns) == ["XLF"]


def test_relative_strength_lines_frame_returns_empty_without_benchmark():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {"XLK": _ohlcv([50, 55, 60, 65], dates)}

    frame = relative_strength_lines_frame(ohlcv, ["XLK"], bench_ticker="SPY", lookback_days=4)

    assert frame.empty


def test_sector_spaghetti_chart_adds_one_trace_per_available_sector():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {
        "SPY": _ohlcv([100, 100, 100, 100], dates),
        "XLK": _ohlcv([50, 55, 60, 65], dates),
        "XLF": _ohlcv([20, 18, 22, 24], dates),
    }

    fig = sector_spaghetti_chart(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert [trace.name for trace in fig.data] == ["XLK", "XLF"]
    assert fig.layout.yaxis.title.text == "Relative strength vs SPY, start = 100"


def test_filter_ohlcv_lookback_uses_latest_available_date():
    dates = pd.date_range("2025-01-01", "2025-08-01", freq="MS")
    frame = _ohlcv(list(range(len(dates))), dates)

    filtered = filter_ohlcv_lookback(frame, "3M")

    assert filtered.index.min() == pd.Timestamp("2025-05-01")
    assert filtered.index.max() == pd.Timestamp("2025-08-01")


def test_filter_ohlcv_lookback_max_keeps_all_rows_sorted():
    dates = pd.to_datetime(["2025-03-01", "2025-01-01", "2025-02-01"])
    frame = _ohlcv([3, 1, 2], dates)

    filtered = filter_ohlcv_lookback(frame, "MAX")

    assert list(filtered.index) == sorted(dates)


def test_filter_ohlcv_lookback_invalid_range_uses_one_year_default():
    dates = pd.date_range("2024-01-01", "2025-08-01", freq="MS")
    frame = _ohlcv(list(range(len(dates))), dates)

    filtered = filter_ohlcv_lookback(frame, "BAD")

    assert filtered.index.min() == pd.Timestamp("2024-08-01")


def test_price_chart_with_30wma_visible_since_preserves_sma_warmup():
    dates = pd.bdate_range("2024-01-01", periods=420)
    frame = _ohlcv(list(range(100, 520)), dates)
    visible_since = dates[-63]

    fig = price_chart_with_30wma(frame, "XLK", visible_since=visible_since)

    close_trace, sma_trace = fig.data
    assert min(close_trace.x) >= visible_since
    assert min(sma_trace.x) >= visible_since
    assert any(pd.notna(value) for value in sma_trace.y)
