from __future__ import annotations

import pytest

from src import indicators


def test_indicator_helpers_return_none_for_short_history(ohlcv_frame_factory):
    short = ohlcv_frame_factory(days=40)

    assert indicators.momentum_12_1(short) is None
    assert indicators.faber_signal(short) is None
    assert indicators.stage_analysis(short, short) is None
    assert indicators.antonacci_absolute(short, short) is None
    assert indicators.rrg(short, short) is None
    assert indicators.breadth_proxy(short) is None


@pytest.mark.parametrize("missing_ticker", ["SPY", "BIL"])
def test_compute_all_indicators_requires_benchmark_and_tbill(market_ohlcv, missing_ticker):
    missing_bil = dict(market_ohlcv)
    missing_bil.pop(missing_ticker)

    with pytest.raises(ValueError, match="Benchmark SPY or T-bill BIL missing"):
        indicators.compute_all_indicators(missing_bil)


def test_compute_all_indicators_excludes_tbill_and_index_tickers(market_ohlcv):
    out = indicators.compute_all_indicators(market_ohlcv)

    assert "BIL" not in out.index
    assert "^TNX" not in out.index
    assert {"XLK", "XLF", "SOXX", "SPY"}.issubset(set(out.index))
    assert {
        "mom_12_1",
        "faber",
        "stage",
        "above_30wma",
        "ma_slope_pos",
        "mansfield_rs",
        "antonacci",
        "rs_ratio",
        "rs_momentum",
        "rrg_quadrant",
        "breadth_50d",
    }.issubset(set(out.columns))
