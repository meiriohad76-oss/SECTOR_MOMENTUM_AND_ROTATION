from __future__ import annotations

import concurrent.futures

import pandas as pd

from src import ohlcv_prefetch
from src.data import OhlcvFetchResult


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=40)
    return pd.DataFrame(
        {
            "open": range(40),
            "high": range(1, 41),
            "low": range(40),
            "close": range(100, 140),
            "volume": [1_000_000] * 40,
            "adj_close": range(100, 140),
        },
        index=dates,
    )


def test_warm_ohlcv_cache_returns_summary_without_frames_or_secret_material():
    calls = []

    def fake_fetch(tickers, period, interval, provider, use_cache):
        calls.append((tuple(tickers), period, interval, provider, use_cache))
        return OhlcvFetchResult(
            data={"XLK": _frame()},
            provider="massive",
            fetched=("XLK",),
            fresh_cache_hits=("XLF",),
            stale_cache_hits=("XLV",),
            missing=("XLE",),
            warnings=("Bearer SECRET should not escape",),
        )

    summary = ohlcv_prefetch.warm_ohlcv_cache(
        ["XLK", "XLF", "XLV", "XLE"],
        period="3y",
        provider="massive",
        fetcher=fake_fetch,
    )

    assert calls == [(("XLK", "XLF", "XLV", "XLE"), "3y", "1d", "massive", True)]
    assert summary.provider == "massive"
    assert summary.fetched_count == 1
    assert summary.fresh_cache_hit_count == 1
    assert summary.stale_cache_hit_count == 1
    assert summary.missing_count == 1
    assert summary.warning_count == 1
    assert not hasattr(summary, "data")
    assert "SECRET" not in repr(summary)


def test_warm_ohlcv_cache_failure_reports_error_type_only():
    def fake_fetch(*args, **kwargs):
        raise RuntimeError("Bearer SECRET provider failure")

    summary = ohlcv_prefetch.warm_ohlcv_cache(["XLK"], fetcher=fake_fetch)

    assert summary.provider == "unknown"
    assert summary.error_type == "RuntimeError"
    assert "SECRET" not in repr(summary)


def test_submit_ohlcv_prefetch_dedupes_inflight_request(monkeypatch):
    ohlcv_prefetch.reset_ohlcv_prefetch_state()
    pending: concurrent.futures.Future = concurrent.futures.Future()
    submitted = []

    def fake_submit(fn, *args, **kwargs):
        submitted.append((fn, args, kwargs))
        return pending

    monkeypatch.setattr(ohlcv_prefetch, "_submit_future", fake_submit)

    first = ohlcv_prefetch.submit_ohlcv_prefetch(["XLK"], period="3y")
    second = ohlcv_prefetch.submit_ohlcv_prefetch(["XLK"], period="3y")

    assert first is pending
    assert second is pending
    assert len(submitted) == 1


def test_prefetch_status_summarizes_future_without_exposing_details():
    future: concurrent.futures.Future = concurrent.futures.Future()
    assert ohlcv_prefetch.prefetch_status(future) == "running"

    future.set_result(
        ohlcv_prefetch.OhlcvPrefetchSummary(
            provider="massive",
            fetched_count=2,
            fresh_cache_hit_count=3,
            stale_cache_hit_count=0,
            missing_count=1,
            warning_count=1,
        )
    )

    assert ohlcv_prefetch.prefetch_status(future) == "ready: massive fetched=2 cache=3 missing=1 warnings=1"
