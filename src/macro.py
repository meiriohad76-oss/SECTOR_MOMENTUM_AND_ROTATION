"""Pillar 6 — macro regime.

Two free signals are computed from yfinance data alone:
    1. Faber 10-month SMA on the benchmark → RISK_ON / RISK_OFF
    2. Yield curve proxy from ^TNX (10Y) and ^IRX (3M-bill) → curve sign

For the full ISM PMI + yield-curve business-cycle classifier, set a FRED
API key in env var FRED_API_KEY and uncomment the calls in
``business_cycle_phase_full``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .data import close_price, to_monthly


@dataclass
class MacroRegime:
    risk_on: bool
    spy_above_10mo_sma: bool
    yield_curve_positive: Optional[bool]
    phase_hint: str          # "EARLY" | "MID" | "LATE" | "RECESSION" | "UNKNOWN"
    note: str


def faber_macro(bench_df: pd.DataFrame) -> Optional[bool]:
    m = to_monthly(bench_df)
    p = close_price(m)
    if len(p) < 11:
        return None
    sma10 = p.rolling(10).mean()
    return bool(p.iloc[-1] > sma10.iloc[-1])


def yield_curve_sign(tnx_df: Optional[pd.DataFrame], irx_df: Optional[pd.DataFrame]) -> Optional[bool]:
    if tnx_df is None or irx_df is None:
        return None
    if tnx_df.empty or irx_df.empty:
        return None
    last_10y = close_price(tnx_df).iloc[-1]
    last_3m = close_price(irx_df).iloc[-1]
    # yfinance reports yields in % * 10 for the ^TNX/^IRX series — direction-only is fine.
    return bool(last_10y > last_3m)


def assess_regime(
    bench_df: pd.DataFrame,
    tnx_df: Optional[pd.DataFrame] = None,
    irx_df: Optional[pd.DataFrame] = None,
) -> MacroRegime:
    risk = faber_macro(bench_df) or False
    yc = yield_curve_sign(tnx_df, irx_df)
    # phase hint without FRED data — coarse but useful
    if risk and yc:
        phase = "MID"
        note = "Benchmark above 10mo SMA + positive yield curve."
    elif risk and yc is False:
        phase = "LATE"
        note = "Benchmark still above 10mo SMA but yield curve inverted — late-cycle risk."
    elif risk and yc is None:
        phase = "MID"
        note = "Benchmark above 10mo SMA; yield-curve data unavailable."
    elif not risk and yc is False:
        phase = "RECESSION"
        note = "Benchmark below 10mo SMA AND yield curve inverted."
    elif not risk:
        phase = "RECESSION"
        note = "Benchmark below 10mo SMA — defensive bias."
    else:
        phase = "UNKNOWN"
        note = "Insufficient data."
    return MacroRegime(
        risk_on=risk,
        spy_above_10mo_sma=risk,
        yield_curve_positive=yc,
        phase_hint=phase,
        note=note,
    )


# Phase → sector tilt map from Fidelity Business Cycle white paper.
PHASE_FAVORED_SECTORS = {
    "EARLY":     {"XLY", "XLF", "XLRE", "XLI", "XLK", "XLB"},
    "MID":       {"XLK", "XLC", "XLI"},
    "LATE":      {"XLE", "XLB", "XLP", "XLV"},
    "RECESSION": {"XLP", "XLU", "XLV"},
}


def cycle_tilt(ticker: str, phase: str) -> float:
    favored = PHASE_FAVORED_SECTORS.get(phase, set())
    if not favored:
        return 0.0
    if ticker in favored:
        return 1.0
    # everything else gets a small negative nudge in known phases
    if ticker.startswith("XL"):
        return -1.0
    return 0.0
