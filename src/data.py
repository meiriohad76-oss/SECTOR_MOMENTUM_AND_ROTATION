"""Data ingestion layer — yfinance-backed, cached.

Public API:
    fetch_ohlcv(tickers, period="3y") -> dict[ticker -> DataFrame]
    to_weekly(df) -> DataFrame   # resamples daily to weekly (Fri close)
    to_monthly(df) -> DataFrame  # resamples daily to monthly
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf


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


def fetch_ohlcv(
    tickers: Iterable[str],
    period: str = "3y",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for a list of tickers from yfinance.

    Parameters
    ----------
    tickers : iterable of ticker strings
    period  : yfinance period string (e.g. '3y', 'max')
    interval: '1d' for daily

    Returns
    -------
    dict mapping ticker -> DataFrame indexed by date with columns
    [open, high, low, close, adj_close, volume].
    """
    tickers = list(dict.fromkeys(tickers))  # de-dup preserving order
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=True,
        group_by="column",
    )
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = _flatten(raw, t)
            if not df.empty and len(df) > 30:
                out[t] = df
        except Exception:
            continue
    return out


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
