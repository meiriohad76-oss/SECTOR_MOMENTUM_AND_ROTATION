from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

from .data import close_price


MACRO_CONTEXT = (
    {"label": "VIX", "symbol": "^VIX", "subtitle": "Volatility"},
    {"label": "Gold", "symbol": "GLD", "subtitle": "Gold proxy"},
    {"label": "Oil", "symbol": "USO", "subtitle": "Oil proxy"},
    {"label": "USD", "symbol": "UUP", "subtitle": "Dollar proxy"},
)
MACRO_CONTEXT_SYMBOLS = tuple(item["symbol"] for item in MACRO_CONTEXT)


def _format_value(value: float) -> str:
    return f"{value:.2f}"


def _tone(change_pct: float | None, label: str) -> str:
    if change_pct is None:
        return "warn"
    if math.isclose(change_pct, 0.0, abs_tol=0.0001):
        return "flat"
    if label == "VIX":
        return "warn" if change_pct > 0 else "up"
    return "up" if change_pct > 0 else "down"


def _row_for(item: Mapping[str, str], frame: pd.DataFrame | None) -> dict[str, str]:
    if frame is None or frame.empty:
        return {
            "label": item["label"],
            "symbol": item["symbol"],
            "value": "DATA PENDING",
            "change": "-",
            "tone": "warn",
            "subtitle": item["subtitle"],
        }

    try:
        prices = close_price(frame).dropna()
    except Exception:
        prices = pd.Series(dtype=float)
    if len(prices) < 1:
        return {
            "label": item["label"],
            "symbol": item["symbol"],
            "value": "DATA PENDING",
            "change": "-",
            "tone": "warn",
            "subtitle": item["subtitle"],
        }

    last = float(prices.iloc[-1])
    change_pct = None
    if len(prices) >= 2:
        prev = float(prices.iloc[-2])
        if not math.isclose(prev, 0.0):
            change_pct = (last / prev - 1.0) * 100.0

    return {
        "label": item["label"],
        "symbol": item["symbol"],
        "value": _format_value(last),
        "change": f"{change_pct:+.1f}%" if change_pct is not None else "-",
        "tone": _tone(change_pct, item["label"]),
        "subtitle": item["subtitle"],
    }


def macro_tile_rows(ohlcv: Mapping[str, pd.DataFrame]) -> list[dict[str, str]]:
    return [_row_for(item, ohlcv.get(item["symbol"])) for item in MACRO_CONTEXT]
