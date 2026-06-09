from __future__ import annotations

from datetime import date

import pandas as pd

from src.api_ticker_chart import build_ticker_chart_payload
from src.ohlcv_store import write_cached_ohlcv


def _daily_frame(days: int = 320, end: date | None = None) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp(end or date.today()), periods=days)
    close = pd.Series(range(days), index=dates, dtype=float) + 100.0
    high = close + 1.0
    low = close - 1.0
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1_000_000.0,
            "adj_close": close,
        },
        index=dates,
    )


def test_ticker_chart_payload_reads_cached_ohlcv_without_provider_fetch(tmp_path):
    cache_path = tmp_path / "ohlcv.duckdb"
    frame = _daily_frame()
    write_cached_ohlcv({"XLK": frame}, cache_path=cache_path, provider="massive")

    payload = build_ticker_chart_payload("xlk", period="1y", cache_path=cache_path, max_points=20)

    assert payload["status"] == "ready"
    assert payload["ticker"] == "XLK"
    assert payload["identity"]
    assert payload["source"]["mode"] == "cache-only"
    assert payload["source"]["provider"] == "massive"
    assert payload["source"]["row_count"] > 30
    assert 1 <= len(payload["series"]) <= 20
    assert payload["series"][-1]["close"] == frame["close"].iloc[-1]
    assert payload["series"][-1]["ma30w"] is not None
    assert payload["latest"]["above_30wma"] is True
    assert payload["flow_series"]
    assert payload["flow_series"][-1]["cmf21"] is not None
    assert payload["flow_series"][-1]["obv"] is not None
    assert payload["latest"]["cmf21"] == payload["flow_series"][-1]["cmf21"]
    assert payload["latest"]["obv_slope"] is not None


def test_ticker_chart_payload_fails_closed_when_cache_missing(tmp_path):
    payload = build_ticker_chart_payload("MISSING", cache_path=tmp_path / "missing.duckdb")

    assert payload["status"] == "empty"
    assert payload["ticker"] == "MISSING"
    assert payload["series"] == []
    assert payload["flow_series"] == []
    assert payload["source"]["mode"] == "cache-only"
