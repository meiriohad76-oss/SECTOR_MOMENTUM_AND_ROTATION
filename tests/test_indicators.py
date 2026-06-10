from __future__ import annotations

from types import SimpleNamespace

from pandas.testing import assert_frame_equal
import pytest

from src import indicators


class _ImmediateFuture:
    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value


def _recording_executor():
    submitted = []
    created = []

    class RecordingExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers
            created.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def submit(self, fn, *args, **kwargs):
            submitted.append(args[0])
            return _ImmediateFuture(fn(*args, **kwargs))

    return RecordingExecutor, submitted, created


def test_indicator_helpers_return_none_for_short_history(ohlcv_frame_factory):
    short = ohlcv_frame_factory(days=40)

    assert indicators.momentum_12_1(short) is None
    assert indicators.return_5d(short.iloc[:5]) is None
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
        "return_5d",
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


def test_return_5d_uses_latest_close_vs_five_sessions_ago(ohlcv_frame_factory):
    frame = ohlcv_frame_factory(days=12)
    close = indicators.close_price(frame)

    assert indicators.return_5d(frame) == pytest.approx(close.iloc[-1] / close.iloc[-6] - 1.0)


def test_compute_all_indicators_parallelizes_eligible_tickers_by_default(market_ohlcv, monkeypatch):
    executor, submitted, created = _recording_executor()
    monkeypatch.setattr(indicators, "ThreadPoolExecutor", executor, raising=False)
    monkeypatch.setattr(indicators, "os", SimpleNamespace(cpu_count=lambda: 4), raising=False)

    out = indicators.compute_all_indicators(market_ohlcv)

    assert created
    assert created[0].max_workers == 4
    assert submitted == ["XLK", "XLF", "SOXX", "SPY"]
    assert list(out.index) == submitted


def test_compute_all_indicators_respects_explicit_worker_count_and_order(market_ohlcv, monkeypatch):
    executor, submitted, created = _recording_executor()
    monkeypatch.setattr(indicators, "ThreadPoolExecutor", executor, raising=False)

    out = indicators.compute_all_indicators(market_ohlcv, max_workers=3)

    assert created
    assert created[0].max_workers == 3
    assert submitted == ["XLK", "XLF", "SOXX", "SPY"]
    assert list(out.index) == submitted


def test_compute_all_indicators_can_run_serially_for_debugging(market_ohlcv, monkeypatch):
    class FailingExecutor:
        def __init__(self, max_workers):
            raise AssertionError("serial indicator execution should not create an executor")

    monkeypatch.setattr(indicators, "ThreadPoolExecutor", FailingExecutor, raising=False)

    out = indicators.compute_all_indicators(market_ohlcv, max_workers=1)

    assert list(out.index) == ["XLK", "XLF", "SOXX", "SPY"]


def test_compute_all_indicators_parallel_output_matches_serial_output(market_ohlcv):
    parallel = indicators.compute_all_indicators(market_ohlcv)
    serial = indicators.compute_all_indicators(market_ohlcv, max_workers=1)

    assert list(parallel.index) == list(serial.index)
    assert_frame_equal(parallel, serial)
