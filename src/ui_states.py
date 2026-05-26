"""Pure helpers for dashboard empty and loading states."""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd


DEFENSIVE_BASKET = ("TLT", "GLD", "BIL")

DEFENSIVE_ROLES = {
    "TLT": "Long Treasury hedge",
    "GLD": "Gold hedge",
    "BIL": "Cash / T-bill proxy",
}

DEFENSIVE_NOTES = {
    "TLT": "Duration hedge for equity drawdown regimes.",
    "GLD": "Real-asset hedge when risk appetite fades.",
    "BIL": "T-bill proxy for capital preservation.",
}


def _first_row(scored_df: pd.DataFrame, ticker: str) -> pd.Series | None:
    if ticker not in scored_df.index:
        return None
    row = scored_df.loc[ticker]
    if isinstance(row, pd.DataFrame):
        return row.iloc[0]
    return row


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _state_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return "DATA_PENDING"
    return str(value)


def defensive_basket_rows(scored_df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ticker in DEFENSIVE_BASKET:
        row = _first_row(scored_df, ticker)
        available = row is not None
        rows.append(
            {
                "ticker": ticker,
                "role": DEFENSIVE_ROLES[ticker],
                "note": DEFENSIVE_NOTES[ticker],
                "available": available,
                "state": _state_text(row.get("state")) if available else "DATA_PENDING",
                "s_score": _optional_float(row.get("S_score")) if available else None,
                "f_score": _optional_float(row.get("F_score")) if available else None,
            }
        )
    return rows


def loading_skeleton_slots(count: int = 4) -> tuple[int, ...]:
    return tuple(range(max(0, int(count))))


def provider_status_banner_html(ohlcv_result: Any) -> str:
    if not (
        getattr(ohlcv_result, "used_stale_cache", False)
        or getattr(ohlcv_result, "missing", ())
        or getattr(ohlcv_result, "warnings", ())
    ):
        return ""
    if getattr(ohlcv_result, "used_stale_cache", False):
        label = "Provider degraded"
    elif getattr(ohlcv_result, "provider_retry_count", 0):
        label = "Provider recovered"
    else:
        label = "Provider gap"
    details = " ".join(escape(str(message), quote=True) for message in ohlcv_result.warnings)
    if not details:
        details = "Market data provider returned a partial response."
    return f"""
    <div class="provider-status-banner" role="status">
      <span class="label">{escape(label, quote=True)}</span>
      <span>{details}</span>
    </div>
    """
