from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from src import data


@pytest.fixture(autouse=True)
def disable_default_ohlcv_cache(monkeypatch):
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "false")


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
    monkeypatch.setattr(data, "_fetch_yfinance_ohlcv", lambda tickers, period, interval: data._ProviderFetchResult({}))

    assert data.fetch_ohlcv(["XLK"], provider="massive") == {}


def test_fetch_ohlcv_yfinance_returns_empty_on_download_error(monkeypatch):
    def fail_download(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(data.yf, "download", fail_download)

    assert data.fetch_ohlcv(["XLK"], provider="yfinance") == {}


def test_fetch_ohlcv_result_retries_yfinance_transient_error(monkeypatch):
    dates = pd.bdate_range("2024-01-01", periods=40)
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
    )
    raw = pd.DataFrame(1.0, index=dates, columns=columns)
    calls = []
    sleeps = []

    def flaky_download(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("temporary provider error")
        return raw

    monkeypatch.setattr(data.yf, "download", flaky_download)
    monkeypatch.setattr(data, "_provider_retry_sleep", lambda seconds: sleeps.append(seconds))

    result = data.fetch_ohlcv_result(["XLK"], period="1y", provider="yfinance")

    assert list(result.data) == ["XLK"]
    assert result.provider_retry_count == 1
    assert sleeps == [data.PROVIDER_RETRY_BACKOFF_SECONDS]
    assert result.warnings == (
        "Provider retry recovered 1 yfinance request before data loaded.",
    )


def test_fetch_ohlcv_result_uses_stale_cache_when_yfinance_is_unavailable(tmp_path, monkeypatch):
    from src import ohlcv_store

    today = pd.Timestamp.today().date()
    cache_path = tmp_path / "ohlcv.duckdb"
    stale_dates = pd.bdate_range(end=pd.Timestamp(today) - pd.Timedelta(days=8), periods=80)
    row_count = len(stale_dates)
    stale_frame = pd.DataFrame(
        {
            "open": range(row_count),
            "high": range(1, row_count + 1),
            "low": range(row_count),
            "close": range(100, 100 + row_count),
            "volume": [1_000_000] * row_count,
            "adj_close": range(100, 100 + row_count),
        },
        index=stale_dates,
    )
    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")
    ohlcv_store.write_cached_ohlcv({"XLK": stale_frame}, cache_path=cache_path, provider="unit-test")

    def fail_download(**kwargs):
        raise RuntimeError("Too Many Requests")

    monkeypatch.setattr(data.yf, "download", fail_download)

    result = data.fetch_ohlcv_result(["XLK"], period="2mo", provider="yfinance")

    assert list(result.data) == ["XLK"]
    assert result.provider == "yfinance"
    assert result.used_stale_cache is True
    assert result.stale_cache_hits == ("XLK",)
    assert result.fetched == ()
    assert result.missing == ()
    assert result.source_by_ticker == {"XLK": "stale_cache"}
    assert result.provider_by_ticker == {"XLK": "unit-test"}
    assert result.warnings == (
        "Using stale cached OHLCV for 1 symbol because yfinance returned no fresh rows.",
        "OHLCV source mix: unit-test=1.",
    )


def test_fetch_ohlcv_result_reports_provider_gap_when_no_cache(monkeypatch):
    def fail_download(**kwargs):
        raise RuntimeError("Too Many Requests")

    monkeypatch.setattr(data.yf, "download", fail_download)

    result = data.fetch_ohlcv_result(["XLK"], period="2mo", provider="yfinance")

    assert result.data == {}
    assert result.used_stale_cache is False
    assert result.missing == ("XLK",)
    assert result.warnings == ("Missing OHLCV for 1 symbol after yfinance fetch.",)


def test_fetch_ohlcv_result_uses_public_fred_for_macro_symbols_after_provider_miss(monkeypatch):
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=45)
    csv_text = "observation_date,VIXCLS\n" + "\n".join(
        f"{date.date()},{15.0 + idx / 10:.1f}" for idx, date in enumerate(dates)
    )
    calls = []

    def fake_massive(tickers, period, interval):
        calls.append(("massive", tuple(tickers), period, interval))
        return data._ProviderFetchResult({})

    def fake_yfinance(tickers, period, interval):
        calls.append(("yfinance", tuple(tickers), period, interval))
        return data._ProviderFetchResult({})

    class FakeResponse:
        text = csv_text

        def raise_for_status(self):
            return None

    def fake_get(url, timeout):
        calls.append(("fred_public", url, timeout))
        return FakeResponse()

    monkeypatch.setattr(data, "_fetch_massive_ohlcv", fake_massive)
    monkeypatch.setattr(data, "_fetch_yfinance_ohlcv", fake_yfinance)
    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fake_get, RequestException=RuntimeError),
        raising=False,
    )

    result = data.fetch_ohlcv_result(["^VIX"], period="1y", provider="massive")

    assert calls[0] == ("massive", ("^VIX",), "1y", "1d")
    assert calls[1][0] == "fred_public"
    assert "VIXCLS" in calls[1][1]
    assert not any(call[0] == "yfinance" for call in calls)
    assert list(result.data) == ["^VIX"]
    assert result.fetched == ("^VIX",)
    assert result.missing == ()
    assert result.source_by_ticker == {"^VIX": "fred_macro_live"}
    assert result.provider_by_ticker == {"^VIX": "fred_macro"}
    assert len(result.data["^VIX"]) > 30
    assert result.data["^VIX"]["close"].iloc[-1] > 18.0
    assert result.warnings == ()


