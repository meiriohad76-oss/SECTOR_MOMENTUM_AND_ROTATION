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

from .ohlcv_store import ohlcv_cache_enabled, read_cached_ohlcv_metadata, write_cached_ohlcv
from .tls import ensure_system_trust_store

ensure_system_trust_store()


MASSIVE_AGGS_URL_TEMPLATE = (
    "https://api.massive.com/v2/aggs/ticker/{ticker}/range/"
    "{multiplier}/{timespan}/{from_date}/{to_date}"
)
FRED_PUBLIC_CSV_URL_TEMPLATE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
MACRO_OHLCV_FRED_FALLBACKS = {
    "^VIX": {"series_id": "VIXCLS", "scale": 1.0},
    "^TNX": {"series_id": "DGS10", "scale": 1.0},
    "^IRX": {"series_id": "DGS3MO", "scale": 1.0},
}
PROVIDER_RETRY_ATTEMPTS = 2
PROVIDER_RETRY_BACKOFF_SECONDS = 0.10
PUBLIC_FRED_MACRO_TIMEOUT_SECONDS = 6
PUBLIC_FRED_MACRO_ATTEMPTS = 1


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
    source_by_ticker: dict[str, str] | None = None
    provider_by_ticker: dict[str, str] | None = None


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


def _fred_public_series_to_ohlcv_frame(series: pd.Series, *, scale: float = 1.0) -> pd.DataFrame:
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return pd.DataFrame()
    values = cleaned.astype(float) * float(scale)
    frame = pd.DataFrame(
        {
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "volume": 0.0,
            "adj_close": values,
        },
        index=pd.to_datetime(values.index),
    )
    return frame.dropna(how="all")


def _fetch_public_fred_macro_ohlcv(
    tickers: list[str],
    period: str = "3y",
    interval: str = "1d",
) -> _ProviderFetchResult:
    if str(interval).strip().lower() not in {"1d", "1day", "day"}:
        return _ProviderFetchResult({})
    try:
        from_date, to_date = _period_to_date_range(period)
        start = pd.Timestamp(from_date)
        end = pd.Timestamp(to_date) + pd.Timedelta(days=1)
    except Exception:
        start = pd.Timestamp("1900-01-01")
        end = pd.Timestamp.today() + pd.Timedelta(days=1)

    out: dict[str, pd.DataFrame] = {}
    retry_count = 0
    for ticker in tickers:
        symbol = str(ticker).upper()
        config = MACRO_OHLCV_FRED_FALLBACKS.get(symbol)
        if not config:
            continue
        series_id = str(config["series_id"])
        url = FRED_PUBLIC_CSV_URL_TEMPLATE.format(series_id=series_id)
        raw_text = ""
        for attempt in range(1, PUBLIC_FRED_MACRO_ATTEMPTS + 1):
            try:
                response = requests.get(url, timeout=PUBLIC_FRED_MACRO_TIMEOUT_SECONDS)
                response.raise_for_status()
                raw_text = response.text
                break
            except (requests.RequestException, ValueError):
                if attempt >= PUBLIC_FRED_MACRO_ATTEMPTS:
                    break
                retry_count += 1
                _provider_retry_sleep(PROVIDER_RETRY_BACKOFF_SECONDS * attempt)
        if not raw_text:
            continue
        try:
            from io import StringIO

            raw = pd.read_csv(StringIO(raw_text))
            if "observation_date" in raw.columns:
                date_column = "observation_date"
            elif "DATE" in raw.columns:
                date_column = "DATE"
            else:
                date_column = str(raw.columns[0])
            value_column = series_id if series_id in raw.columns else str(raw.columns[-1])
            series = pd.Series(
                raw[value_column].replace(".", pd.NA).to_numpy(),
                index=pd.to_datetime(raw[date_column], errors="coerce"),
            ).dropna()
            frame = _fred_public_series_to_ohlcv_frame(series, scale=float(config.get("scale", 1.0)))
            frame = frame[(frame.index >= start) & (frame.index <= end)]
            if not frame.empty and len(frame) > 30:
                out[symbol] = frame
        except (KeyError, TypeError, ValueError, pd.errors.ParserError):
            continue
    return _ProviderFetchResult(out, retry_count)


