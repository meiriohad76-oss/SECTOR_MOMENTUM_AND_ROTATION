from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

from .data import close_price


MACRO_CONTEXT = (
    {
        "label": "VIX",
        "symbol": "^VIX",
        "subtitle": "Volatility stress proxy",
        "tone": "higher_warn",
        "tooltip": "Volatility proxy: VIX is an equity-volatility stress proxy. Rising VIX usually means risk appetite is worsening, which can weaken momentum picks.",
    },
    {
        "label": "Gold ETF proxy",
        "symbol": "GLD",
        "subtitle": "GLD ETF, tradable gold exposure",
        "tone": "higher_warn",
        "tooltip": "GLD is a liquid gold ETF proxy, not spot gold. It is kept as a tradable defensive-demand context because the configured FRED feed does not provide a stable current spot-gold series.",
    },
)
MACRO_CONTEXT_SYMBOLS = tuple(item["symbol"] for item in MACRO_CONTEXT)
FRED_HEADER_CONTEXT_IDS = ("DCOILWTICO", "DTWEXBGS")
FRED_CONTEXT_GROUPS = (
    {
        "group": "Rates",
        "series": (
            {"id": "DGS10", "label": "10Y yield", "unit": "percent", "tone": "higher_warn", "tooltip": "10-year Treasury yield. Rising yields can raise the discount rate for equities and may pressure long-duration momentum leaders."},
            {"id": "T10Y2Y", "label": "2s10s", "unit": "percent", "tone": "higher_up", "tooltip": "10-year minus 2-year Treasury yield curve. A steeper positive curve is usually healthier for growth expectations than an inversion."},
        ),
    },
    {
        "group": "Inflation",
        "series": (
            {"id": "CPIAUCSL", "label": "CPI", "unit": "index", "tone": "higher_warn", "yoy": True, "tooltip": "Consumer Price Index. Higher year-over-year inflation can pressure valuations and increase the risk of tighter policy."},
            {"id": "PCEPILFE", "label": "Core PCE", "unit": "index", "tone": "higher_warn", "yoy": True, "tooltip": "Core PCE inflation. This is a key Federal Reserve inflation gauge; rising pressure can be negative for risk assets."},
            {"id": "T10YIE", "label": "10Y breakeven", "unit": "percent", "tone": "higher_warn", "tooltip": "Market-implied 10-year inflation expectations. Rising breakevens can point to inflation pressure and affect sector leadership."},
        ),
    },
    {
        "group": "Liquidity",
        "series": (
            {"id": "WALCL", "label": "Fed assets", "unit": "millions_usd", "tone": "higher_up", "tooltip": "Federal Reserve balance sheet assets. More liquidity can support risk appetite; shrinking liquidity can be a headwind."},
            {"id": "M2SL", "label": "M2", "unit": "billions_usd", "tone": "higher_up", "yoy": True, "tooltip": "M2 is broad money supply: cash, checking deposits, savings deposits, and similar liquid money. Rising M2 can support liquidity conditions."},
        ),
    },
    {
        "group": "Growth",
        "series": (
            {"id": "CFNAI", "label": "CFNAI", "unit": "number", "tone": "higher_up", "tooltip": "Chicago Fed National Activity Index. Higher readings indicate stronger economic activity, which can support cyclical momentum."},
            {"id": "ICSA", "label": "Claims", "unit": "number", "tone": "higher_warn", "tooltip": "Initial jobless claims. Rising claims can signal labor-market deterioration and slower growth."},
            {"id": "UMCSENT", "label": "Sentiment", "unit": "number", "tone": "higher_up", "tooltip": "University of Michigan consumer sentiment. Improving sentiment can support risk appetite and consumer-linked sectors."},
        ),
    },
    {
        "group": "Credit",
        "series": (
            {"id": "BAMLH0A0HYM2", "label": "HY OAS", "unit": "percent", "tone": "higher_warn", "tooltip": "High-yield option-adjusted spread. Wider spreads indicate more credit stress and can be negative for risk assets."},
            {"id": "BAMLC0A0CM", "label": "Corp OAS", "unit": "percent", "tone": "higher_warn", "tooltip": "Investment-grade corporate option-adjusted spread. Wider spreads indicate tighter credit conditions."},
            {"id": "STLFSI4", "label": "Stress", "unit": "number", "tone": "higher_warn", "tooltip": "St. Louis Fed Financial Stress Index. Higher stress is usually negative for broad market momentum."},
        ),
    },
    {
        "group": "Commodities",
        "series": (
            {"id": "DCOILWTICO", "label": "WTI spot", "unit": "number", "tone": "higher_warn", "tooltip": "WTI crude oil spot price from FRED. Rising oil can raise inflation pressure and affect sector rotation."},
            {"id": "DHHNGSP", "label": "Nat gas", "unit": "number", "tone": "higher_warn", "tooltip": "Henry Hub natural gas spot price. Rising energy input costs can affect inflation and sector margins."},
        ),
    },
    {
        "group": "FX",
        "series": (
            {"id": "DTWEXBGS", "label": "USD broad", "unit": "index", "tone": "higher_warn", "tooltip": "Broad U.S. Dollar Index from FRED. A rising dollar can tighten global liquidity and pressure risk assets."},
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


def _sentiment_label(tone: str) -> str:
    if tone == "up":
        return "positive"
    if tone in {"warn", "down"}:
        return "negative"
    if tone == "flat":
        return "neutral"
    return "unavailable"


def _trend_symbol(sentiment: str) -> str:
    return {
        "positive": "+",
        "negative": "!",
        "neutral": "=",
        "unavailable": "?",
    }.get(sentiment, "?")


def _trend_label(delta: float | None, mode: str) -> str:
    if delta is None:
        return "data pending"
    if math.isclose(delta, 0.0, abs_tol=0.0001):
        return "flat"
    higher_is_good = mode == "higher_up"
    if delta > 0:
        return "improving" if higher_is_good else "worsening"
    return "worsening" if higher_is_good else "improving"


def _gauge_pct(delta: float | None, scale: float) -> int:
    if delta is None or math.isclose(delta, 0.0, abs_tol=0.0001):
        return 50
    return int(round(min(100.0, 50.0 + abs(delta) * scale)))


def _decorate_row(row: dict[str, object], delta: float | None, mode: str, gauge_scale: float) -> dict[str, object]:
    tone = str(row.get("tone", "warn"))
    sentiment = _sentiment_label(tone)
    row["sentiment_label"] = sentiment
    row["trend_label"] = _trend_label(delta, mode)
    row["trend_symbol"] = _trend_symbol(sentiment)
    row["gauge_pct"] = _gauge_pct(delta, gauge_scale)
    return row


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
    row: dict[str, object] = {
        "group": group,
        "series_id": item["id"],
        "label": item["label"],
        "value": "DATA PENDING",
        "change": "-",
        "tone": "warn",
        "subtitle": item["id"],
        "latest_date": "",
        "tooltip": item.get("tooltip", f"{item['label']} macro context from FRED."),
    }
    row["sentiment_label"] = "unavailable"
    row["trend_label"] = "data pending"
    row["trend_symbol"] = "?"
    row["gauge_pct"] = 50
    return row


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
        trend_delta = yoy_pct
        gauge_scale = 10.0
    elif isinstance(delta, float):
        suffix = " pp" if unit == "percent" else ""
        change = f"{delta:+.2f}{suffix}"
        tone = _delta_tone(delta, str(item.get("tone", "higher_up")))
        trend_delta = delta
        gauge_scale = 50.0 if unit == "percent" else 1.0
    else:
        tone = "flat"
        trend_delta = None
        gauge_scale = 1.0
    return _decorate_row({
        "group": group,
        "series_id": item["id"],
        "label": item["label"],
        "value": _format_fred_value(float(stats["latest_value"]), unit),
        "change": change,
        "tone": tone,
        "subtitle": str(stats["latest_date"]),
        "latest_date": str(stats["latest_date"]),
        "tooltip": item.get("tooltip", f"{item['label']} macro context from FRED."),
    }, trend_delta, str(item.get("tone", "higher_up")), gauge_scale)


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


def _fred_context_item_by_id(series_id: str) -> tuple[Mapping[str, str], str] | None:
    for group in FRED_CONTEXT_GROUPS:
        group_name = str(group["group"])
        for item in group["series"]:
            if item["id"] == series_id:
                return item, group_name
    return None


def _tone(change_pct: float | None, label: str) -> str:
    if change_pct is None:
        return "warn"
    if math.isclose(change_pct, 0.0, abs_tol=0.0001):
        return "flat"
    if label == "VIX":
        return "warn" if change_pct > 0 else "up"
    return "up" if change_pct > 0 else "down"


def _proxy_tone(change_pct: float | None, mode: str) -> str:
    return _delta_tone(change_pct, mode)


def _row_for(item: Mapping[str, str], frame: pd.DataFrame | None) -> dict[str, str]:
    if frame is None or frame.empty:
        row: dict[str, object] = {
            "label": item["label"],
            "symbol": item["symbol"],
            "value": "DATA PENDING",
            "change": "-",
            "tone": "warn",
            "subtitle": item["subtitle"],
            "tooltip": item.get("tooltip", f"{item['label']} market proxy."),
        }
        row["sentiment_label"] = "unavailable"
        row["trend_label"] = "data pending"
        row["trend_symbol"] = "?"
        row["gauge_pct"] = 50
        return row

    try:
        prices = close_price(frame).dropna()
    except Exception:
        prices = pd.Series(dtype=float)
    if len(prices) < 1:
        row = {
            "label": item["label"],
            "symbol": item["symbol"],
            "value": "DATA PENDING",
            "change": "-",
            "tone": "warn",
            "subtitle": item["subtitle"],
            "tooltip": item.get("tooltip", f"{item['label']} market proxy."),
        }
        row["sentiment_label"] = "unavailable"
        row["trend_label"] = "data pending"
        row["trend_symbol"] = "?"
        row["gauge_pct"] = 50
        return row

    last = float(prices.iloc[-1])
    change_pct = None
    if len(prices) >= 2:
        prev = float(prices.iloc[-2])
        if not math.isclose(prev, 0.0):
            change_pct = (last / prev - 1.0) * 100.0

    mode = str(item.get("tone", "higher_up"))
    return _decorate_row({
        "label": item["label"],
        "symbol": item["symbol"],
        "value": _format_value(last),
        "change": f"{change_pct:+.1f}%" if change_pct is not None else "-",
        "tone": _proxy_tone(change_pct, mode),
        "subtitle": item["subtitle"],
        "tooltip": item.get("tooltip", f"{item['label']} market proxy."),
    }, change_pct, mode, 4.0)


def macro_tile_rows(
    ohlcv: Mapping[str, pd.DataFrame],
    fred_data: Mapping[str, pd.Series] | None = None,
) -> list[dict[str, str]]:
    rows = [_row_for(item, ohlcv.get(item["symbol"])) for item in MACRO_CONTEXT]
    fred_payload = fred_data or {}
    for series_id in FRED_HEADER_CONTEXT_IDS:
        item_and_group = _fred_context_item_by_id(series_id)
        if item_and_group is None:
            continue
        item, group_name = item_and_group
        rows.append(_fred_row(item, group_name, fred_payload.get(series_id)))
    return rows


def session_range_tile(frame: pd.DataFrame | None, symbol: str) -> dict[str, str]:
    base = {
        "label": f"{symbol} range",
        "symbol": symbol,
        "value": "DATA PENDING",
        "change": "-",
        "tone": "warn",
        "subtitle": "latest bar",
        "sentiment_label": "unavailable",
        "trend_label": "data pending",
        "trend_symbol": "?",
        "gauge_pct": 50,
        "tooltip": f"{symbol} latest high-low range. It shows where the latest close sits inside the session: near high suggests buying pressure; near low suggests selling pressure.",
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
    position = 0.5
    if math.isclose(span, 0.0):
        tone = "flat"
        subtitle = "flat range"
        sentiment = "neutral"
        trend = "balanced"
    else:
        position = (close - low) / span
        if position >= 0.75:
            tone = "up"
            subtitle = "close near high"
            sentiment = "positive"
            trend = "buying pressure"
        elif position <= 0.25:
            tone = "down"
            subtitle = "close near low"
            sentiment = "negative"
            trend = "selling pressure"
        else:
            tone = "flat"
            subtitle = "close mid range"
            sentiment = "neutral"
            trend = "balanced"

    return {
        "label": f"{symbol} range",
        "symbol": symbol,
        "value": _format_value(close),
        "change": f"H {_format_value(high)} / L {_format_value(low)}",
        "tone": tone,
        "subtitle": subtitle,
        "sentiment_label": sentiment,
        "trend_label": trend,
        "trend_symbol": _trend_symbol(sentiment),
        "gauge_pct": int(round(position * 100)) if not math.isclose(span, 0.0) else 50,
        "tooltip": f"{symbol} latest high-low range. It shows where the latest close sits inside the session: near high suggests buying pressure; near low suggests selling pressure.",
    }