def test_public_fred_macro_fallback_only_handles_known_macro_symbols(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        raise AssertionError("unknown equity tickers should not call public FRED fallback")

    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fake_get, RequestException=RuntimeError),
        raising=False,
    )

    result = data._fetch_public_fred_macro_ohlcv(["XLK"], period="1y")

    assert result.data == {}
    assert calls == []


def test_fetch_ohlcv_result_reports_public_fred_macro_fallback_failure(monkeypatch):
    calls = []

    def fake_massive(tickers, period, interval):
        calls.append(("massive", tuple(tickers)))
        return data._ProviderFetchResult({})

    def fake_yfinance(tickers, period, interval):
        calls.append(("yfinance", tuple(tickers)))
        return data._ProviderFetchResult({})

    def fail_get(url, timeout):
        calls.append(("fred_public", url, timeout))
        raise RuntimeError("timeout")

    monkeypatch.setattr(data, "_fetch_massive_ohlcv", fake_massive)
    monkeypatch.setattr(data, "_fetch_yfinance_ohlcv", fake_yfinance)
    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fail_get, RequestException=RuntimeError),
        raising=False,
    )

    result = data.fetch_ohlcv_result(["^TNX"], period="1y", provider="massive")

    assert result.data == {}
    assert result.missing == ("^TNX",)
    assert not any(call[0] == "yfinance" for call in calls)
    assert result.warnings == (
        "FRED macro fallback unavailable for ^TNX.",
        "Missing OHLCV for 1 symbol after massive fetch.",
    )


def test_fetch_ohlcv_result_uses_yfinance_fallback_when_massive_misses(monkeypatch):
    dates = pd.bdate_range("2024-01-01", periods=40)
    fallback_frame = pd.DataFrame(
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
    calls = []

    def fake_massive(tickers, period, interval):
        calls.append(("massive", tuple(tickers), period, interval))
        return data._ProviderFetchResult({})

    def fake_yfinance(tickers, period, interval):
        calls.append(("yfinance", tuple(tickers), period, interval))
        return data._ProviderFetchResult({"XLK": fallback_frame})

    monkeypatch.setattr(data, "_fetch_massive_ohlcv", fake_massive)
    monkeypatch.setattr(data, "_fetch_yfinance_ohlcv", fake_yfinance)

    result = data.fetch_ohlcv_result(["XLK"], period="2mo", provider="massive")

    assert calls == [("massive", ("XLK",), "2mo", "1d")]
    assert result.provider == "massive"
    assert result.data == {}
    assert result.fetched == ()
    assert result.missing == ("XLK",)
    assert result.source_by_ticker == {}
    assert result.provider_by_ticker == {}
    assert result.warnings == ("Missing OHLCV for 1 symbol after massive fetch.",)


def test_fetch_ohlcv_result_ignores_yfinance_cache_when_massive_is_requested(tmp_path, monkeypatch):
    from src import ohlcv_store

    cache_path = tmp_path / "ohlcv.duckdb"
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=50)
    row_count = len(dates)
    cached_frame = pd.DataFrame(
        {
            "open": range(row_count),
            "high": range(1, row_count + 1),
            "low": range(row_count),
            "close": range(100, 100 + row_count),
            "volume": [1_000_000] * row_count,
            "adj_close": range(100, 100 + row_count),
        },
        index=dates,
    )
    ohlcv_store.write_cached_ohlcv({"XLK": cached_frame}, cache_path=cache_path, provider="yfinance")
    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")
    monkeypatch.setattr(data, "_fetch_massive_ohlcv", lambda tickers, period, interval: data._ProviderFetchResult({}))
    monkeypatch.setattr(
        data,
        "_fetch_yfinance_ohlcv",
        lambda tickers, period, interval: (_ for _ in ()).throw(
            AssertionError("Massive production path must not fall back to yfinance")
        ),
    )

    result = data.fetch_ohlcv_result(["XLK"], period="2mo", provider="massive")

    assert result.data == {}
    assert result.fresh_cache_hits == ()
    assert result.missing == ("XLK",)
    assert result.provider_by_ticker == {}
    assert result.warnings == ("Missing OHLCV for 1 symbol after massive fetch.",)