def _fetch_configured_fred_macro_ohlcv(
    tickers: list[str],
    period: str = "3y",
    interval: str = "1d",
) -> _ProviderFetchResult:
    if str(interval).strip().lower() not in {"1d", "1day", "day"}:
        return _ProviderFetchResult({})
    token = _resolve_secret("FRED_API_KEY")
    if not token:
        return _ProviderFetchResult({})
    try:
        from fredapi import Fred  # type: ignore
    except ImportError:
        return _ProviderFetchResult({})
    try:
        from_date, to_date = _period_to_date_range(period)
    except Exception:
        from_date, to_date = "1900-01-01", date.today().isoformat()
    try:
        client = Fred(token)
    except Exception:
        return _ProviderFetchResult({})

    out: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        symbol = str(ticker).upper()
        config = MACRO_OHLCV_FRED_FALLBACKS.get(symbol)
        if not config:
            continue
        series_id = str(config["series_id"])
        try:
            series = client.get_series(series_id, observation_start=from_date, observation_end=to_date)
            frame = _fred_public_series_to_ohlcv_frame(series, scale=float(config.get("scale", 1.0)))
            if not frame.empty and len(frame) > 30:
                out[symbol] = frame
        except Exception:
            continue
    return _ProviderFetchResult(out)


def _fetch_fred_macro_ohlcv(
    tickers: list[str],
    period: str = "3y",
    interval: str = "1d",
) -> _ProviderFetchResult:
    configured_result = _fetch_configured_fred_macro_ohlcv(tickers, period=period, interval=interval)
    missing = [
        ticker
        for ticker in tickers
        if ticker not in configured_result.data and str(ticker).upper() not in configured_result.data
    ]
    if not missing:
        return configured_result
    public_result = _fetch_public_fred_macro_ohlcv(missing, period=period, interval=interval)
    return _ProviderFetchResult(
        {**configured_result.data, **public_result.data},
        configured_result.retry_count + public_result.retry_count,
    )


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


def _cache_provider_allowed(requested_provider: str, ticker: str, cached_provider: object) -> bool:
    provider = str(cached_provider or "").strip().lower()
    if not provider:
        return False
    if requested_provider == "massive":
        if provider == "massive":
            return True
        return provider in {"fred_macro", "fred_public_macro"} and str(ticker).upper() in MACRO_OHLCV_FRED_FALLBACKS
    if requested_provider == "yfinance":
        return provider in {"yfinance", "unit-test"}
    return provider == requested_provider


