"""Pillar 7 - volume & institutional money flow.

LIVE from OHLCV: CMF, OBV slope, MFI, RVOL, distribution days, OBV divergence.
STUBBED (return neutral until wired): ETF SHO, block trades, dark pool,
short interest, 13F. Toggle STUB_MODE = False after wiring providers.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


STUB_MODE = True


def chaikin_money_flow(df, period=21):
    if len(df) < period + 1:
        return None
    high = df["high"]; low = df["low"]; close = df["close"]; vol = df["volume"]
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    mfv = (mfm * vol).fillna(0)
    cmf = mfv.rolling(period).sum() / vol.rolling(period).sum().replace(0, np.nan)
    return float(cmf.iloc[-1]) if not pd.isna(cmf.iloc[-1]) else None


def on_balance_volume(df):
    sign = np.sign(df["close"].diff().fillna(0))
    return (sign * df["volume"]).cumsum()


def obv_slope(df, lookback=20):
    if len(df) < lookback + 5:
        return None
    obv = on_balance_volume(df).iloc[-lookback:]
    if len(obv) < lookback or obv.std() == 0:
        return None
    x = np.arange(len(obv))
    slope = np.polyfit(x, obv.values, 1)[0]
    norm = np.mean(np.abs(obv.values)) or 1.0
    return float(slope / norm)


def money_flow_index(df, period=14):
    if len(df) < period + 2:
        return None
    typ = (df["high"] + df["low"] + df["close"]) / 3
    rmf = typ * df["volume"]
    pos = rmf.where(typ > typ.shift(), 0.0)
    neg = rmf.where(typ < typ.shift(), 0.0)
    pos_sum = pos.rolling(period).sum()
    neg_sum = neg.rolling(period).sum().replace(0, np.nan)
    mfr = pos_sum / neg_sum
    mfi = 100 - 100 / (1 + mfr)
    return float(mfi.iloc[-1]) if not pd.isna(mfi.iloc[-1]) else None


def relative_volume(df, lookback=20):
    if len(df) < lookback + 1:
        return None
    avg = df["volume"].iloc[-lookback - 1:-1].mean()
    if avg == 0:
        return None
    return float(df["volume"].iloc[-1] / avg)


def distribution_day_count(df, window=25):
    if len(df) < window + 21:
        return None
    sub = df.iloc[-(window + 20):].copy()
    sub["vavg20"] = sub["volume"].rolling(20).mean()
    recent = sub.iloc[-window:]
    rng = (recent["high"] - recent["low"]).replace(0, np.nan)
    pct_in_range = (recent["close"] - recent["low"]) / rng
    is_dist = (
        (pct_in_range < 0.25)
        & (recent["volume"] >= 1.5 * recent["vavg20"])
        & (recent["close"] < recent["close"].shift(1))
    )
    return int(is_dist.fillna(False).sum())


def obv_price_divergence(df, lookback=20):
    if len(df) < lookback + 1:
        return None
    close = df["close"]
    obv = on_balance_volume(df)
    price_new_high = close.iloc[-1] >= close.iloc[-lookback:].max()
    obv_new_high = obv.iloc[-1] >= obv.iloc[-lookback:].max()
    return bool(price_new_high and not obv_new_high)


def etf_primary_flow_5d_pct(ticker):
    if STUB_MODE:
        return 0.0
    raise NotImplementedError("Wire iShares/SSGA SHO CSV here.")


def block_trade_upside_ratio(ticker):
    if STUB_MODE:
        return 1.0
    raise NotImplementedError("Wire Polygon trade-tape here.")


def dark_pool_pct(ticker):
    if STUB_MODE:
        return 0.40
    raise NotImplementedError("Wire FINRA ATS Transparency feed here.")


def short_interest_delta_15d(ticker):
    if STUB_MODE:
        return 0.0
    raise NotImplementedError("Wire FINRA Reg SHO bi-monthly file here.")


def thirteen_f_net_buys_q(ticker):
    if STUB_MODE:
        return 0.0
    raise NotImplementedError("Wire SEC EDGAR Form 13F-HR ingestion here.")


def compute_flow_signals(ohlcv):
    rows = []
    for t, df in ohlcv.items():
        if str(t).startswith("^"):
            continue
        rows.append({
            "ticker":          t,
            "cmf21":           chaikin_money_flow(df, 21),
            "obv_slope":       obv_slope(df, 20),
            "mfi14":           money_flow_index(df, 14),
            "rvol":            relative_volume(df, 20),
            "dist_days_25":    distribution_day_count(df, 25),
            "obv_divergence":  obv_price_divergence(df, 20),
            "etf_flow_5d_pct": etf_primary_flow_5d_pct(t),
            "block_up_ratio":  block_trade_upside_ratio(t),
            "dark_pool_pct":   dark_pool_pct(t),
            "si_delta_15d":    short_interest_delta_15d(t),
            "thirteen_f_q":    thirteen_f_net_buys_q(t),
        })
    return pd.DataFrame(rows).set_index("ticker")


def flow_composite_z(flow_df):
    def _z(s):
        s = s.astype(float)
        std = s.std(ddof=0)
        if std == 0 or pd.isna(std):
            return s * 0.0
        return (s - s.mean()) / std

    z_cmf = _z(flow_df["cmf21"])
    z_obv = _z(flow_df["obv_slope"])
    z_etf = _z(flow_df["etf_flow_5d_pct"])
    z_blk = _z(flow_df["block_up_ratio"])
    z_vel = _z(flow_df["rvol"])
    z_si = _z(flow_df["si_delta_15d"]) * -1
    F = (0.30 * z_cmf + 0.20 * z_obv + 0.20 * z_etf + 0.10 * z_blk
         + 0.10 * z_vel + 0.10 * z_si).fillna(0)
    F.name = "F"
    return F
