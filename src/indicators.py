"""Pillars 1-5 + breadth. Inputs: daily OHLCV from data.fetch_ohlcv."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .data import close_price, to_weekly, to_monthly


def momentum_12_1(df):
    p = close_price(df)
    if len(p) < 252:
        return None
    return float(p.iloc[-21] / p.iloc[-252] - 1.0)


def faber_signal(df):
    m = to_monthly(df)
    p = close_price(m)
    if len(p) < 11:
        return None
    sma10 = p.rolling(10).mean()
    return int(p.iloc[-1] > sma10.iloc[-1])


@dataclass
class StageResult:
    stage: int
    above_30wma: bool
    slope_positive: bool
    mansfield_rs: float
    sma30w: float
    price: float


def stage_analysis(df, bench_df):
    w = to_weekly(df)
    wb = to_weekly(bench_df)
    if len(w) < 35 or len(wb) < 53:
        return None
    p = close_price(w)
    pb = close_price(wb)
    sma30 = p.rolling(30).mean()
    if pd.isna(sma30.iloc[-1]):
        return None
    above = p.iloc[-1] > sma30.iloc[-1]
    slope = (sma30.iloc[-1] - sma30.iloc[-6]) / 5
    ratio = p / pb.reindex(p.index).ffill()
    if len(ratio) < 53 or pd.isna(ratio.iloc[-53]):
        return None
    mansfield = float((ratio.iloc[-1] / ratio.iloc[-53] - 1.0) * 100)
    if above and slope > 0 and mansfield > 0:
        stage = 2
    elif above and (slope <= 0 or mansfield <= 0):
        stage = 3
    elif not above and slope < 0 and mansfield < 0:
        stage = 4
    else:
        stage = 1
    return StageResult(
        stage=stage,
        above_30wma=bool(above),
        slope_positive=bool(slope > 0),
        mansfield_rs=mansfield,
        sma30w=float(sma30.iloc[-1]),
        price=float(p.iloc[-1]),
    )


def antonacci_absolute(df, bil_df):
    p = close_price(df)
    pb = close_price(bil_df)
    if len(p) < 252 or len(pb) < 252:
        return None
    ret_asset = p.iloc[-1] / p.iloc[-252] - 1.0
    ret_bil = pb.iloc[-1] / pb.iloc[-252] - 1.0
    return int(ret_asset > ret_bil)


@dataclass
class RRGResult:
    rs_ratio: float
    rs_momentum: float
    quadrant: str


def rrg(df, bench_df):
    w = to_weekly(df)
    wb = to_weekly(bench_df)
    if len(w) < 60 or len(wb) < 60:
        return None
    p = close_price(w)
    pb = close_price(wb).reindex(p.index).ffill()
    rs = 100 * p / pb
    rs_sma = rs.rolling(63).mean()
    rs_std = rs.rolling(252, min_periods=60).std()
    if pd.isna(rs_sma.iloc[-1]) or pd.isna(rs_std.iloc[-1]) or rs_std.iloc[-1] == 0:
        return None
    rs_ratio = 100 + (rs - rs_sma) / rs_std * 10
    rs_ratio_sma = rs_ratio.rolling(5).mean()
    rs_ratio_std = rs_ratio.rolling(21).std()
    if pd.isna(rs_ratio_sma.iloc[-1]) or pd.isna(rs_ratio_std.iloc[-1]) or rs_ratio_std.iloc[-1] == 0:
        return None
    rs_mom = 100 + (rs_ratio - rs_ratio_sma) / rs_ratio_std * 10
    r = float(rs_ratio.iloc[-1])
    m = float(rs_mom.iloc[-1])
    if r >= 100 and m >= 100:
        q = "Leading"
    elif r >= 100 and m < 100:
        q = "Weakening"
    elif r < 100 and m < 100:
        q = "Lagging"
    else:
        q = "Improving"
    return RRGResult(rs_ratio=r, rs_momentum=m, quadrant=q)


def breadth_proxy(df):
    p = close_price(df)
    if len(p) < 100:
        return None
    sma50 = p.rolling(50).mean()
    window = (p.iloc[-50:] > sma50.iloc[-50:])
    return float(window.mean())


def compute_all_indicators(ohlcv, bench_ticker="SPY", bil_ticker="BIL"):
    if bench_ticker not in ohlcv or bil_ticker not in ohlcv:
        raise ValueError(f"Benchmark {bench_ticker} or T-bill {bil_ticker} missing from data.")
    bench = ohlcv[bench_ticker]
    bil = ohlcv[bil_ticker]
    rows = []
    for tkr, df in ohlcv.items():
        if tkr == bil_ticker:
            continue
        if str(tkr).startswith("^"):
            continue
        m121 = momentum_12_1(df)
        fab = faber_signal(df)
        st = stage_analysis(df, bench)
        ant = antonacci_absolute(df, bil)
        r = rrg(df, bench)
        b = breadth_proxy(df)
        rows.append({
            "ticker": tkr,
            "mom_12_1": m121,
            "faber": fab,
            "stage": st.stage if st else None,
            "above_30wma": st.above_30wma if st else None,
            "ma_slope_pos": st.slope_positive if st else None,
            "mansfield_rs": st.mansfield_rs if st else None,
            "antonacci": ant,
            "rs_ratio": r.rs_ratio if r else None,
            "rs_momentum": r.rs_momentum if r else None,
            "rrg_quadrant": r.quadrant if r else None,
            "breadth_50d": b,
        })
    return pd.DataFrame(rows).set_index("ticker")