def test_fetch_ohlcv_result_can_bypass_fresh_cache_for_validation(tmp_path, monkeypatch):
    from src import ohlcv_store

    cache_path = tmp_path / "ohlcv.duckdb"
    today = pd.Timestamp.today().normalize()
    fixture_end = pd.offsets.BDay().rollback(today)
    cached_dates = pd.bdate_range(end=fixture_end, periods=50)
    cached_frame = pd.DataFrame(
        {
            "open": range(50),
            "high": range(1, 51),
            "low": range(50),
            "close": range(100, 150),
            "volume": [1_000_000] * 50,
            "adj_close": range(100, 150),
        },
        index=cached_dates,
    )
    provider_frame = cached_frame.copy()
    provider_frame["close"] = provider_frame["close"] + 1000
    provider_frame["adj_close"] = provider_frame["close"]
    ohlcv_store.write_cached_ohlcv({"XLK": cached_frame}, cache_path=cache_path, provider="unit-test")
    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")

    def fake_download(**kwargs):
        columns = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
        )
        raw = pd.DataFrame(index=provider_frame.index, columns=columns)
        for source, column in [
            ("open", "Open"),
            ("high", "High"),
            ("low", "Low"),
            ("close", "Close"),
            ("adj_close", "Adj Close"),
            ("volume", "Volume"),
        ]:
            raw[(column, "XLK")] = provider_frame[source]
        return raw

    monkeypatch.setattr(data.yf, "download", fake_download)

    result = data.fetch_ohlcv_result(["XLK"], period="2mo", provider="yfinance", use_cache=False)

    assert result.fresh_cache_hits == ()
    assert result.fetched == ("XLK",)
    assert result.data["XLK"]["close"].iloc[-1] == provider_frame["close"].iloc[-1]


def test_fetch_ohlcv_result_force_refresh_bypasses_cache_read_and_updates_cache(tmp_path, monkeypatch):
    from src import ohlcv_store

    cache_path = tmp_path / "ohlcv.duckdb"
    today = pd.Timestamp.today().normalize()
    fixture_end = pd.offsets.BDay().rollback(today)
    cached_dates = pd.bdate_range(end=fixture_end, periods=50)
    cached_frame = pd.DataFrame(
        {
            "open": range(50),
            "high": range(1, 51),
            "low": range(50),
            "close": range(100, 150),
            "volume": [1_000_000] * 50,
            "adj_close": range(100, 150),
        },
        index=cached_dates,
    )
    provider_frame = cached_frame.copy()
    provider_frame["close"] = provider_frame["close"] + 1000
    provider_frame["adj_close"] = provider_frame["close"]
    ohlcv_store.write_cached_ohlcv({"XLK": cached_frame}, cache_path=cache_path, provider="unit-test")
    monkeypatch.setenv("OHLCV_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("OHLCV_CACHE_ENABLED", "true")

    def fake_download(**kwargs):
        columns = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
        )
        raw = pd.DataFrame(index=provider_frame.index, columns=columns)
        for source, column in [
            ("open", "Open"),
            ("high", "High"),
            ("low", "Low"),
            ("close", "Close"),
            ("adj_close", "Adj Close"),
            ("volume", "Volume"),
        ]:
            raw[(column, "XLK")] = provider_frame[source]
        return raw

    monkeypatch.setattr(data.yf, "download", fake_download)

    result = data.fetch_ohlcv_result(["XLK"], period="2mo", provider="yfinance", force_refresh=True)
    refreshed_cache = ohlcv_store.read_cached_ohlcv(["XLK"], period="2mo", cache_path=cache_path)

    assert result.cache_refresh_forced is True
    assert result.fresh_cache_hits == ()
    assert result.fetched == ("XLK",)
    assert result.data["XLK"]["close"].iloc[-1] == provider_frame["close"].iloc[-1]
    assert refreshed_cache["XLK"]["close"].iloc[-1] == provider_frame["close"].iloc[-1]


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


def test_fetch_ohlcv_massive_preserves_lowercase_request_as_provider_symbol(monkeypatch):
    monkeypatch.setenv("OHLCV_PROVIDER", "massive")
    monkeypatch.setenv("MASSIVE_API_KEY", "secret")
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
        return FakeResponse()

    monkeypatch.setattr(
        data,
        "requests",
        SimpleNamespace(get=fake_get, RequestException=RuntimeError),
        raising=False,
    )

    out = data.fetch_ohlcv(["xlk"], provider="massive")

    assert list(out) == ["XLK"]
    assert len(out["XLK"]) == 40
