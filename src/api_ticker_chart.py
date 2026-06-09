"""Read-only ticker chart payloads for the B-170 React migration."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .data import close_price, to_weekly
from .ohlcv_store import read_cached_ohlcv_metadata
from .ticker_identity import ticker_display_name


def build_ticker_chart_payload(
    ticker: str,
    *,
    period: str = "3y",
    cache_path: str | Path | None = None,
    max_points: int = 180,
) -> dict[str, Any]:
    """Return cached weekly price + 30wMA data without provider fetches."""

    symbol = str(ticker or "").strip().upper()
    if not symbol:
        return _empty_payload("", period, "Ticker is required.")
    metadata = read_cached_ohlcv_metadata(
        [symbol],
        period=period,
        cache_path=cache_path,
        allow_stale=True,
    )
    entry = metadata.get(symbol)
    if not entry or not isinstance(entry.get("frame"), pd.DataFrame):
        return _empty_payload(symbol, period, "No cached OHLCV data is available for this ticker.")
    frame = entry["frame"]
    if frame.empty:
        return _empty_payload(symbol, period, "Cached OHLCV data is empty.")

    weekly = to_weekly(frame).dropna(subset=["close"])
    if weekly.empty:
        return _empty_payload(symbol, period, "Cached OHLCV data could not be converted to weekly rows.")
    close = close_price(weekly).astype(float)
    ma30 = close.rolling(30, min_periods=1).mean()
    rows = pd.DataFrame({"date": weekly.index, "close": close.to_numpy(), "ma30w": ma30.to_numpy()})
    rows = rows.dropna(subset=["close"]).tail(max(1, int(max_points)))
    latest = rows.iloc[-1].to_dict() if not rows.empty else {}
    close_value = _float_or_none(latest.get("close"))
    ma_value = _float_or_none(latest.get("ma30w"))
    above_ma = None if close_value is None or ma_value is None else close_value >= ma_value
    slope_30w = None
    if len(ma30.dropna()) >= 2:
        slope_30w = float(ma30.dropna().iloc[-1] - ma30.dropna().iloc[-2])

    return {
        "api_version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "message": "Cached weekly price chart loaded.",
        "ticker": symbol,
        "identity": ticker_display_name(symbol),
        "period": period,
        "source": {
            "mode": "cache-only",
            "provider": str(entry.get("provider") or "unknown"),
            "updated_at": str(entry.get("updated_at") or ""),
            "row_count": int(len(frame)),
            "weekly_row_count": int(len(rows)),
        },
        "latest": {
            "date": _date_text(latest.get("date")),
            "close": close_value,
            "ma30w": ma_value,
            "above_30wma": above_ma,
            "ma30w_slope": slope_30w,
        },
        "series": [
            {
                "date": _date_text(row["date"]),
                "close": _float_or_none(row["close"]),
                "ma30w": _float_or_none(row["ma30w"]),
            }
            for row in rows.to_dict(orient="records")
        ],
    }


def _empty_payload(ticker: str, period: str, message: str) -> dict[str, Any]:
    symbol = str(ticker or "").strip().upper()
    return {
        "api_version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "empty",
        "message": message,
        "ticker": symbol,
        "identity": ticker_display_name(symbol) if symbol else "",
        "period": period,
        "source": {"mode": "cache-only", "provider": "", "updated_at": "", "row_count": 0, "weekly_row_count": 0},
        "latest": {"date": "", "close": None, "ma30w": None, "above_30wma": None, "ma30w_slope": None},
        "series": [],
    }


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return pd.Timestamp(value).date().isoformat()
    except Exception:
        return str(value)
