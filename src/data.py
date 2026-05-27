"""Data ingestion layer - yfinance by default, Massive when configured.

Public API:
    fetch_ohlcv(tickers, period="3y") -> dict[ticker -> DataFrame]
    to_weekly(df) -> DataFrame   # resamples daily to weekly (Fri close)
    to_monthly(df) -> DataFrame  # resamples daily to monthly
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import os
import time
from typing import Iterable

import pandas as pd
import requests
import yfinance as yf

from .ohlcv_store import ohlcv_cache_enabled, read_cached_ohlcv, write_cached_ohlcv


MASSIVE_AGGS_URL_TEMPLATE = (
    "https://api.massive.com/v2/aggs/ticker/{ticker}/range/"
    "{multiplier}/{timespan}/{from_date}/{to_date}"
)
PROVIDER_RETRY_ATTEMPTS = 2
PROVIDER_RETRY_BACKOFF_SECONDS = 0.10


@dataclass(frozen=True)
class OhlcvFetchResult:
    data: dict[str, pd.DataFrame]
    provider: str
    fetched: tuple[str, ...] = ()
    fresh_cache_hits: tuple[str, ...] = ()
    stale_cache_hits: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    used_stale_cache: bool = False
    provider_retry_count: int = 0
    cache_refresh_forced: bool = False


@dataclass(frozen=True)
class _ProviderFetchResult:
    data: dict[str, pd.DataFrame]
    retry_count: int = 0


def _provider_retry_sleep(seconds: float) -> None:
    time.sleep(seconds)


def _resolve_secret(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        import streamlit as st  # type: ignore
        from streamlit.errors import StreamlitSecretNotFoundError  # type: ignore

        if hasattr(st, "secrets"):
            try:
                secret = st.secrets.get(name)
                if secret is not None:
                    text = str(secret).strip()
                    if text:
                        return text
            except (KeyError, StreamlitSecretNotFoundError):
                pass
    except ImportError:
        pass
    return None


def _select_ohlcv_provider(provider: str | None) -> str:
    configured = provider or _resolve_secret("OHLCV_PROVIDER") or "yfinance"
    normalized = str(configured).strip().lower()
    if normalized == "auto":
        return "massive" if _resolve_secret("MASSIVE_API_KEY") else "yfinance"
    if normalized in {"massive", "polygon"}:
        return "massive"
    return "yfinance"


def _period_to_date_range(period: str, today: date | None = None) -> tuple[str, str]:
    end = today or date.today()
    text = str(period).strip().lower()
    if text == "max":
        return "2003-01-01", end.isoformat()
    try:
        if text.endswith("mo"):
            months = int(text[:-2])
            return (end - timedelta(days=months * 31)).isoformat(), end.isoformat()
        if text.endswith("y"):
            years = int(text[:-1])
            return (end - timedelta(days=years * 365 + years // 4)).isoformat(), end.isoformat()
        if text.endswith("d"):
            days = int(text[:-1])
            return (end - timedelta(days=days)).isoformat(), end.isoformat()
    except ValueError:
        pass
    return "2003-01-01", end.isoformat()


def _massive_interval(interval: str) -> tuple[int, str]:
    normalized = str(interval).strip().lower()
    if normalized in {"1d", "1day", "day"}:
        return 1, "day"
    raise ValueError(f"Unsupported Massive OHLCV interval: {interval}")


def _massive_ssl_verify_setting() -> bool | None:
    configured = _resolve_secret("MASSIVE_VERIFY_SSL")
    if configured is None:
        return None
    normalized = configured.strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        try:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except ImportError:
            pass
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return None


def _flatten(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """yfinance returns a multi-index when multiple tickers are requested.
    Slice and return a clean OHLCV DataFrame for a single ticker."""
    if isinstance(df.columns, pd.MultiIndex):
        try:
            sub = df.xs(ticker, level=1, axis=1)
        except KeyError:
            return pd.DataFrame()
    else:
        sub = df
    sub = sub.rename(columns=str.lower)
    keep = [c for c in ["open", "high", "low", "close", "adj close", "volume"] if c in sub.columns]
    sub = sub[keep].copy()
    if "adj close" in sub.columns:
        sub["adj_close"] = sub["adj close"]
        sub = sub.drop(columns=["adj close"])
    sub.index = pd.to_datetime(sub.index)
    return sub.dropna(how="all")


def _frame_from_massive_results(results) -> pd.DataFrame:
    rows = []
    if not isinstance(results, list):
        return pd.DataFrame()
    for bar in results:
        if not isinstance(bar, dict):
            continue
        timestamp = bar.get("t")
        try:
            close = float(bar["c"])
            rows.append(
                {
                    "date": pd.to_datetime(timestamp, unit="ms", utc=True).tz_convert(None),
                    "open": float(bar["o"]),
                    "high": float(bar["h"]),
                    "low": float(bar["l"]),
                    "close": close,
                    "volume": float(bar["v"]),
                    "adj_close": close,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .set_index("date")
        .sort_index()[["open", "high", "low", "close", "volume", "adj_close"]]
        .dropna(how="all")
    )


def _fetch_massive_ohlcv(
    tickers: list[str],
    period: str = "3y",
    interval: str = "1d",
    api_key: str | None = None,
) -> _ProviderFetchResult:
    token = api_key or _resolve_secret("MASSIVE_API_KEY")
    if not token:
        return _ProviderFetchResult({})
    try:
        multiplier, timespan = _massive_interval(interval)
        from_date, to_date = _period_to_date_range(period)
    except ValueError:
        return _ProviderFetchResult({})

    out: dict[str, pd.DataFrame] = {}
    retry_count = 0
    for ticker in tickers:
        symbol = str(ticker).upper()
        url = MASSIVE_AGGS_URL_TEMPLATE.format(
            ticker=symbol,
            multiplier=multiplier,
            timespan=timespan,
            from_date=from_date,
            to_date=to_date,
        )
        payload = None
        for attempt in range(1, PROVIDER_RETRY_ATTEMPTS + 1):
            try:
                request_options = {
                    "params": {"adjusted": "true", "sort": "asc", "limit": 50000},
                    "headers": {"Authorization": f"Bearer {token}"},
                    "timeout": 30,
                }
                verify = _massive_ssl_verify_setting()
                if verify is not None:
                    request_options["verify"] = verify
                response = requests.get(url, **request_options)
                response.raise_for_status()
                payload = response.json()
                break
            except (requests.RequestException, ValueError):
                if attempt >= PROVIDER_RETRY_ATTEMPTS:
                    break
                retry_count += 1
                _provider_retry_sleep(PROVIDER_RETRY_BACKOFF_SECONDS * attempt)
        if payload is None:
            continue
        if not isinstance(payload, dict):
            continue
        df = _frame_from_massive_results(payload.get("results", []))
        if not df.empty and len(df) > 30:
            out[symbol] = df
    return _ProviderFetchResult(out, retry_count)


def _fetch_yfinance_ohlcv(
    tickers: list[str],
    period: str = "3y",
    interval: str = "1d",
) -> _ProviderFetchResult:
    retry_count = 0
    raw = pd.DataFrame()
    for attempt in range(1, PROVIDER_RETRY_ATTEMPTS + 1):
        try:
            raw = yf.download(
                tickers=tickers,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
            )
            break
        except Exception:
            if attempt >= PROVIDER_RETRY_ATTEMPTS:
                return _ProviderFetchResult({}, retry_count)
            retry_count += 1
            _provider_retry_sleep(PROVIDER_RETRY_BACKOFF_SECONDS * attempt)
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = _flatten(raw, t)
            if not df.empty and len(df) > 30:
                out[t] = df
        except Exception:
            continue
    return _ProviderFetchResult(out, retry_count)


def fetch_ohlcv(
    tickers: Iterable[str],
    period: str = "3y",
    interval: str = "1d",
    provider: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for a list of tickers from the configured provider.

    Parameters
    ----------
    tickers : iterable of ticker strings
    period  : provider period string (e.g. '3y', 'max')
    interval: '1d' for daily
    provider: 'yfinance', 'massive', or 'auto' (defaults to OHLCV_PROVIDER or yfinance)

    Returns
    -------
    dict mapping ticker -> DataFrame indexed by date with columns
    [open, high, low, close, volume, adj_close].
    """
    return fetch_ohlcv_result(tickers, period=period, interval=interval, provider=provider).data


