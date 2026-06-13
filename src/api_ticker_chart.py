"""Read-only ticker chart payloads for the B-170 React migration."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .data import close_price, to_weekly
from .ohlcv_store import read_cached_ohlcv_metadata
from .ticker_identity import ticker_display_name
from .universe import BENCH


def build_ticker_chart_payload(
    ticker: str,
    *,
    period: str = "3y",
    cache_path: str | Path | None = None,
    max_points: int = 180,
    benchmark: str | None = None,
) -> dict[str, Any]:
    """Return cached weekly price + 30wMA data without provider fetches."""

    symbol = str(ticker or "").strip().upper()
    benchmark_symbol = str(benchmark or BENCH["US"]).strip().upper()
    if not symbol:
        return _empty_payload("", period, "Ticker is required.")
    metadata = read_cached_ohlcv_metadata(
        [symbol, benchmark_symbol],
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
    benchmark_frame = metadata.get(benchmark_symbol, {}).get("frame") if benchmark_symbol else None
    rs_frame = _relative_strength_frame(
        frame,
        benchmark_frame if isinstance(benchmark_frame, pd.DataFrame) else pd.DataFrame(),
        max_points=max_points,
    )
    latest_rs = rs_frame.iloc[-1].to_dict() if not rs_frame.empty else {}

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
            "benchmark": benchmark_symbol,
            "benchmark_available": bool(isinstance(benchmark_frame, pd.DataFrame) and not benchmark_frame.empty),
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
            "rs_ratio": _float_or_none(latest_rs.get("rs_ratio")),
            "rs_slope": _series_slope(rs_frame["rs_ratio"]) if "rs_ratio" in rs_frame else None,
            "momentum_12w": _float_or_none(latest_rs.get("momentum_12w")),
            "momentum_52w": _float_or_none(latest_rs.get("momentum_52w")),
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
        "relative_strength_series": [
            {
                "date": _date_text(row["date"]),
                "rs_ratio": _float_or_none(row["rs_ratio"]),
                "momentum_12w": _float_or_none(row["momentum_12w"]),
                "momentum_52w": _float_or_none(row["momentum_52w"]),
            }
            for row in rs_frame.to_dict(orient="records")
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
        "source": {
            "mode": "cache-only",
            "provider": "",
            "updated_at": "",
            "row_count": 0,
            "weekly_row_count": 0,
            "benchmark": BENCH["US"],
            "benchmark_available": False,
        },
        "latest": {
            "date": "",
            "close": None,
            "ma30w": None,
            "above_30wma": None,
            "ma30w_slope": None,
            "cmf21": None,
            "obv": None,
            "obv_slope": None,
            "rs_ratio": None,
            "rs_slope": None,
            "momentum_12w": None,
            "momentum_52w": None,
        },
        "series": [],
        "flow_series": [],
        "relative_strength_series": [],
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


def _relative_strength_frame(
    frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    *,
    max_points: int,
) -> pd.DataFrame:
    if frame.empty or benchmark_frame.empty:
        return pd.DataFrame(columns=["date", "rs_ratio", "momentum_12w", "momentum_52w"])
    weekly = to_weekly(frame).dropna(subset=["close"])
    benchmark_weekly = to_weekly(benchmark_frame).dropna(subset=["close"])
    if weekly.empty or benchmark_weekly.empty:
        return pd.DataFrame(columns=["date", "rs_ratio", "momentum_12w", "momentum_52w"])
    close = close_price(weekly).astype(float)
    benchmark_close = close_price(benchmark_weekly).astype(float)
    aligned = pd.concat({"close": close, "benchmark": benchmark_close}, axis=1).dropna()
    aligned = aligned[(aligned["close"] > 0) & (aligned["benchmark"] > 0)]
    if aligned.empty:
        return pd.DataFrame(columns=["date", "rs_ratio", "momentum_12w", "momentum_52w"])
    relative = aligned["close"] / aligned["benchmark"]
    base = float(relative.iloc[0]) or 1.0
    rs_ratio = relative / base * 100.0
    momentum_12w = aligned["close"].pct_change(12)
    momentum_52w = aligned["close"].pct_change(52)
    rows = pd.DataFrame(
        {
            "date": aligned.index,
            "rs_ratio": rs_ratio.to_numpy(),
            "momentum_12w": momentum_12w.to_numpy(),
            "momentum_52w": momentum_52w.to_numpy(),
        }
    )
    return rows.dropna(how="all", subset=["rs_ratio", "momentum_12w", "momentum_52w"]).tail(max(1, int(max_points)))


def _series_slope(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna().tail(12)
    if len(values) < 2:
        return None
    return float(values.iloc[-1] - values.iloc[0])


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
