"""Dashboard data freshness and health helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import pandas as pd

from .fred_data import FRED_SERIES
from .macro_tiles import FRED_CONTEXT_GROUPS


OHLCV_FRESH_DAYS = 5
OHLCV_STALE_DAYS = 10
FRED_DEFAULT_FRESH_DAYS = 7
FRED_SERIES_FRESH_DAYS = {
    "CPIAUCSL": 70,
    "INDPRO": 70,
    # Monthly FRED observations are usually dated at the start of the measured period.
    # Give them release-lag tolerance so current monthly data is not flagged stale.
    "RECPROUSM156N": 100,
    "PCEPILFE": 100,
    "UNRATE": 70,
    "WALCL": 14,
    "M2SL": 70,
    "CFNAI": 70,
    "ICSA": 14,
    "UMCSENT": 70,
    "NFCI": 14,
    "STLFSI4": 14,
    "DCOILWTICO": 14,
    "DHHNGSP": 14,
    "DTWEXBGS": 14,
}
LANE_REFRESH_LABELS = {
    "market_ohlcv": "Refresh market OHLCV",
    "fred_macro": "Refresh FRED macro",
    "dashboard_compute": "Recompute dashboard",
    "provider_flow": "Recompute flow signals",
}
LANE_SLA_LABELS = {
    "market_ohlcv": f"fresh <={OHLCV_FRESH_DAYS}d; stale >{OHLCV_STALE_DAYS}d",
    "fred_macro": "series cadence adjusted",
    "dashboard_compute": "snapshot <=60m",
    "provider_flow": "recomputes from current OHLCV",
}
STATUS_SYMBOLS = {
    "healthy": "OK",
    "info": "INFO",
    "warning": "WARN",
    "stale": "STALE",
}


def _now_timestamp(now: pd.Timestamp | datetime | None = None) -> pd.Timestamp:
    if now is None:
        return pd.Timestamp.now(tz="UTC")
    parsed = pd.Timestamp(now)
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _date_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    try:
        parsed = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.tz_convert("UTC").tz_localize(None)
    return parsed.normalize()


def _age_days(value: Any, now: pd.Timestamp | datetime | None = None) -> int | None:
    latest = _date_timestamp(value)
    if latest is None:
        return None
    current = _now_timestamp(now).tz_localize(None).normalize()
    return max(0, int((current - latest).days))


def format_age_label(value: Any, now: pd.Timestamp | datetime | None = None) -> str:
    age = _age_days(value, now)
    if age is None:
        return "missing"
    if age == 0:
        return "today"
    if age == 1:
        return "1d old"
    return f"{age}d old"


def _latest_frame_date(frame: pd.DataFrame | None) -> pd.Timestamp | None:
    if frame is None or frame.empty:
        return None
    try:
        index = pd.DatetimeIndex(pd.to_datetime(frame.index)).dropna()
    except Exception:
        return None
    if len(index) == 0:
        return None
    return pd.Timestamp(index.max()).normalize()


def _status_rank(status: str) -> int:
    return {"healthy": 0, "info": 0, "warning": 1, "stale": 2}.get(status, 1)


def _lane_metadata(lane_id: str, status: str) -> dict[str, object]:
    return {
        "lane_id": lane_id,
        "sla": LANE_SLA_LABELS[lane_id],
        "refresh_label": LANE_REFRESH_LABELS[lane_id],
        "refresh_key": f"data_health_refresh_{lane_id}",
        "severity_symbol": STATUS_SYMBOLS.get(status, "WARN"),
    }


def _ohlcv_health_row(
    ohlcv: Mapping[str, pd.DataFrame],
    expected_symbols: Iterable[str],
    ohlcv_result: Any,
    *,
    now: pd.Timestamp,
) -> dict[str, object]:
    expected = tuple(dict.fromkeys(str(symbol) for symbol in expected_symbols))
    latest_dates = []
    for symbol in expected:
        frame = ohlcv.get(symbol)
        if frame is None:
            frame = ohlcv.get(symbol.upper())
        latest = _latest_frame_date(frame)
        if latest is not None:
            latest_dates.append(latest)
    missing = tuple(getattr(ohlcv_result, "missing", ())) or tuple(
        symbol
        for symbol in expected
        if symbol not in ohlcv and symbol.upper() not in ohlcv
    )
    latest = max(latest_dates) if latest_dates else None
    oldest = min(latest_dates) if latest_dates else None
    latest_age = _age_days(latest, now)
    oldest_age = _age_days(oldest, now)
    stale_cache_hits = tuple(getattr(ohlcv_result, "stale_cache_hits", ()))
    warnings = tuple(getattr(ohlcv_result, "warnings", ()))

    status = "healthy"
    if oldest_age is None or not latest_dates:
        status = "stale"
    elif oldest_age > OHLCV_STALE_DAYS or missing:
        status = "stale"
    elif oldest_age > OHLCV_FRESH_DAYS or stale_cache_hits or warnings:
        status = "warning"

    detail_parts = [
        f"{len(latest_dates)}/{len(expected)} symbols loaded",
        f"provider {getattr(ohlcv_result, 'provider', 'unknown')}",
    ]
    if getattr(ohlcv_result, "cache_refresh_forced", False):
        detail_parts.append("manual refresh bypassed persistent cache")
    if oldest is not None and oldest_age is not None:
        detail_parts.append(f"oldest loaded bar {oldest.date()} ({oldest_age}d old)")
    if stale_cache_hits:
        detail_parts.append(f"{len(stale_cache_hits)} stale-cache hits")
    if missing:
        detail_parts.append(f"{len(missing)} missing")
    if warnings:
        detail_parts.append("provider warnings present")

    return {
        **_lane_metadata("market_ohlcv", status),
        "source": "Market OHLCV",
        "role": "Critical: price, volume, trend, momentum, and market proxies",
        "status": status,
        "latest": str(latest.date()) if latest is not None else "-",
        "freshness": format_age_label(latest, now),
        "age_days": latest_age,
        "oldest_age_days": oldest_age,
        "coverage": f"oldest {oldest.date()} ({oldest_age}d old)" if oldest is not None and oldest_age is not None else "",
        "detail": "; ".join(detail_parts),
    }


def _fred_items() -> list[dict[str, str]]:
    context_meta: dict[str, dict[str, str]] = {}
    for group in FRED_CONTEXT_GROUPS:
        for item in group["series"]:
            context_meta[str(item["id"])] = {
                "label": str(item["label"]),
                "group": str(group["group"]),
            }
    items: list[dict[str, str]] = []
    for series_id, label in FRED_SERIES.items():
        meta = context_meta.get(str(series_id), {})
        items.append(
            {
                "id": str(series_id),
                "label": meta.get("label", str(label)),
                "group": meta.get("group", "Regime classifier"),
            }
        )
    return items


def _latest_series_date(series: pd.Series | None) -> pd.Timestamp | None:
    if series is None:
        return None
    try:
        cleaned = series.dropna()
    except Exception:
        return None
    if cleaned.empty:
        return None
    try:
        latest_index = pd.DatetimeIndex(pd.to_datetime(cleaned.index)).dropna().max()
    except Exception:
        return None
    return _date_timestamp(latest_index)


def _fred_health_row(fred_data: Mapping[str, pd.Series], *, now: pd.Timestamp) -> dict[str, object]:
    items = _fred_items()
    stale: list[str] = []
    missing = 0
    latest_dates: list[pd.Timestamp] = []
    for item in items:
        series_id = item["id"]
        latest = _latest_series_date(fred_data.get(series_id))
        if latest is None:
            missing += 1
            continue
        latest_dates.append(latest)
        age = _age_days(latest, now)
        limit = FRED_SERIES_FRESH_DAYS.get(series_id, FRED_DEFAULT_FRESH_DAYS)
        if age is None or age > limit:
            stale.append(f"{series_id} {format_age_label(latest, now)}")

    latest = max(latest_dates) if latest_dates else None
    status = "healthy"
    if not latest_dates:
        status = "stale"
    elif stale or missing:
        status = "warning"

    detail_parts = [f"{len(latest_dates)}/{len(items)} series loaded"]
    if stale:
        detail_parts.append(f"{len(stale)} stale: {', '.join(stale[:4])}")
    if missing:
        detail_parts.append(f"{missing} missing")
    detail_parts.append("FRED freshness is cadence/release-lag adjusted")

    return {
        **_lane_metadata("fred_macro", status),
        "source": "FRED macro/regime",
        "role": "Critical when configured: business-cycle tilt and macro context",
        "status": status,
        "latest": str(latest.date()) if latest is not None else "-",
        "freshness": f"latest available: {format_age_label(latest, now)}",
        "age_days": _age_days(latest, now),
        "coverage": f"{len(stale)} stale series" if stale else "",
        "detail": "; ".join(detail_parts),
    }


def _compute_health_row(compute_created_at: float | int | None, *, now: pd.Timestamp) -> dict[str, object]:
    if compute_created_at is None:
        status = "warning"
        return {
            **_lane_metadata("dashboard_compute", status),
            "source": "Dashboard compute",
            "role": "Critical: current rendered analysis snapshot",
            "status": status,
            "latest": "-",
            "freshness": "missing",
            "detail": "No compute timestamp was recorded for this render.",
        }
    try:
        created = pd.Timestamp(datetime.fromtimestamp(float(compute_created_at), tz=timezone.utc))
    except (TypeError, ValueError, OSError):
        created = None
    if created is None:
        age_minutes = None
    else:
        age_minutes = max(0, int((now - created).total_seconds() // 60))
    status = "healthy" if age_minutes is not None and age_minutes <= 60 else "warning"
    return {
        **_lane_metadata("dashboard_compute", status),
        "source": "Dashboard compute",
        "role": "Critical: current rendered analysis snapshot",
        "status": status,
        "latest": created.strftime("%Y-%m-%d %H:%M UTC") if created is not None else "-",
        "freshness": f"{age_minutes}m old" if age_minutes is not None else "missing",
        "age_minutes": age_minutes,
        "detail": "Analysis snapshot reused for visual-only changes for up to 60 minutes.",
    }


def _provider_flow_health_row(provider_flow_stubbed: bool) -> dict[str, object]:
    if provider_flow_stubbed:
        detail = (
            "Provider-backed institutional-flow feeds are neutral/stub; "
            "OHLCV-derived CMF, OBV, MFI, RVOL, and distribution-day flow still update with market OHLCV."
        )
        status = "info"
    else:
        detail = "Provider-backed flow feeds are enabled; check provider warnings above for data gaps."
        status = "healthy"
    return {
        **_lane_metadata("provider_flow", status),
        "source": "Provider-flow feeds",
        "role": "Optional provider feeds; OHLCV-derived flow remains active",
        "status": status,
        "latest": "-",
        "freshness": "derived from market lane",
        "detail": detail,
    }


def data_health_rows(
    *,
    ohlcv: Mapping[str, pd.DataFrame],
    expected_symbols: Iterable[str],
    ohlcv_result: Any,
    fred_data: Mapping[str, pd.Series],
    compute_created_at: float | int | None,
    now: pd.Timestamp | datetime | None = None,
    provider_flow_stubbed: bool = True,
) -> list[dict[str, object]]:
    current = _now_timestamp(now)
    return [
        _ohlcv_health_row(ohlcv, expected_symbols, ohlcv_result, now=current),
        _fred_health_row(fred_data, now=current),
        _compute_health_row(compute_created_at, now=current),
        _provider_flow_health_row(provider_flow_stubbed),
    ]


def dashboard_health_summary(rows: Iterable[Mapping[str, object]]) -> dict[str, str]:
    statuses = [str(row.get("status", "warning")) for row in rows]
    worst = max(statuses or ["warning"], key=_status_rank)
    labels = {
        "healthy": "Data healthy",
        "info": "Data healthy",
        "warning": "Data warning",
        "stale": "Data stale",
    }
    details = {
        "healthy": "All critical dashboard inputs are within freshness thresholds.",
        "info": "Critical dashboard inputs are healthy; some optional feeds are informational.",
        "warning": "Some inputs are lagging or partial. Review source cards before acting.",
        "stale": "At least one critical input is stale or missing. Refresh and review before acting.",
    }
    return {"status": worst, "label": labels.get(worst, "Data warning"), "detail": details.get(worst, details["warning"])}
