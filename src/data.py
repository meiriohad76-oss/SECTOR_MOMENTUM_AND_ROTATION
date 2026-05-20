"""Data ingestion layer - yfinance by default, Massive when configured.

Public API:
    fetch_ohlcv(tickers, period="3y") -> dict[ticker -> DataFrame]
    to_weekly(df) -> DataFrame   # resamples daily to weekly (Fri close)
    to_monthly(df) -> DataFrame  # resamples daily to monthly
"""
from __future__ import annotations

from datetime import date, timedelta
import os
from typing import Iterable

import pandas as pd
import requests
import yfinance as yf


MASSIVE_AGGS_URL_TEMPLATE = (
    "https://api.massive.com/v2/aggs/ticker/{ticker}/range/"
    "{multiplier}/{timespan}/{from_date}/{to_date}"
)


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
) -> dict[str, pd.DataFrame]:
    token = api_key or _resolve_secret("MASSIVE_API_KEY")
    if not token:
        return {}
    try:
        multiplier, timespan = _massive_interval(interval)
        from_date, to_date = _period_to_date_range(period)
    except ValueError:
        return {}

    out: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        symbol = str(ticker).upper()
        url = MASSIVE_AGGS_URL_TEMPLATE.format(
            ticker=symbol,
            multiplier=multiplier,
            timespan=timespan,
            from_date=from_date,
            to_date=to_date,
        )
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
        except (requests.RequestException, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        df = _frame_from_massive_results(payload.get("results", []))
        if not df.empty and len(df) > 30:
            out[symbol] = df
    return out


def _fetch_yfinance_ohlcv(
    tickers: list[str],
    period: str = "3y",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
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
    except Exception:
        return {}
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = _flatten(raw, t)
            if not df.empty and len(df) > 30:
                out[t] = df
        except Exception:
            continue
    return out


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
    [open, high, low, close, adj_close, volume].
    """
    tickers = list(dict.fromkeys(tickers))  # de-dup preserving order
    if _select_ohlcv_provider(provider) == "massive":
        return _fetch_massive_ohlcv(tickers, period=period, interval=interval)
    return _fetch_yfinance_ohlcv(tickers, period=period, interval=interval)


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
