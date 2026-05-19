from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv_frame_factory():
    def _make(
        days: int = 900,
        start: str = "2020-01-01",
        start_price: float = 100.0,
        daily_return: float = 0.001,
        volume: int = 1_000_000,
    ) -> pd.DataFrame:
        dates = pd.bdate_range(start=start, periods=days)
        steps = np.arange(days, dtype=float)
        close = pd.Series(start_price * np.power(1.0 + daily_return, steps), index=dates)
        open_ = close.shift(1).fillna(close.iloc[0] * 0.999)
        high = pd.concat([open_, close], axis=1).max(axis=1) * 1.01
        low = pd.concat([open_, close], axis=1).min(axis=1) * 0.99
        vol = pd.Series(volume + (steps.astype(int) % 20) * 1_000, index=dates)
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "adj_close": close * 0.995,
                "volume": vol,
            },
            index=dates,
        )

    return _make


@pytest.fixture
def market_ohlcv(ohlcv_frame_factory):
    return {
        "XLK": ohlcv_frame_factory(start_price=100, daily_return=0.0014),
        "XLF": ohlcv_frame_factory(start_price=80, daily_return=0.0007),
        "SOXX": ohlcv_frame_factory(start_price=120, daily_return=0.0018),
        "SPY": ohlcv_frame_factory(start_price=100, daily_return=0.0010),
        "BIL": ohlcv_frame_factory(start_price=90, daily_return=0.0001),
        "^TNX": ohlcv_frame_factory(start_price=40, daily_return=0.0002),
    }
