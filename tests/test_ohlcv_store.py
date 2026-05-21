from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src import data, ohlcv_store


def _frame(days: int = 80, end: date | None = None, start_price: float = 100.0) -> pd.DataFrame:
    end_ts = pd.Timestamp(end or date.today()).normalize()
    dates = pd.bdate_range(end=end_ts, periods=days)
    values = pd.Series(range(days), index=dates, dtype=float)
    close = start_price + values
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000 + values,
            "adj_close": close - 0.25,
        },
        index=dates,
    )


def _expected_window(frame: pd.DataFrame, today: date, period_days: int = 62) -> pd.DataFrame:
    start = pd.Timestamp(today - timedelta(days=period_days))
    return frame.loc[frame.index >= start, ohlcv_store.OHLCV_COLUMNS]


def _yfinance_raw(ticker: str, frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "adj_close": "Adj Close",
            "volume": "Volume",
        }
    )
    renamed = renamed[["Open", "High", "Low", "Close", "Adj Close", "Volume"]]
    renamed.columns = pd.MultiIndex.from_product([renamed.columns, [ticker]])
    return renamed


def _sparse_frame(today: date) -> pd.DataFrame:
    period_start = pd.Timestamp(today - timedelta(days=62))
    early_dates = pd.bdate_range(start=period_start, periods=31)
    dates = early_dates.append(pd.DatetimeIndex([pd.Timestamp(today)]))
    values = pd.Series(range(len(dates)), index=dates, dtype=float)
    close = 50.0 + values
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 500_000 + values,
            "adj_close": close - 0.25,
        },
        index=dates,
    )


def test_default_cache_path_is_anchored_to_project_root(monkeypatch):
    monkeypatch.delenv("OHLCV_CACHE_PATH", raising=False)

    expected = Path(ohlcv_store.__file__).resolve().parent.parent / "data_cache" / "ohlcv.duckdb"

    assert ohlcv_store.ohlcv_cache_path() == expected


def test_duckdb_ohlcv_cache_round_trips_fresh_period(tmp_path):
    cache_path = tmp_path / "ohlcv.duckdb"
    today = date.today()
    frame = _frame(end=today)

    ohlcv_store.write_cached_ohlcv({"XLK": frame}, cache_path=cache_path, provider="unit-test")
    cached = ohlcv_store.read_cached_ohlcv(["XLK", "XLF"], period="2mo", cache_path=cache_path, today=today)

    assert list(cached) == ["XLK"]
    assert_frame_equal(cached["XLK"], _expected_window(frame, today), check_freq=False)


def test_fetch_ohlcv_uses_fresh_duckdb_cache_without_provider_call(tmp_path, monkeypatch):
    cache_path = tmp_path / "ohlcv.duckdb"
    today = date.today()
    frame = _frame(end=today)
    ohlcv_store.write_cached_ohlcv({"XLK": frame}, cache_path=cache_path, provider="unit-test")
    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")

    def fail_download(**kwargs):
        raise AssertionError("fresh DuckDB cache should avoid yfinance")

    monkeypatch.setattr(data.yf, "download", fail_download)

    out = data.fetch_ohlcv(["XLK"], period="2mo", provider="yfinance")

    assert list(out) == ["XLK"]
    assert_frame_equal(out["XLK"], _expected_window(frame, today), check_freq=False)


def test_fetch_ohlcv_persists_provider_results_to_duckdb_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "ohlcv.duckdb"
    today = date.today()
    frame = _frame(end=today)
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return _yfinance_raw("XLK", frame)

    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")
    monkeypatch.setattr(data.yf, "download", fake_download)

    first = data.fetch_ohlcv(["XLK"], period="2mo", provider="yfinance")

    assert list(first) == ["XLK"]
    assert cache_path.exists()
    assert len(calls) == 1

    def fail_download(**kwargs):
        raise AssertionError("second call should be served from DuckDB cache")

    monkeypatch.setattr(data.yf, "download", fail_download)

    second = data.fetch_ohlcv(["XLK"], period="2mo", provider="yfinance")

    assert list(second) == ["XLK"]
    assert_frame_equal(second["XLK"], _expected_window(frame, today), check_freq=False)


def test_fetch_ohlcv_ignores_cache_failures_and_uses_provider(tmp_path, monkeypatch):
    bad_cache_path = tmp_path / "cache-directory"
    bad_cache_path.mkdir()
    today = date.today()
    frame = _frame(end=today)
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return _yfinance_raw("XLK", frame)

    monkeypatch.setenv("OHLCV_CACHE_PATH", str(bad_cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")
    monkeypatch.setattr(data.yf, "download", fake_download)

    out = data.fetch_ohlcv(["XLK"], period="2mo", provider="yfinance")

    assert list(out) == ["XLK"]
    assert len(calls) == 1


def test_sparse_cache_does_not_block_provider_refresh(tmp_path, monkeypatch):
    cache_path = tmp_path / "ohlcv.duckdb"
    today = date.today()
    cached_frame = _sparse_frame(today)
    provider_frame = _frame(end=today, start_price=300.0)
    calls = []
    ohlcv_store.write_cached_ohlcv({"XLK": cached_frame}, cache_path=cache_path, provider="unit-test")

    def fake_download(**kwargs):
        calls.append(kwargs)
        return _yfinance_raw("XLK", provider_frame)

    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")
    monkeypatch.setattr(data.yf, "download", fake_download)

    out = data.fetch_ohlcv(["XLK"], period="2mo", provider="yfinance")

    assert len(calls) == 1
    assert out["XLK"]["close"].iloc[-1] == provider_frame["close"].iloc[-1]
