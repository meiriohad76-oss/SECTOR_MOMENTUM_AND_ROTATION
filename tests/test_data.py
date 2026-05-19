from __future__ import annotations

import pandas as pd

from src import data


def test_to_weekly_aggregates_ohlcv_to_friday_close():
    dates = pd.bdate_range("2024-01-01", periods=10)
    df = pd.DataFrame(
        {
            "open": range(10, 20),
            "high": range(20, 30),
            "low": range(0, 10),
            "close": range(30, 40),
            "adj_close": range(40, 50),
            "volume": [100] * 10,
        },
        index=dates,
    )

    weekly = data.to_weekly(df)

    assert list(weekly["open"]) == [10, 15]
    assert list(weekly["high"]) == [24, 29]
    assert list(weekly["low"]) == [0, 5]
    assert list(weekly["close"]) == [34, 39]
    assert list(weekly["adj_close"]) == [44, 49]
    assert list(weekly["volume"]) == [500, 500]
    assert all(idx.weekday() == 4 for idx in weekly.index)


def test_to_monthly_aggregates_to_month_end():
    dates = pd.bdate_range("2024-01-29", periods=8)
    df = pd.DataFrame(
        {
            "open": range(8),
            "high": range(10, 18),
            "low": range(8),
            "close": range(20, 28),
            "adj_close": range(30, 38),
            "volume": [10] * 8,
        },
        index=dates,
    )

    monthly = data.to_monthly(df)

    assert list(monthly["open"]) == [0, 3]
    assert list(monthly["close"]) == [22, 27]
    assert list(monthly["adj_close"]) == [32, 37]
    assert list(monthly["volume"]) == [30, 50]


def test_close_price_prefers_adjusted_close_and_falls_back_to_close():
    idx = pd.date_range("2024-01-01", periods=2)
    with_adj = pd.DataFrame({"close": [10, 11], "adj_close": [9, 10]}, index=idx)
    without_adj = pd.DataFrame({"close": [10, 11]}, index=idx)

    assert list(data.close_price(with_adj)) == [9, 10]
    assert list(data.close_price(without_adj)) == [10, 11]


def test_fetch_ohlcv_flattens_mocked_yfinance_response(monkeypatch):
    dates = pd.bdate_range("2024-01-01", periods=40)
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
    )
    raw = pd.DataFrame(1.0, index=dates, columns=columns)
    raw[("Volume", "XLK")] = 1_000_000
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return raw

    monkeypatch.setattr(data.yf, "download", fake_download)

    out = data.fetch_ohlcv(["XLK", "XLK"], period="1y")

    assert list(out.keys()) == ["XLK"]
    assert list(out["XLK"].columns) == ["open", "high", "low", "close", "volume", "adj_close"]
    assert len(out["XLK"]) == 40
    assert calls[0]["tickers"] == ["XLK"]
    assert calls[0]["period"] == "1y"
