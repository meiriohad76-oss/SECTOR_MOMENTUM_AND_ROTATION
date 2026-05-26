"""Deterministic OHLCV fixtures for browser QA runs."""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
import pandas as pd

from .data import OhlcvFetchResult


def browser_qa_ohlcv_result(tickers: Iterable[str], period: str = "3y") -> OhlcvFetchResult:
    """Return complete local OHLCV data so browser QA never depends on providers."""
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=_period_rows(period))
    frames = {str(ticker).upper(): _ticker_frame(str(ticker).upper(), dates) for ticker in dict.fromkeys(tickers)}
    return OhlcvFetchResult(data=frames, provider="browser_qa_fixture")


def _period_rows(period: str) -> int:
    text = str(period).strip().lower()
    if text.endswith("y"):
        try:
            return max(260, int(text[:-1]) * 260)
        except ValueError:
            pass
    if text.endswith("mo"):
        try:
            return max(60, int(text[:-2]) * 22)
        except ValueError:
            pass
    return 780


def _ticker_frame(ticker: str, dates: pd.DatetimeIndex) -> pd.DataFrame:
    seed = int(hashlib.sha256(ticker.encode("utf-8")).hexdigest()[:8], 16)
    phase = (seed % 31) / 5.0
    base = 60.0 + (seed % 80)
    slope = 0.0003 + ((seed % 17) / 100_000)
    if ticker in {"BIL", "^IRX"}:
        slope = 0.00008
    if ticker in {"SPY", "ACWI"}:
        slope = 0.00045
    x = np.arange(len(dates), dtype=float)
    wave = np.sin((x / 23.0) + phase) * 0.018
    drift = 1.0 + slope * x
    close = base * drift * (1.0 + wave)
    open_ = close * (1.0 + np.sin((x / 17.0) + phase) * 0.002)
    high = np.maximum(open_, close) * 1.012
    low = np.minimum(open_, close) * 0.988
    volume = 800_000 + ((seed % 11) * 40_000) + (np.cos(x / 19.0 + phase) * 30_000)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.maximum(volume, 100_000),
            "adj_close": close,
        },
        index=dates,
    )