def _warning_symbol_text(count: int) -> str:
    return "symbol" if count == 1 else "symbols"


def _provider_retry_warning(provider_name: str, retry_count: int) -> str:
    request_text = "request" if retry_count == 1 else "requests"
    return f"Provider retry recovered {retry_count} {provider_name} {request_text} before data loaded."


def fetch_ohlcv_result(
    tickers: Iterable[str],
    period: str = "3y",
    interval: str = "1d",
    provider: str | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> OhlcvFetchResult:
    """Fetch OHLCV and return provider/cache metadata for operator status UI."""
    tickers = list(dict.fromkeys(tickers))  # de-dup preserving order
    provider_name = _select_ohlcv_provider(provider)
    cached: dict[str, pd.DataFrame] = {}
    cache_enabled = use_cache and ohlcv_cache_enabled()
    if cache_enabled and not force_refresh:
        try:
            cached = read_cached_ohlcv(tickers, period=period, interval=interval)
        except Exception:
            cached = {}
    missing = [ticker for ticker in tickers if ticker not in cached]
    fetched: dict[str, pd.DataFrame] = {}
    provider_retry_count = 0
    yfinance_fallback: dict[str, pd.DataFrame] = {}
    if missing:
        if provider_name == "massive":
            provider_result = _fetch_massive_ohlcv(missing, period=period, interval=interval)
        else:
            provider_result = _fetch_yfinance_ohlcv(missing, period=period, interval=interval)
        fetched = provider_result.data
        provider_retry_count = provider_result.retry_count
        if fetched and cache_enabled:
            try:
                write_cached_ohlcv(fetched, provider=provider_name, interval=interval)
            except Exception:
                pass
        provider_misses_after_primary = [
            ticker for ticker in missing if ticker not in fetched and str(ticker).upper() not in fetched
        ]
        if provider_name == "massive" and provider_misses_after_primary:
            fallback_result = _fetch_yfinance_ohlcv(
                provider_misses_after_primary,
                period=period,
                interval=interval,
            )
            yfinance_fallback = fallback_result.data
            if yfinance_fallback:
                fetched = {**fetched, **yfinance_fallback}
                if cache_enabled:
                    try:
                        write_cached_ohlcv(yfinance_fallback, provider="yfinance", interval=interval)
                    except Exception:
                        pass
    stale_cached: dict[str, pd.DataFrame] = {}
    provider_misses = [ticker for ticker in missing if ticker not in fetched and str(ticker).upper() not in fetched]
    if provider_misses and cache_enabled:
        try:
            stale_cached = read_cached_ohlcv(
                provider_misses,
                period=period,
                interval=interval,
                allow_stale=True,
            )
        except Exception:
            stale_cached = {}
    combined = {**cached, **stale_cached, **fetched}
    ordered = {}
    for ticker in tickers:
        key = ticker if ticker in combined else str(ticker).upper()
        if key in combined and key not in ordered:
            ordered[key] = combined[key]
    missing_after_fallback = []
    for ticker in tickers:
        key = ticker if ticker in ordered else str(ticker).upper()
        if key not in ordered:
            missing_after_fallback.append(str(ticker))

    warnings: list[str] = []
    if provider_retry_count and fetched:
        warnings.append(_provider_retry_warning(provider_name, provider_retry_count))
    if yfinance_fallback:
        count = len(yfinance_fallback)
        warnings.append(
            f"Massive unavailable for {count} {_warning_symbol_text(count)}; "
            "yfinance fallback used for live OHLCV."
        )
    if stale_cached:
        count = len(stale_cached)
        warnings.append(
            f"Using stale cached OHLCV for {count} {_warning_symbol_text(count)} "
            f"because {provider_name} returned no fresh rows."
        )
    if missing_after_fallback:
        count = len(missing_after_fallback)
        warnings.append(
            f"Missing OHLCV for {count} {_warning_symbol_text(count)} after {provider_name} fetch."
        )

    return OhlcvFetchResult(
        data=ordered,
        provider=provider_name,
        fetched=tuple(key for key in ordered if key in fetched),
        fresh_cache_hits=tuple(key for key in ordered if key in cached),
        stale_cache_hits=tuple(key for key in ordered if key in stale_cached),
        missing=tuple(missing_after_fallback),
        warnings=tuple(warnings),
        used_stale_cache=bool(stale_cached),
        provider_retry_count=provider_retry_count,
        cache_refresh_forced=bool(force_refresh),
    )


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (Fri close)."""
    if df.empty:
        return df
    rules = {
        "open":      "first",
        "high":      "max",
        "low":       "min",
        "close":     "last",
        "adj_close": "last",
        "volume":    "sum",
    }
    keep = {k: v for k, v in rules.items() if k in df.columns}
    return df.resample("W-FRI").agg(keep).dropna(how="all")


def to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to monthly (month-end)."""
    if df.empty:
        return df
    rules = {
        "open":      "first",
        "high":      "max",
        "low":       "min",
        "close":     "last",
        "adj_close": "last",
        "volume":    "sum",
    }
    keep = {k: v for k, v in rules.items() if k in df.columns}
    return df.resample("ME").agg(keep).dropna(how="all")


def close_price(df: pd.DataFrame) -> pd.Series:
    """Return the adjusted close as a Series (falls back to close)."""
    if "adj_close" in df.columns:
        return df["adj_close"]
    return df["close"]
