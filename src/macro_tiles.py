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
FRED_CONTEXT_GROUPS = (
    {
        "group": "Rates",
        "series": (
            {"id": "DGS10", "label": "10Y yield", "unit": "percent", "tone": "higher_warn"},
            {"id": "T10Y2Y", "label": "2s10s", "unit": "percent", "tone": "higher_up"},
        ),
    },
    {
        "group": "Inflation",
        "series": (
            {"id": "CPIAUCSL", "label": "CPI", "unit": "index", "tone": "higher_warn", "yoy": True},
            {"id": "PCEPILFE", "label": "Core PCE", "unit": "index", "tone": "higher_warn", "yoy": True},
            {"id": "T10YIE", "label": "10Y breakeven", "unit": "percent", "tone": "higher_warn"},
        ),
    },
    {
        "group": "Liquidity",
        "series": (
            {"id": "WALCL", "label": "Fed assets", "unit": "millions_usd", "tone": "higher_up"},
            {"id": "M2SL", "label": "M2", "unit": "billions_usd", "tone": "higher_up", "yoy": True},
        ),
    },
    {
        "group": "Growth",
        "series": (
            {"id": "CFNAI", "label": "CFNAI", "unit": "number", "tone": "higher_up"},
            {"id": "ICSA", "label": "Claims", "unit": "number", "tone": "higher_warn"},
            {"id": "UMCSENT", "label": "Sentiment", "unit": "number", "tone": "higher_up"},
        ),
    },
    {
        "group": "Credit",
        "series": (
            {"id": "BAMLH0A0HYM2", "label": "HY OAS", "unit": "percent", "tone": "higher_warn"},
            {"id": "BAMLC0A0CM", "label": "Corp OAS", "unit": "percent", "tone": "higher_warn"},
            {"id": "STLFSI4", "label": "Stress", "unit": "number", "tone": "higher_warn"},
        ),
    },
    {
        "group": "Commodities",
        "series": (
            {"id": "DCOILWTICO", "label": "WTI", "unit": "number", "tone": "higher_warn"},
            {"id": "DHHNGSP", "label": "Nat gas", "unit": "number", "tone": "higher_warn"},
        ),
    },
)


def _format_value(value: float) -> str:
    return f"{value:.2f}"


def _format_fred_value(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:.2f}%"
    if unit == "millions_usd":
        return f"{value / 1_000_000:.2f}T"
    if unit == "billions_usd":
        return f"{value / 1_000:.2f}T"
    if abs(value) >= 100_000:
        return f"{value / 1_000:.0f}K"
    return _format_value(value)


def _format_fred_date(index_value) -> str:
    if hasattr(index_value, "date"):
        return str(index_value.date())
    return str(index_value)


def _delta_tone(delta: float | None, mode: str) -> str:
    if delta is None:
        return "warn"
    if math.isclose(delta, 0.0, abs_tol=0.0001):
        return "flat"
    higher_is_good = mode == "higher_up"
    if delta > 0:
        return "up" if higher_is_good else "warn"
    return "down" if higher_is_good else "up"


def _fred_series_stats(series: pd.Series | None) -> dict[str, float | str] | None:
    if series is None:
        return None
    try:
        cleaned = series.dropna()
    except Exception:
        return None
    if cleaned.empty:
        return None
    latest = float(cleaned.iloc[-1])
    stats: dict[str, float | str] = {
        "latest_value": latest,
        "latest_date": _format_fred_date(cleaned.index[-1]),
    }
    if len(cleaned) >= 2:
        stats["delta"] = latest - float(cleaned.iloc[-2])
    if len(cleaned) >= 13:
        previous = float(cleaned.iloc[-13])
        if not math.isclose(previous, 0.0):
            stats["yoy_pct"] = (latest / previous - 1.0) * 100.0
    return stats


def _pending_fred_row(item: Mapping[str, str], group: str) -> dict[str, str]:
    return {
        "group": group,
        "series_id": item["id"],
        "label": item["label"],
        "value": "DATA PENDING",
        "change": "-",
        "tone": "warn",
        "subtitle": item["id"],
        "latest_date": "",
    }


def _fred_row(item: Mapping[str, str], group: str, series: pd.Series | None) -> dict[str, str]:
    stats = _fred_series_stats(series)
    if stats is None:
        return _pending_fred_row(item, group)
    delta = stats.get("delta")
    yoy_pct = stats.get("yoy_pct")
    unit = str(item.get("unit", "number"))
    change = "-"
    if item.get("yoy") and isinstance(yoy_pct, float):
        change = f"{yoy_pct:+.1f}% YoY"
        tone = _delta_tone(yoy_pct, str(item.get("tone", "higher_up")))
    elif isinstance(delta, float):
        suffix = " pp" if unit == "percent" else ""
        change = f"{delta:+.2f}{suffix}"
        tone = _delta_tone(delta, str(item.get("tone", "higher_up")))
    else:
        tone = "flat"
    return {
        "group": group,
        "series_id": item["id"],
        "label": item["label"],
        "value": _format_fred_value(float(stats["latest_value"]), unit),
        "change": change,
        "tone": tone,
        "subtitle": str(stats["latest_date"]),
        "latest_date": str(stats["latest_date"]),
    }


def fred_macro_tile_groups(fred_data: Mapping[str, pd.Series]) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for group in FRED_CONTEXT_GROUPS:
        group_name = str(group["group"])
        rows = [
            _fred_row(item, group_name, fred_data.get(item["id"]))
            for item in group["series"]
        ]
        groups.append({"group": group_name, "rows": rows})
    return groups


def fred_macro_snapshot(fred_data: Mapping[str, pd.Series]) -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for group in FRED_CONTEXT_GROUPS:
        group_name = str(group["group"])
        for item in group["series"]:
            stats = _fred_series_stats(fred_data.get(item["id"]))
            if stats is None:
                continue
            snapshot[item["id"]] = {
                "label": item["label"],
                "group": group_name,
                "latest_date": stats["latest_date"],
                "latest_value": stats["latest_value"],
            }
            if "delta" in stats:
                snapshot[item["id"]]["delta"] = stats["delta"]
            if "yoy_pct" in stats:
                snapshot[item["id"]]["yoy_pct"] = stats["yoy_pct"]
    return snapshot


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


def session_range_tile(frame: pd.DataFrame | None, symbol: str) -> dict[str, str]:
    base = {
        "label": "Session range",
        "symbol": symbol,
        "value": "DATA PENDING",
        "change": "-",
        "tone": "warn",
        "subtitle": "latest bar",
    }
    if frame is None or frame.empty:
        return base
    try:
        latest = frame.dropna(how="all").iloc[-1]
        high = float(latest["high"])
        low = float(latest["low"])
        close = float(latest["adj_close"] if "adj_close" in frame.columns else latest["close"])
    except (IndexError, KeyError, TypeError, ValueError):
        return base
    if not (math.isfinite(high) and math.isfinite(low) and math.isfinite(close)):
        return base
    if high < low:
        return base

    span = high - low
    if math.isclose(span, 0.0):
        tone = "flat"
        subtitle = "flat range"
    else:
        position = (close - low) / span
        if position >= 0.75:
            tone = "up"
            subtitle = "near high"
        elif position <= 0.25:
            tone = "down"
            subtitle = "near low"
        else:
            tone = "flat"
            subtitle = "mid range"

    return {
        "label": "Session range",
        "symbol": symbol,
        "value": _format_value(close),
        "change": f"H {_format_value(high)} / L {_format_value(low)}",
        "tone": tone,
        "subtitle": subtitle,
    }
