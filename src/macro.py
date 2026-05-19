"""Pillar 6 - macro regime classification.

Two paths:
  - PROPER (when FRED_API_KEY is configured): 4-phase Stovall/Fidelity classifier
    using ISM-proxy (industrial production growth), yield curves, NFCI, recession
    probability, and unemployment. Phase ∈ {EARLY, MID, LATE, RECESSION}.
  - FALLBACK (no FRED key): coarse 2-signal proxy using Faber 10-month SMA on SPY
    + yield-curve sign from yfinance ^TNX/^IRX.

The dashboard automatically uses whichever is available — the user can wire FRED
later without code changes (see docs/BACKLOG.md D-101).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .data import close_price, to_monthly
from .fred_data import fetch_fred, fred_available, yoy_change, momentum_change


@dataclass
class MacroRegime:
    risk_on: bool
    spy_above_10mo_sma: bool
    yield_curve_positive: Optional[bool]
    phase_hint: str          # "EARLY" | "MID" | "LATE" | "RECESSION" | "UNKNOWN"
    note: str
    # Optional FRED-derived values (None when running on fallback)
    fred_used: bool = False
    indpro_yoy: Optional[float] = None
    indpro_accel: Optional[float] = None
    curve_2s10s: Optional[float] = None
    curve_3m10y: Optional[float] = None
    recession_prob: Optional[float] = None
    nfci: Optional[float] = None
    hy_spread: Optional[float] = None
    unemployment: Optional[float] = None


# ---------- Faber 10-month SMA (price-based circuit breaker) ----------

def faber_macro(bench_df: pd.DataFrame) -> Optional[bool]:
    m = to_monthly(bench_df)
    p = close_price(m)
    if len(p) < 11:
        return None
    sma10 = p.rolling(10).mean()
    return bool(p.iloc[-1] > sma10.iloc[-1])


# ---------- Yield-curve sign from yfinance proxies (fallback only) ----------

def yield_curve_sign(tnx_df: Optional[pd.DataFrame], irx_df: Optional[pd.DataFrame]) -> Optional[bool]:
    if tnx_df is None or irx_df is None or tnx_df.empty or irx_df.empty:
        return None
    last_10y = close_price(tnx_df).iloc[-1]
    last_3m = close_price(irx_df).iloc[-1]
    return bool(last_10y > last_3m)


# ---------- FRED-based 4-phase classifier ----------

def _classify_phase_from_fred(fred: dict[str, pd.Series]) -> dict:
    """Return phase + supporting metrics from FRED data."""
    indpro = fred.get("INDPRO")
    unrate = fred.get("UNRATE")
    curve_25 = fred.get("T10Y2Y")
    curve_3m = fred.get("T10Y3M")
    nfci = fred.get("NFCI")
    rec_prob = fred.get("RECPROUSM156N")
    hy = fred.get("BAMLH0A0HYM2")

    indpro_yoy = yoy_change(indpro, 12) if indpro is not None else None
    indpro_accel = momentum_change(indpro, recent=3, older=12) if indpro is not None else None
    curve_25_last = float(curve_25.iloc[-1]) if curve_25 is not None and len(curve_25) else None
    curve_3m_last = float(curve_3m.iloc[-1]) if curve_3m is not None and len(curve_3m) else None
    nfci_last = float(nfci.iloc[-1]) if nfci is not None and len(nfci) else None
    rec_prob_last = float(rec_prob.iloc[-1]) if rec_prob is not None and len(rec_prob) else None
    hy_last = float(hy.iloc[-1]) if hy is not None and len(hy) else None
    unemp_last = float(unrate.iloc[-1]) if unrate is not None and len(unrate) else None
    unemp_rising = False
    if unrate is not None and len(unrate) >= 5:
        unemp_rising = float(unrate.iloc[-1]) > float(unrate.iloc[-4])

    # ----- Phase decision tree -----
    phase = "UNKNOWN"
    reasons: list[str] = []

    # RECESSION: recession_prob high OR INDPRO contracting OR NFCI in stress
    if (
        (rec_prob_last is not None and rec_prob_last > 25) or
        (indpro_yoy is not None and indpro_yoy < -0.02) or
        (nfci_last is not None and nfci_last > 0.5)
    ):
        phase = "RECESSION"
        if rec_prob_last is not None and rec_prob_last > 25:
            reasons.append(f"recession prob {rec_prob_last:.0f}%")
        if indpro_yoy is not None and indpro_yoy < -0.02:
            reasons.append(f"INDPRO YoY {indpro_yoy:+.1%}")
        if nfci_last is not None and nfci_last > 0.5:
            reasons.append(f"NFCI stressed {nfci_last:+.2f}")

    # LATE: still growing but yield curve inverted OR INDPRO decelerating
    elif (
        (curve_25_last is not None and curve_25_last < 0) or
        (curve_3m_last is not None and curve_3m_last < 0) or
        (indpro_accel is not None and indpro_accel < 0 and (indpro_yoy or 0) > 0)
    ):
        phase = "LATE"
        if curve_25_last is not None and curve_25_last < 0:
            reasons.append(f"2s10s inverted {curve_25_last:+.2f}")
        if curve_3m_last is not None and curve_3m_last < 0:
            reasons.append(f"3M10Y inverted {curve_3m_last:+.2f}")
        if indpro_accel is not None and indpro_accel < 0:
            reasons.append("INDPRO decelerating")

    # EARLY: clear acceleration off lows
    elif (
        (indpro_yoy is not None and indpro_yoy > 0.03 and
         indpro_accel is not None and indpro_accel > 0) and
        (rec_prob_last is None or rec_prob_last < 5)
    ):
        phase = "EARLY"
        reasons.append(f"INDPRO YoY {indpro_yoy:+.1%} accelerating")
        if curve_25_last is not None:
            reasons.append(f"2s10s {curve_25_last:+.2f}")

    # MID: positive growth, normal curve, no stress
    elif indpro_yoy is not None and indpro_yoy > 0:
        phase = "MID"
        reasons.append(f"INDPRO YoY {indpro_yoy:+.1%}")
        if curve_25_last is not None:
            reasons.append(f"curve {curve_25_last:+.2f}")

    return {
        "phase": phase,
        "indpro_yoy": indpro_yoy,
        "indpro_accel": indpro_accel,
        "curve_2s10s": curve_25_last,
        "curve_3m10y": curve_3m_last,
        "recession_prob": rec_prob_last,
        "nfci": nfci_last,
        "hy_spread": hy_last,
        "unemployment": unemp_last,
        "note": " · ".join(reasons) if reasons else "Insufficient data",
    }


# ---------- Public API ----------

def assess_regime(
    bench_df: pd.DataFrame,
    tnx_df: Optional[pd.DataFrame] = None,
    irx_df: Optional[pd.DataFrame] = None,
    fred_cache: Optional[dict] = None,
) -> MacroRegime:
    """Return the unified macro regime assessment.

    If FRED is available and a key is configured, use the 4-phase classifier
    augmented with INDPRO + curves + NFCI + recession probability.
    Otherwise fall back to the coarse Faber + yfinance-curve proxy.

    Parameters
    ----------
    bench_df, tnx_df, irx_df : DataFrames from yfinance
    fred_cache : dict, optional. Pre-fetched FRED series (so app.py can cache it).
    """
    risk_on = faber_macro(bench_df) or False
    yc_yf = yield_curve_sign(tnx_df, irx_df)

    # Try FRED path first
    fred = fred_cache
    if fred is None and fred_available():
        try:
            fred = fetch_fred()
        except Exception:
            fred = {}

    if fred and "INDPRO" in fred:
        # Use the proper classifier
        out = _classify_phase_from_fred(fred)
        phase = out["phase"] if out["phase"] != "UNKNOWN" else ("MID" if risk_on else "RECESSION")
        note = "FRED data: " + out["note"]
        return MacroRegime(
            risk_on=risk_on,
            spy_above_10mo_sma=risk_on,
            yield_curve_positive=(out["curve_2s10s"] is not None and out["curve_2s10s"] > 0)
                                 if out["curve_2s10s"] is not None else yc_yf,
            phase_hint=phase,
            note=note,
            fred_used=True,
            indpro_yoy=out["indpro_yoy"],
            indpro_accel=out["indpro_accel"],
            curve_2s10s=out["curve_2s10s"],
            curve_3m10y=out["curve_3m10y"],
            recession_prob=out["recession_prob"],
            nfci=out["nfci"],
            hy_spread=out["hy_spread"],
            unemployment=out["unemployment"],
        )

    # ---- FALLBACK: coarse 2-signal proxy (existing behavior) ----
    if risk_on and yc_yf:
        phase = "MID"
        note = "Benchmark above 10mo SMA + positive yield curve. (FRED not configured — using coarse 2-signal proxy.)"
    elif risk_on and yc_yf is False:
        phase = "LATE"
        note = "Benchmark above 10mo SMA but yield curve inverted — late-cycle risk. (Coarse proxy.)"
    elif risk_on and yc_yf is None:
        phase = "MID"
        note = "Benchmark above 10mo SMA; yield-curve data unavailable. (Coarse proxy.)"
    elif not risk_on:
        phase = "RECESSION"
        note = "Benchmark below 10mo SMA — defensive bias. (Coarse proxy.)"
    else:
        phase = "UNKNOWN"
        note = "Insufficient data."

    return MacroRegime(
        risk_on=risk_on,
        spy_above_10mo_sma=risk_on,
        yield_curve_positive=yc_yf,
        phase_hint=phase,
        note=note,
        fred_used=False,
    )


# ---- Phase → sector basket map (Fidelity Business Cycle) ----

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
    if ticker.startswith("XL"):
        return -1.0
    return 0.0
