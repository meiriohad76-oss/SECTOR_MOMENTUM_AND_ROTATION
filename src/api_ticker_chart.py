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
    flow_frame = _flow_frame(frame, max_points=max_points)
    latest_flow = flow_frame.iloc[-1].to_dict() if not flow_frame.empty else {}

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
            "cmf21": _float_or_none(latest_flow.get("cmf21")),
            "obv": _float_or_none(latest_flow.get("obv")),
            "obv_slope": _obv_slope(flow_frame["obv"]) if "obv" in flow_frame else None,
        },
        "series": [
            {
                "date": _date_text(row["date"]),
                "close": _float_or_none(row["close"]),
                "ma30w": _float_or_none(row["ma30w"]),
            }
            for row in rows.to_dict(orient="records")
        ],
        "flow_series": [
            {
                "date": _date_text(row["date"]),
                "cmf21": _float_or_none(row["cmf21"]),
                "obv": _float_or_none(row["obv"]),
            }
            for row in flow_frame.to_dict(orient="records")
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
        "latest": {
            "date": "",
            "close": None,
            "ma30w": None,
            "above_30wma": None,
            "ma30w_slope": None,
            "cmf21": None,
            "obv": None,
            "obv_slope": None,
        },
        "series": [],
        "flow_series": [],
    }


def _flow_frame(frame: pd.DataFrame, *, max_points: int) -> pd.DataFrame:
    values = frame.copy().sort_index()
    for column in ("high", "low", "close", "volume"):
        if column not in values.columns:
            values[column] = pd.NA
        values[column] = pd.to_numeric(values[column], errors="coerce")
    high = values["high"]
    low = values["low"]
    close = values["close"]
    volume = values["volume"].fillna(0.0)
    denominator = (high - low).replace(0, pd.NA)
    money_flow_multiplier = ((close - low) - (high - close)) / denominator
    money_flow_volume = money_flow_multiplier.fillna(0.0) * volume
    cmf21 = money_flow_volume.rolling(21, min_periods=1).sum() / volume.rolling(21, min_periods=1).sum().replace(0, pd.NA)
    signed_volume = close.diff().fillna(0.0).apply(lambda value: 1 if value > 0 else -1 if value < 0 else 0) * volume
    obv = signed_volume.cumsum()
    rows = pd.DataFrame({"date": values.index, "cmf21": cmf21.to_numpy(), "obv": obv.to_numpy()})
    rows = rows.dropna(how="all", subset=["cmf21", "obv"]).tail(max(1, int(max_points)))
    return rows


def _obv_slope(obv: pd.Series) -> float | None:
    values = pd.to_numeric(obv, errors="coerce").dropna().tail(20)
    if len(values) < 2:
        return None
    delta = float(values.iloc[-1] - values.iloc[0])
    normalizer = float(values.abs().mean()) or 1.0
    return delta / normalizer


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
