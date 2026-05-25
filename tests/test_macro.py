from __future__ import annotations

import pandas as pd

from src import macro


def _monthly_ohlcv(values: list[float]) -> pd.DataFrame:
    index = pd.date_range("2024-01-31", periods=len(values), freq="ME")
    return pd.DataFrame(
        {
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "adj_close": values,
            "volume": [1_000_000] * len(values),
        },
        index=index,
    )


def test_assess_regime_uses_fred_cache_when_available():
    bench = _monthly_ohlcv([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112])
    indpro = pd.Series(
        [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 104, 105, 106],
        index=pd.date_range("2025-01-31", periods=15, freq="ME"),
    )
    fred_cache = {
        "INDPRO": indpro,
        "T10Y2Y": pd.Series([0.75], index=[pd.Timestamp("2026-03-31")]),
        "RECPROUSM156N": pd.Series([1.0], index=[pd.Timestamp("2026-03-31")]),
        "NFCI": pd.Series([-0.20], index=[pd.Timestamp("2026-03-31")]),
    }

    regime = macro.assess_regime(bench, fred_cache=fred_cache)

    assert regime.fred_used is True
    assert regime.phase_hint == "EARLY"
    assert regime.yield_curve_positive is True
    assert regime.indpro_yoy is not None


def test_assess_regime_falls_back_when_fred_cache_is_empty():
    bench = _monthly_ohlcv([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112])
    tnx = _monthly_ohlcv([4.0])
    irx = _monthly_ohlcv([5.0])

    regime = macro.assess_regime(bench, tnx_df=tnx, irx_df=irx, fred_cache={})

    assert regime.fred_used is False
    assert regime.phase_hint == "LATE"
    assert regime.yield_curve_positive is False