def _filter_cache_metadata_by_provider(
    metadata: dict[str, dict[str, object]],
    *,
    requested_provider: str,
) -> dict[str, dict[str, object]]:
    return {
        ticker: meta
        for ticker, meta in metadata.items()
        if _cache_provider_allowed(requested_provider, ticker, meta.get("provider"))
    }


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
    cached_meta: dict[str, dict[str, object]] = {}
    cache_enabled = use_cache and ohlcv_cache_enabled()
    if cache_enabled and not force_refresh:
        try:
            cached_meta = read_cached_ohlcv_metadata(tickers, period=period, interval=interval)
            cached_meta = _filter_cache_metadata_by_provider(
                cached_meta,
                requested_provider=provider_name,
            )
            cached = {
                ticker: meta["frame"]
                for ticker, meta in cached_meta.items()
                if isinstance(meta.get("frame"), pd.DataFrame)
            }
        except Exception:
            cached = {}
            cached_meta = {}
    missing = [ticker for ticker in tickers if ticker not in cached]
    fetched: dict[str, pd.DataFrame] = {}
    provider_retry_count = 0
    fred_public_fallback: dict[str, pd.DataFrame] = {}
    attempted_fred_public: set[str] = set()
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
            macro_misses = [
                ticker
                for ticker in provider_misses_after_primary
                if str(ticker).upper() in MACRO_OHLCV_FRED_FALLBACKS
            ]
            if macro_misses:
                attempted_fred_public.update(str(ticker).upper() for ticker in macro_misses)
                fred_result = _fetch_fred_macro_ohlcv(
                    macro_misses,
                    period=period,
                    interval=interval,
                )
                fred_public_fallback = fred_result.data
                provider_retry_count += fred_result.retry_count
                if fred_public_fallback:
                    fetched = {**fetched, **fred_public_fallback}
                    if cache_enabled:
                        try:
                            write_cached_ohlcv(fred_public_fallback, provider="fred_macro", interval=interval)
                        except Exception:
                            pass
            provider_misses_after_primary = [
                ticker for ticker in provider_misses_after_primary
                if ticker not in fetched and str(ticker).upper() not in fetched
            ]
        provider_misses_after_yfinance = [
            ticker for ticker in missing
            if ticker not in fetched
            and str(ticker).upper() not in fetched
            and str(ticker).upper() not in attempted_fred_public
        ]
        if provider_misses_after_yfinance:
            fred_result = _fetch_fred_macro_ohlcv(
                provider_misses_after_yfinance,
                period=period,
                interval=interval,
            )
            fred_public_fallback = fred_result.data
            provider_retry_count += fred_result.retry_count
            if fred_public_fallback:
                fetched = {**fetched, **fred_public_fallback}
                if cache_enabled:
                    try:
                        write_cached_ohlcv(fred_public_fallback, provider="fred_macro", interval=interval)
                    except Exception:
                        pass
    stale_cached: dict[str, pd.DataFrame] = {}
    stale_cached_meta: dict[str, dict[str, object]] = {}
    provider_misses = [ticker for ticker in missing if ticker not in fetched and str(ticker).upper() not in fetched]
    if provider_misses and cache_enabled:
        try:
            stale_cached_meta = read_cached_ohlcv_metadata(
                provider_misses,
                period=period,
                interval=interval,
                allow_stale=True,
            )
            stale_cached_meta = _filter_cache_metadata_by_provider(
                stale_cached_meta,
                requested_provider=provider_name,
            )
            stale_cached = {
                ticker: meta["frame"]
                for ticker, meta in stale_cached_meta.items()
                if isinstance(meta.get("frame"), pd.DataFrame)
            }
        except Exception:
            stale_cached = {}
            stale_cached_meta = {}
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
    failed_fred_public = sorted(
        symbol
        for symbol in attempted_fred_public
        if symbol not in fred_public_fallback
    )
    if failed_fred_public:
        warnings.append(
            "FRED macro fallback unavailable for "
            + ", ".join(failed_fred_public)
            + "."
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

    source_by_ticker: dict[str, str] = {}
    provider_by_ticker: dict[str, str] = {}
    for key in ordered:
        if key in fetched:
            if key in fred_public_fallback:
                source_by_ticker[key] = "fred_macro_live"
                provider_by_ticker[key] = "fred_macro"
            else:
                source_by_ticker[key] = f"{provider_name}_live"
                provider_by_ticker[key] = provider_name
        elif key in cached:
            source_by_ticker[key] = "fresh_cache"
            provider_by_ticker[key] = str(cached_meta.get(key, {}).get("provider") or "unknown")
        elif key in stale_cached:
            source_by_ticker[key] = "stale_cache"
            provider_by_ticker[key] = str(stale_cached_meta.get(key, {}).get("provider") or "unknown")

    if provider_by_ticker:
        provider_mix = sorted(set(provider_by_ticker.values()))
        allowed_massive_mix = provider_name == "massive" and set(provider_mix).issubset({"massive", "fred_macro"})
        if (len(provider_mix) > 1 or provider_name not in provider_mix) and not allowed_massive_mix:
            warnings.append(
                "OHLCV source mix: "
                + ", ".join(
                    f"{provider}={sum(1 for value in provider_by_ticker.values() if value == provider)}"
                    for provider in provider_mix
                )
                + "."
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
        source_by_ticker=source_by_ticker,
        provider_by_ticker=provider_by_ticker,
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
