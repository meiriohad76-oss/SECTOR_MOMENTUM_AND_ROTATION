"""FRED API fetcher for macro data (D-101).

Pulls a small set of economic time-series used by the business-cycle classifier
in src/macro.py. Reads FRED_API_KEY from either:
  - environment variable FRED_API_KEY, or
  - Streamlit secrets (st.secrets["FRED_API_KEY"]).

If no key is configured, fetch_fred() returns an empty dict and the rest of the
system falls back to the coarse 2-signal proxy in macro.py.

FRED series used:

    T10Y2Y          10-Year minus 2-Year Treasury yield (yield curve, daily)
    T10Y3M          10-Year minus 3-Month Treasury yield (recession predictor)
    INDPRO          Industrial Production Index (monthly)
    UNRATE          Civilian Unemployment Rate (monthly)
    NFCI            Chicago Fed National Financial Conditions Index (weekly)
    RECPROUSM156N   Smoothed US Recession Probability (monthly, 0-100)
    BAMLH0A0HYM2    ICE BofA US High Yield OAS spread (daily)
"""
from __future__ import annotations

import os
from typing import Callable, Optional

import pandas as pd

from .tls import ensure_system_trust_store

ensure_system_trust_store()


FRED_SERIES = {
    "T10Y2Y": "Yield curve 10Y - 2Y",
    "T10Y3M": "Yield curve 10Y - 3M",
    "DGS10": "10-Year Treasury yield",
    "INDPRO": "Industrial Production Index",
    "UNRATE": "Unemployment Rate",
    "NFCI":   "Chicago Fed Financial Conditions",
    "RECPROUSM156N": "Recession Probability (smoothed)",
    "BAMLH0A0HYM2":  "HY credit spread (OAS)",
    "CPIAUCSL": "Consumer Price Index",
    "PCEPILFE": "Core PCE price index",
    "T10YIE": "10-Year breakeven inflation",
    "WALCL": "Fed total assets",
    "M2SL": "M2 money supply",
    "CFNAI": "Chicago Fed National Activity Index",
    "ICSA": "Initial claims",
    "UMCSENT": "University of Michigan consumer sentiment",
    "BAMLC0A0CM": "Corporate credit spread (OAS)",
    "STLFSI4": "St. Louis Fed Financial Stress Index",
    "DCOILWTICO": "WTI crude oil price",
    "DHHNGSP": "Henry Hub natural gas price",
    "DTWEXBGS": "Nominal Broad U.S. Dollar Index",
}

_LAST_FETCH_DIAGNOSTICS: dict[str, object] = {
    "status": "not_attempted",
    "configured": False,
    "series_loaded": 0,
    "series_failed": 0,
    "errors": [],
}


def _set_fetch_diagnostics(**updates: object) -> None:
    _LAST_FETCH_DIAGNOSTICS.clear()
    _LAST_FETCH_DIAGNOSTICS.update(
        {
            "status": "not_attempted",
            "configured": False,
            "series_loaded": 0,
            "series_failed": 0,
            "errors": [],
        }
    )
    _LAST_FETCH_DIAGNOSTICS.update(updates)


def fred_fetch_diagnostics() -> dict[str, object]:
    """Return secret-safe diagnostics for the most recent FRED fetch attempt."""
    return {
        **_LAST_FETCH_DIAGNOSTICS,
        "errors": list(_LAST_FETCH_DIAGNOSTICS.get("errors", []) or []),
    }


def _resolve_api_key() -> Optional[str]:
    """Pull the FRED API key from env first, then Streamlit secrets."""
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key.strip()

    # Try Streamlit secrets - lazy import so module usable without streamlit
    try:
        import streamlit as st  # type: ignore
        if hasattr(st, "secrets"):
            try:
                key = st.secrets.get("FRED_API_KEY")
                if key:
                    return key.strip()
            except Exception:
                pass
    except Exception:
        pass
    return None


def fred_available() -> bool:
    """True if both fredapi is installed and a key is configured."""
    if _resolve_api_key() is None:
        return False
    try:
        import fredapi  # noqa: F401
        return True
    except ImportError:
        return False


def fetch_fred(
    start_date: str = "2018-01-01",
    client_factory: Optional[Callable[[str], object]] = None,
) -> dict[str, pd.Series]:
    """Fetch all configured FRED series. Returns {series_id: Series} or {} on failure.

    Caches via Streamlit if available.
    """
    key = _resolve_api_key()
    if key is None:
        _set_fetch_diagnostics(status="missing_key", configured=False)
        return {}

    if client_factory is None:
        try:
            from fredapi import Fred  # type: ignore
        except ImportError:
            _set_fetch_diagnostics(status="missing_library", configured=True)
            return {}
        client_factory = Fred

    try:
        fred = client_factory(key)
    except Exception as exc:
        _set_fetch_diagnostics(
            status="client_error",
            configured=True,
            errors=[f"client: {type(exc).__name__}"],
        )
        return {}
    out: dict[str, pd.Series] = {}
    errors: list[str] = []
    for series_id in FRED_SERIES:
        try:
            s = fred.get_series(series_id, observation_start=start_date)
            if s is not None and not s.empty:
                cleaned = s.dropna().sort_index()
                if cleaned.index.has_duplicates:
                    cleaned = cleaned.groupby(level=0).last()
                out[series_id] = cleaned
        except Exception as exc:
            errors.append(f"{series_id}: {type(exc).__name__}")
            continue
    failed = len(FRED_SERIES) - len(out)
    if out and errors:
        status = "partial"
    elif out:
        status = "ok"
    else:
        status = "failed"
    _set_fetch_diagnostics(
        status=status,
        configured=True,
        series_loaded=len(out),
        series_failed=failed,
        errors=errors[:8],
    )
    return out


def latest_values(fred_data: dict[str, pd.Series]) -> dict[str, Optional[float]]:
    """Return the most recent observation for each fetched series."""
    out = {}
    for sid, series in fred_data.items():
        try:
            out[sid] = float(series.iloc[-1])
        except Exception:
            out[sid] = None
    return out


def yoy_change(series: pd.Series, lag_months: int = 12) -> Optional[float]:
    """Year-over-year % change. For monthly series."""
    if series is None or len(series) < lag_months + 1:
        return None
    try:
        return float(series.iloc[-1] / series.iloc[-lag_months - 1] - 1)
    except Exception:
        return None


def momentum_change(series: pd.Series, recent: int = 3, older: int = 12) -> Optional[float]:
    """Recent average vs older average — used to detect acceleration / deceleration."""
    if series is None or len(series) < older + 1:
        return None
    try:
        recent_avg = float(series.iloc[-recent:].mean())
        older_avg = float(series.iloc[-older:-recent].mean())
        return recent_avg - older_avg
    except Exception:
        return None
