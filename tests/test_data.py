from __future__ import annotations

from types import SimpleNamespace

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

    out = data.fetch_ohlcv(["XLK", "XLK"], period="1y", provider="yfinance")

    assert list(out.keys()) == ["XLK"]
    assert list(out["XLK"].columns) == ["open", "high", "low", "close", "volume", "adj_close"]
    assert len(out["XLK"]) == 40
    assert calls[0]["tickers"] == ["XLK"]
    assert calls[0]["period"] == "1y"


def test_fetch_ohlcv_can_use_massive_aggregate_bars(monkeypatch):
    monkeypatch.setenv("OHLCV_PROVIDER", "massive")
    monkeypatch.setenv("MASSIVE_API_KEY", "secret")
    monkeypatch.setenv("MASSIVE_VERIFY_SSL", "true")
    calls = []
    base = pd.Timestamp("2024-01-01", tz="UTC")
    results = [
        {
            "t": int((base + pd.Timedelta(days=idx)).timestamp() * 1000),
            "o": 100.0 + idx,
            "h": 101.0 + idx,
            "l": 99.0 + idx,
            "c": 100.5 + idx,
            "v": 1_000_000 + idx,
        }
        for idx in range(40)
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": results}

    def fake_get(url, params, headers, timeout, verify=None):
        calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
                "verify": verify,
            }
        )
        return FakeResponse()

    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fake_get, RequestException=RuntimeError),
        raising=False,
    )

    out = data.fetch_ohlcv(["XLK"], period="2mo")

    assert list(out.keys()) == ["XLK"]
    assert calls[0]["url"].startswith("https://api.massive.com/v2/aggs/ticker/XLK/range/1/day/")
    assert calls[0]["params"] == {"adjusted": "true", "sort": "asc", "limit": 50000}
    assert calls[0]["headers"] == {"Authorization": "Bearer secret"}
    assert calls[0]["verify"] is True
    assert list(out["XLK"].columns) == ["open", "high", "low", "close", "volume", "adj_close"]
    assert len(out["XLK"]) == 40
    assert out["XLK"]["adj_close"].iloc[0] == 100.5


def test_fetch_ohlcv_massive_can_disable_ssl_verification(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "secret")
    monkeypatch.setenv("MASSIVE_VERIFY_SSL", "false")
    calls = []
    base = pd.Timestamp("2024-01-01", tz="UTC")
    results = [
        {
            "t": int((base + pd.Timedelta(days=idx)).timestamp() * 1000),
            "o": 100.0 + idx,
            "h": 101.0 + idx,
            "l": 99.0 + idx,
            "c": 100.5 + idx,
            "v": 1_000_000 + idx,
        }
        for idx in range(40)
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": results}

    def fake_get(url, params, headers, timeout, verify=None):
        calls.append({"verify": verify})
        return FakeResponse()

    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fake_get, RequestException=RuntimeError),
        raising=False,
    )

    out = data.fetch_ohlcv(["XLK"], provider="massive")

    assert list(out) == ["XLK"]
    assert calls[0]["verify"] is False


def test_fetch_ohlcv_auto_falls_back_to_yfinance_without_massive_key(monkeypatch):
    monkeypatch.setenv("OHLCV_PROVIDER", "auto")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    dates = pd.bdate_range("2024-01-01", periods=40)
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
    )
    raw = pd.DataFrame(1.0, index=dates, columns=columns)
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return raw

    monkeypatch.setattr(data.yf, "download", fake_download)

    out = data.fetch_ohlcv(["XLK"], period="1y", provider="yfinance")

    assert list(out.keys()) == ["XLK"]
    assert calls[0]["tickers"] == ["XLK"]
    assert calls[0]["period"] == "1y"


def test_fetch_ohlcv_massive_returns_empty_on_provider_error(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "secret")
    monkeypatch.setenv("MASSIVE_VERIFY_SSL", "true")

    def fail_get(url, params, headers, timeout, verify=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fail_get, RequestException=RuntimeError),
        raising=False,
    )

    assert data.fetch_ohlcv(["XLK"], provider="massive") == {}


def test_fetch_ohlcv_yfinance_returns_empty_on_download_error(monkeypatch):
    def fail_download(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(data.yf, "download", fail_download)

    assert data.fetch_ohlcv(["XLK"], provider="yfinance") == {}


def test_fetch_ohlcv_explicit_yfinance_ignores_massive_environment(monkeypatch):
    monkeypatch.setenv("OHLCV_PROVIDER", "massive")
    monkeypatch.setenv("MASSIVE_API_KEY", "secret")
    dates = pd.bdate_range("2024-01-01", periods=40)
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
    )
    raw = pd.DataFrame(1.0, index=dates, columns=columns)

    def fake_download(**kwargs):
        return raw

    def fail_get(url, params, headers, timeout):
        raise AssertionError("explicit yfinance should not call Massive")

    monkeypatch.setattr(data.yf, "download", fake_download)
    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fail_get, RequestException=RuntimeError),
        raising=False,
    )

    assert list(data.fetch_ohlcv(["XLK"], provider="yfinance")) == ["XLK"]
