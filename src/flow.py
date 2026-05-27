"""Pillar 7 - volume & institutional money flow.

LIVE from OHLCV: CMF, OBV slope, MFI, RVOL, distribution days, OBV divergence.
ETF primary flow can be enabled with FLOW_STUB_MODE=false plus Massive/source
configuration. Other provider-backed signals stay neutral until wired.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import requests


def _resolve_secret(name: str) -> Optional[str]:
    try:
        import streamlit as st  # type: ignore
        from streamlit.errors import StreamlitSecretNotFoundError  # type: ignore

        if hasattr(st, "secrets"):
            try:
                value = st.secrets.get(name)
                if value:
                    return str(value).strip()
            except (KeyError, StreamlitSecretNotFoundError):
                pass
    except ImportError:
        pass
    value = os.environ.get(name)
    return value.strip() if value else None


def _config_flag(name: str, default: bool) -> bool:
    value = _resolve_secret(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


STUB_MODE = True
ETF_PRIMARY_FLOW_STUB_MODE = _config_flag("FLOW_STUB_MODE", True)
MASSIVE_TRADES_STUB_MODE = _config_flag("MASSIVE_TRADES_STUB_MODE", True)
FINRA_ATS_STUB_MODE = _config_flag("FINRA_ATS_STUB_MODE", True)
FINRA_SHORT_INTEREST_STUB_MODE = _config_flag("FINRA_SHORT_INTEREST_STUB_MODE", True)
SEC_13F_STUB_MODE = _config_flag("SEC_13F_STUB_MODE", True)
MASSIVE_BROWSER_URL = "https://render.joinmassive.com/browser"
MASSIVE_STOCK_TRADES_URL_TEMPLATE = "https://api.massive.com/v3/trades/{ticker}"
FINRA_ATS_WEEKLY_SUMMARY_URL = "https://api.finra.org/data/group/otcMarket/name/weeklySummary"
FINRA_SHORT_INTEREST_URL = "https://api.finra.org/data/group/otcmarket/name/consolidatedShortInterest"
PRIMARY_FLOW_SOURCE_ENV_PREFIX = "ETF_PRIMARY_FLOW_URL_"
BLOCK_TRADE_MIN_SHARES = 10_000
BLOCK_TRADE_MIN_NOTIONAL = 200_000.0
_PROVIDER_FLOW_RUNTIME_HEALTH: dict[str, dict[str, object]] = {}


def reset_provider_flow_runtime_health() -> None:
    """Clear in-process provider-flow diagnostics, primarily for tests and QA runs."""
    _PROVIDER_FLOW_RUNTIME_HEALTH.clear()


def _provider_runtime_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _record_provider_flow_runtime_health(
    row_id: str,
    *,
    ticker: str,
    status: str,
    mode: str,
    value: Optional[float] = None,
    error: BaseException | None = None,
    note: str = "",
) -> None:
    symbol = str(ticker).upper()
    completed_at = _provider_runtime_timestamp()
    event_parts = [f"{symbol} {mode}"]
    if value is not None:
        event_parts.append(f"value={float(value):.4g}")
    if error is not None:
        event_parts.append(f"error={type(error).__name__}")
    if note:
        event_parts.append(note)
    event_detail = "; ".join(event_parts)
    entry = _PROVIDER_FLOW_RUNTIME_HEALTH.setdefault(
        row_id,
        {
            "last_completed": completed_at,
            "total_count": 0,
            "status_counts": {},
            "mode_counts": {},
            "samples": [],
            "events": [],
        },
    )
    entry["last_completed"] = completed_at
    entry["total_count"] = int(entry.get("total_count", 0)) + 1
    status_counts = dict(entry.get("status_counts", {}) or {})
    status_counts[status] = int(status_counts.get(status, 0)) + 1
    entry["status_counts"] = status_counts
    mode_counts = dict(entry.get("mode_counts", {}) or {})
    mode_counts[mode] = int(mode_counts.get(mode, 0)) + 1
    entry["mode_counts"] = mode_counts
    samples = list(entry.get("samples", []) or [])
    if symbol not in samples and len(samples) < 5:
        samples.append(symbol)
    entry["samples"] = samples
    events = list(entry.get("events", []) or [])
    if len(events) < 5:
        events.append(event_detail)
    entry["events"] = events


def _merge_provider_runtime_health(row: dict[str, str], *, stubbed: bool) -> dict[str, str]:
    if stubbed or str(row.get("mode", "")).startswith("missing "):
        return row
    runtime = _PROVIDER_FLOW_RUNTIME_HEALTH.get(str(row.get("id", "")))
    if not runtime:
        return row
    total_count = int(runtime.get("total_count", 0))
    status_counts = dict(runtime.get("status_counts", {}) or {})
    mode_counts = dict(runtime.get("mode_counts", {}) or {})
    samples = [str(item) for item in (runtime.get("samples", []) or [])]
    events = [str(item) for item in (runtime.get("events", []) or [])]
    last_completed = str(runtime.get("last_completed", ""))
    if total_count <= 1:
        status = next(iter(status_counts), str(row.get("status", "info")))
        mode = next(iter(mode_counts), str(row.get("mode", "unknown")))
        detail = f"last completed {last_completed}; {events[0]}" if events else str(row.get("detail", ""))
        return {**row, "status": status, "mode": mode, "detail": detail}

    healthy_count = int(status_counts.get("healthy", 0))
    warning_count = total_count - healthy_count
    status = "warning" if warning_count else "healthy"
    mode = f"{healthy_count} live ok / {warning_count} warning" if warning_count else f"{healthy_count} live ok"
    detail_parts = [
        f"last completed {last_completed}",
        f"{healthy_count} live ok, {warning_count} warning across {total_count} tickers",
    ]
    if samples:
        detail_parts.append(f"sample tickers: {', '.join(samples)}")
    warning_events = [event for event in events if " live ok" not in event]
    if warning_events:
        detail_parts.append(f"warnings: {'; '.join(warning_events)}")
    return {**row, "status": status, "mode": mode, "detail": "; ".join(detail_parts)}


def provider_flow_feeds_stubbed(statuses: Iterable[dict[str, str]] | None = None) -> bool:
    """Return True only when every optional provider-flow feed is in neutral stub mode."""
    rows = list(statuses) if statuses is not None else provider_flow_health_statuses()
    optional_rows = [row for row in rows if row.get("id") != "ohlcv_derived"]
    return bool(optional_rows) and all(str(row.get("mode", "")).startswith("stubbed") for row in optional_rows)


def _provider_health_row(
    *,
    row_id: str,
    label: str,
    provider: str,
    signal: str,
    stubbed: bool,
    required_secrets: tuple[str, ...] = (),
    detail: str = "",
) -> dict[str, str]:
    if stubbed:
        return {
            "id": row_id,
            "label": label,
            "provider": provider,
            "signal": signal,
            "status": "info",
            "mode": "stubbed neutral",
            "detail": detail or f"{signal} is held at its neutral default.",
        }
    missing = tuple(secret for secret in required_secrets if not _resolve_secret(secret))
    if missing:
        return {
            "id": row_id,
            "label": label,
            "provider": provider,
            "signal": signal,
            "status": "warning",
            "mode": f"missing {', '.join(missing)}",
            "detail": detail or f"{signal} is enabled but not fully configured.",
        }
    return {
        "id": row_id,
        "label": label,
        "provider": provider,
        "signal": signal,
        "status": "healthy",
        "mode": "enabled",
        "detail": detail or f"{signal} provider path is configured.",
    }


def provider_flow_health_statuses() -> list[dict[str, str]]:
    """Return secret-safe per-provider flow readiness for dashboard health UI."""
    return [
        {
            "id": "ohlcv_derived",
            "label": "OHLCV-derived flow",
            "provider": "Market OHLCV",
            "signal": "CMF/OBV/MFI/RVOL/distribution",
            "status": "healthy",
            "mode": "live from market lane",
            "detail": "CMF, OBV, MFI, RVOL, and distribution-day signals update from refreshed OHLCV.",
        },
        _merge_provider_runtime_health(
            _provider_health_row(
                row_id="etf_primary_flow",
                label="ETF primary flow",
                provider="Massive browser",
                signal="etf_flow_5d_pct",
                stubbed=ETF_PRIMARY_FLOW_STUB_MODE,
                required_secrets=("MASSIVE_API_KEY",),
                detail="Uses ticker-specific ETF_PRIMARY_FLOW_URL_* sources through Massive browser when configured.",
            ),
            stubbed=ETF_PRIMARY_FLOW_STUB_MODE,
        ),
        _merge_provider_runtime_health(
            _provider_health_row(
                row_id="massive_block_trades",
                label="Massive block trades",
                provider="Massive",
                signal="block_up_ratio",
                stubbed=MASSIVE_TRADES_STUB_MODE,
                required_secrets=("MASSIVE_API_KEY",),
                detail="Reads recent trade prints to estimate upside/downside block-trade pressure.",
            ),
            stubbed=MASSIVE_TRADES_STUB_MODE,
        ),
        _merge_provider_runtime_health(
            _provider_health_row(
                row_id="finra_ats_dark_pool",
                label="FINRA ATS dark pool",
                provider="FINRA",
                signal="dark_pool_pct",
                stubbed=FINRA_ATS_STUB_MODE,
                detail="Uses FINRA ATS weekly summaries; no API key is required.",
            ),
            stubbed=FINRA_ATS_STUB_MODE,
        ),
        _merge_provider_runtime_health(
            _provider_health_row(
                row_id="finra_short_interest",
                label="FINRA short interest",
                provider="FINRA",
                signal="si_delta_15d",
                stubbed=FINRA_SHORT_INTEREST_STUB_MODE,
                detail="Uses FINRA consolidated short-interest records; no API key is required.",
            ),
            stubbed=FINRA_SHORT_INTEREST_STUB_MODE,
        ),
        _merge_provider_runtime_health(
            _provider_health_row(
                row_id="sec_13f",
                label="SEC 13F",
                provider="SEC",
                signal="thirteen_f_q",
                stubbed=SEC_13F_STUB_MODE,
                required_secrets=("SEC_13F_DATA_URL", "SEC_USER_AGENT"),
                detail="Uses a configured 13F information-table archive plus SEC-compliant User-Agent.",
            ),
            stubbed=SEC_13F_STUB_MODE,
        ),
    ]


@dataclass(frozen=True)
class PrimaryFlowSnapshot:
    as_of: str
    shares_outstanding: float
    nav: float
    aum: float


def _date_sort_key(value: str):
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return (0, datetime.strptime(text, fmt).date())
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, errors="raise")
        return (0, parsed.date())
    except Exception:
        return (1, text)


def _has_parseable_date(value: str) -> bool:
    return _date_sort_key(value)[0] == 0


def _parse_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    multiplier = 1.0
    suffix = text[-1:].upper()
    if suffix in {"K", "M", "B", "T"}:
        multiplier = {
            "K": 1_000.0,
            "M": 1_000_000.0,
            "B": 1_000_000_000.0,
            "T": 1_000_000_000_000.0,
        }[suffix]
        text = text[:-1]
    try:
        return float(text.replace(",", "").replace("$", "")) * multiplier
    except ValueError:
        pass
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _pick(record: dict, names: Iterable[str]):
    normalized = {str(k).strip().lower().replace(" ", "_"): v for k, v in record.items()}
    for name in names:
        key = name.lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]
    return None


def _snapshot_from_record(record: dict) -> Optional[PrimaryFlowSnapshot]:
    as_of = _pick(record, ["as_of", "as of", "date", "trade_date", "holdings_date"])
    shares = _parse_float(_pick(record, ["shares_outstanding", "shares outstanding", "sho", "sharesOutstanding"]))
    nav = _parse_float(_pick(record, ["nav", "net_asset_value", "net asset value"]))
    aum = _parse_float(_pick(record, ["aum", "net_assets", "net assets", "total_net_assets", "total net assets"]))
    if as_of is None or shares is None or nav is None or aum is None or aum == 0:
        return None
    return PrimaryFlowSnapshot(str(as_of).strip(), shares, nav, aum)


def _records_from_json(payload: str) -> list[dict]:
    parsed = json.loads(payload)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        for key in ("records", "data", "snapshots", "rows"):
            rows = parsed.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _records_from_csv(payload: str) -> list[dict]:
    lines = [line for line in payload.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if ("shares" in lowered or "sho" in lowered) and ("nav" in lowered or "net asset" in lowered):
            reader = csv.DictReader(io.StringIO("\n".join(lines[idx:])))
            return [row for row in reader]
    reader = csv.DictReader(io.StringIO(payload))
    return [row for row in reader] if reader.fieldnames else []


def parse_primary_flow_snapshots(payload: str) -> list[PrimaryFlowSnapshot]:
    if not payload or not payload.strip():
        return []
    records: list[dict]
    try:
        records = _records_from_json(payload)
    except json.JSONDecodeError:
        records = _records_from_csv(payload)
    snapshots = [_snapshot_from_record(record) for record in records]
    return sorted([snapshot for snapshot in snapshots if snapshot is not None], key=lambda item: _date_sort_key(item.as_of))


def primary_flow_5d_pct_from_snapshots(
    snapshots: list[PrimaryFlowSnapshot],
    lookback_observations: int = 5,
) -> Optional[float]:
    dated_snapshots = [snapshot for snapshot in snapshots if _has_parseable_date(snapshot.as_of)]
    if len(dated_snapshots) <= lookback_observations:
        return None
    ordered = sorted(dated_snapshots, key=lambda item: _date_sort_key(item.as_of))
    latest = ordered[-1]
    if latest.aum == 0:
        return None
    window = ordered[-lookback_observations - 1:]
    estimated_net_flow = sum(
        (current.shares_outstanding - prior.shares_outstanding) * current.nav
        for prior, current in zip(window, window[1:])
    )
    return float(estimated_net_flow / latest.aum * 100.0)


def chaikin_money_flow(df, period=21):
    if len(df) < period + 1:
        return None
    high = df["high"]; low = df["low"]; close = df["close"]; vol = df["volume"]
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    mfv = (mfm * vol).fillna(0)
    cmf = mfv.rolling(period).sum() / vol.rolling(period).sum().replace(0, np.nan)
    return float(cmf.iloc[-1]) if not pd.isna(cmf.iloc[-1]) else None


def on_balance_volume(df):
    sign = np.sign(df["close"].diff().fillna(0))
    return (sign * df["volume"]).cumsum()


def obv_slope(df, lookback=20):
    if len(df) < lookback + 5:
        return None
    obv = on_balance_volume(df).iloc[-lookback:]
    if len(obv) < lookback or obv.std() == 0:
        return None
    x = np.arange(len(obv))
    slope = np.polyfit(x, obv.values, 1)[0]
    norm = np.mean(np.abs(obv.values)) or 1.0
    return float(slope / norm)


def money_flow_index(df, period=14):
    if len(df) < period + 2:
        return None
    typ = (df["high"] + df["low"] + df["close"]) / 3
    rmf = typ * df["volume"]
    pos = rmf.where(typ > typ.shift(), 0.0)
    neg = rmf.where(typ < typ.shift(), 0.0)
    pos_sum = pos.rolling(period).sum()
    neg_sum = neg.rolling(period).sum().replace(0, np.nan)
    mfr = pos_sum / neg_sum
    mfi = 100 - 100 / (1 + mfr)
    return float(mfi.iloc[-1]) if not pd.isna(mfi.iloc[-1]) else None


def relative_volume(df, lookback=20):
    if len(df) < lookback + 1:
        return None
    avg = df["volume"].iloc[-lookback - 1:-1].mean()
    if avg == 0:
        return None
    return float(df["volume"].iloc[-1] / avg)


def distribution_day_count(df, window=25):
    if len(df) < window + 21:
        return None
    sub = df.iloc[-(window + 20):].copy()
    sub["vavg20"] = sub["volume"].rolling(20).mean()
    recent = sub.iloc[-window:]
    rng = (recent["high"] - recent["low"]).replace(0, np.nan)
    pct_in_range = (recent["close"] - recent["low"]) / rng
    is_dist = (
        (pct_in_range < 0.25)
        & (recent["volume"] >= 1.5 * recent["vavg20"])
        & (recent["close"] < recent["close"].shift(1))
    )
    return int(is_dist.fillna(False).sum())


def obv_price_divergence(df, lookback=20):
    if len(df) < lookback + 1:
        return None
    close = df["close"]
    obv = on_balance_volume(df)
    price_new_high = close.iloc[-1] >= close.iloc[-lookback:].max()
    obv_new_high = obv.iloc[-1] >= obv.iloc[-lookback:].max()
    return bool(price_new_high and not obv_new_high)


def _primary_flow_source_url(ticker: str) -> Optional[str]:
    key = f"{PRIMARY_FLOW_SOURCE_ENV_PREFIX}{ticker.upper().replace('-', '_')}"
    return _resolve_secret(key)


def _fetch_massive_browser_content(
    source_url: str,
    api_key: Optional[str] = None,
    timeout: int = 20,
) -> Optional[str]:
    token = api_key or _resolve_secret("MASSIVE_API_KEY")
    if not token:
        return None
    try:
        response = requests.get(
            MASSIVE_BROWSER_URL,
            params={
                "url": source_url,
                "format": "raw",
                "expiration": 0,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException:
        return None


def _fetch_primary_flow_payload(ticker: str) -> Optional[str]:
    source_url = _primary_flow_source_url(ticker)
    if not source_url:
        return None
    return _fetch_massive_browser_content(source_url)


def etf_primary_flow_5d_pct(ticker):
    if ETF_PRIMARY_FLOW_STUB_MODE:
        return 0.0
    try:
        payload = _fetch_primary_flow_payload(ticker)
    except requests.RequestException as exc:
        _record_provider_flow_runtime_health(
            "etf_primary_flow",
            ticker=ticker,
            status="warning",
            mode="request error neutral",
            error=exc,
        )
        return 0.0
    if not payload:
        source_key = f"{PRIMARY_FLOW_SOURCE_ENV_PREFIX}{str(ticker).upper().replace('-', '_')}"
        mode = "no provider payload neutral"
        note = ""
        if not _primary_flow_source_url(ticker):
            mode = "missing ticker source"
            note = f"missing {source_key}"
        _record_provider_flow_runtime_health(
            "etf_primary_flow",
            ticker=ticker,
            status="warning",
            mode=mode,
            note=note,
        )
        return 0.0
    snapshots = parse_primary_flow_snapshots(payload)
    value = primary_flow_5d_pct_from_snapshots(snapshots)
    if value is None:
        _record_provider_flow_runtime_health(
            "etf_primary_flow",
            ticker=ticker,
            status="warning",
            mode="no usable records neutral",
        )
        return 0.0
    result = float(value)
    _record_provider_flow_runtime_health(
        "etf_primary_flow",
        ticker=ticker,
        status="healthy",
        mode="live ok",
        value=result,
    )
    return result


def _neutral_float(value: Optional[float], neutral: float) -> float:
    if value is None:
        return neutral
    try:
        number = float(value)
    except (TypeError, ValueError):
        return neutral
    return number if np.isfinite(number) else neutral


def _trade_timestamp(trade: dict) -> float:
    value = _pick(trade, ["sip_timestamp", "participant_timestamp", "trf_timestamp", "timestamp", "t"])
    parsed = _parse_float(value)
    return parsed if parsed is not None else 0.0


def _trade_price_and_size(trade: dict) -> tuple[Optional[float], Optional[float]]:
    return (
        _parse_float(_pick(trade, ["p", "price"])),
        _parse_float(_pick(trade, ["s", "size", "volume"])),
    )


def block_trade_upside_ratio_from_massive_trades(trades: list[dict]) -> Optional[float]:
    clean_trades = []
    for trade in trades:
        correction = _parse_float(_pick(trade, ["correction", "c"]))
        if correction not in (None, 0.0):
            continue
        price, size = _trade_price_and_size(trade)
        if price is None or size is None or price <= 0 or size <= 0:
            continue
        clean_trades.append((float(_trade_timestamp(trade)), price, size))
    clean_trades.sort(key=lambda item: item[0])

    upside_notional = 0.0
    downside_notional = 0.0
    previous_price: Optional[float] = None
    for _, price, size in clean_trades:
        notional = price * size
        is_block = size >= BLOCK_TRADE_MIN_SHARES or notional >= BLOCK_TRADE_MIN_NOTIONAL
        if is_block and previous_price is not None:
            if price > previous_price:
                upside_notional += notional
            elif price < previous_price:
                downside_notional += notional
        previous_price = price

    if upside_notional == 0.0 and downside_notional == 0.0:
        return None
    if downside_notional == 0.0:
        return 2.0
    return upside_notional / downside_notional


def _fetch_massive_stock_trades(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5_000,
    timeout: int = 20,
) -> list[dict]:
    token = _resolve_secret("MASSIVE_API_KEY")
    if not token:
        return []
    params: dict[str, str | int] = {
        "limit": int(limit),
        "sort": "timestamp",
        "order": "desc",
    }
    if start_date:
        params["timestamp.gte"] = start_date
    if end_date:
        params["timestamp.lt"] = end_date
    response = requests.get(
        MASSIVE_STOCK_TRADES_URL_TEMPLATE.format(ticker=str(ticker).upper()),
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return []
    results = payload.get("results", [])
    return [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []


def _provider_block_trade_upside_ratio(ticker) -> Optional[float]:
    return block_trade_upside_ratio_from_massive_trades(_fetch_massive_stock_trades(ticker))


def block_trade_upside_ratio(ticker):
    if MASSIVE_TRADES_STUB_MODE:
        return 1.0
    try:
        value = _provider_block_trade_upside_ratio(ticker)
    except requests.RequestException as exc:
        _record_provider_flow_runtime_health(
            "massive_block_trades",
            ticker=ticker,
            status="warning",
            mode="request error neutral",
            error=exc,
        )
        return 1.0
    if value is None:
        _record_provider_flow_runtime_health(
            "massive_block_trades",
            ticker=ticker,
            status="warning",
            mode="no provider data neutral",
        )
        return 1.0
    result = _neutral_float(value, 1.0)
    _record_provider_flow_runtime_health(
        "massive_block_trades",
        ticker=ticker,
        status="healthy" if result == value else "warning",
        mode="live ok" if result == value else "invalid provider value neutral",
        value=result,
    )
    return result


def _provider_dark_pool_pct(ticker) -> Optional[float]:
    return dark_pool_pct_from_finra_ats_records(_fetch_finra_ats_weekly_summary(ticker))


def dark_pool_pct_from_finra_ats_records(records: list[dict]) -> Optional[float]:
    rows = [record for record in records if isinstance(record, dict)]
    if not rows:
        return None
    latest_key = max(_record_date_key(record) for record in rows)
    latest_rows = [record for record in rows if _record_date_key(record) == latest_key]
    ats_shares = 0.0
    total_shares = 0.0
    for record in latest_rows:
        shares = _parse_float(_pick(record, ["totalWeeklyShareQuantity", "totalWeeklyShares", "shares"]))
        if shares is None or shares < 0:
            continue
        total_shares += shares
        summary_type = str(_pick(record, ["summaryTypeCode", "summary_type"]) or "").upper()
        if "ATS" in summary_type:
            ats_shares += shares
    if total_shares <= 0:
        return None
    return ats_shares / total_shares


def _fetch_finra_ats_weekly_summary(ticker: str, limit: int = 40, timeout: int = 20) -> list[dict]:
    payload = {
        "fields": [
            "issueSymbolIdentifier",
            "weekStartDate",
            "summaryTypeCode",
            "totalWeeklyShareQuantity",
            "totalWeeklyTradeCount",
        ],
        "compareFilters": [
            {
                "compareType": "EQUAL",
                "fieldName": "issueSymbolIdentifier",
                "fieldValue": str(ticker).upper(),
            }
        ],
        "limit": int(limit),
    }
    response = requests.post(
        FINRA_ATS_WEEKLY_SUMMARY_URL,
        json=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        records = data.get("data") or data.get("results") or data.get("rows") or []
        return [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []
    return []


def dark_pool_pct(ticker):
    if FINRA_ATS_STUB_MODE:
        return 0.40
    try:
        value = _provider_dark_pool_pct(ticker)
    except requests.RequestException as exc:
        _record_provider_flow_runtime_health(
            "finra_ats_dark_pool",
            ticker=ticker,
            status="warning",
            mode="request error neutral",
            error=exc,
        )
        return 0.40
    if value is None:
        _record_provider_flow_runtime_health(
            "finra_ats_dark_pool",
            ticker=ticker,
            status="warning",
            mode="no provider data neutral",
        )
        return 0.40
    result = _neutral_float(value, 0.40)
    _record_provider_flow_runtime_health(
        "finra_ats_dark_pool",
        ticker=ticker,
        status="healthy" if result == value else "warning",
        mode="live ok" if result == value else "invalid provider value neutral",
        value=result,
    )
    return result


def _provider_short_interest_delta_15d(ticker) -> Optional[float]:
    return short_interest_delta_from_finra_records(_fetch_finra_short_interest(ticker))


def _record_date_key(record: dict):
    return _date_sort_key(
        str(_pick(record, ["settlementDate", "settlement_date", "weekStartDate", "week_start_date", "date"]) or "")
    )


def short_interest_delta_from_finra_records(records: list[dict]) -> Optional[float]:
    ordered = sorted([record for record in records if isinstance(record, dict)], key=_record_date_key)
    if not ordered:
        return None
    latest = ordered[-1]
    reported = _parse_float(
        _pick(latest, ["changePercent", "change_percent", "changePercentQuantity", "change percent"])
    )
    if reported is not None:
        return reported

    latest_position = _parse_float(
        _pick(latest, ["currentShortPositionQuantity", "shortPositionQuantity", "short_position"])
    )
    previous_position = _parse_float(
        _pick(latest, ["previousShortPositionQuantity", "previous_short_position"])
    )
    if previous_position is None and len(ordered) >= 2:
        previous_position = _parse_float(
            _pick(ordered[-2], ["currentShortPositionQuantity", "shortPositionQuantity", "short_position"])
        )
    if latest_position is None or previous_position in (None, 0.0):
        return None
    return (latest_position - previous_position) / previous_position * 100.0


def _fetch_finra_short_interest(ticker: str, limit: int = 4, timeout: int = 20) -> list[dict]:
    payload = {
        "fields": [
            "symbolCode",
            "settlementDate",
            "currentShortPositionQuantity",
            "previousShortPositionQuantity",
            "changePercent",
            "daysToCoverQuantity",
        ],
        "compareFilters": [
            {
                "compareType": "EQUAL",
                "fieldName": "symbolCode",
                "fieldValue": str(ticker).upper(),
            }
        ],
        "limit": int(limit),
    }
    response = requests.post(
        FINRA_SHORT_INTEREST_URL,
        json=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        records = data.get("data") or data.get("results") or data.get("rows") or []
        return [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []
    return []


def short_interest_delta_15d(ticker):
    if FINRA_SHORT_INTEREST_STUB_MODE:
        return 0.0
    try:
        value = _provider_short_interest_delta_15d(ticker)
    except requests.RequestException as exc:
        _record_provider_flow_runtime_health(
            "finra_short_interest",
            ticker=ticker,
            status="warning",
            mode="request error neutral",
            error=exc,
        )
        return 0.0
    if value is None:
        _record_provider_flow_runtime_health(
            "finra_short_interest",
            ticker=ticker,
            status="warning",
            mode="no provider data neutral",
        )
        return 0.0
    result = _neutral_float(value, 0.0)
    _record_provider_flow_runtime_health(
        "finra_short_interest",
        ticker=ticker,
        status="healthy" if result == value else "warning",
        mode="live ok" if result == value else "invalid provider value neutral",
        value=result,
    )
    return result


def _provider_thirteen_f_net_buys_q(ticker) -> Optional[float]:
    cusips = _sec_13f_cusips_for_ticker(ticker)
    if not cusips:
        return None
    return thirteen_f_net_buys_from_sec_records(_fetch_sec_13f_records(), cusips)


def _sec_13f_cusips_for_ticker(ticker: str) -> list[str]:
    value = _resolve_secret(f"SEC_13F_CUSIP_{str(ticker).upper().replace('-', '_')}")
    if not value:
        return []
    return [item.strip().upper() for item in str(value).split(",") if item.strip()]


def _sec_record_period_key(record: dict):
    return _date_sort_key(
        str(_pick(record, ["REPORTCALENDARORQUARTER", "reportCalendarOrQuarter", "periodOfReport", "period"]) or "")
    )


def thirteen_f_net_buys_from_sec_records(records: list[dict], cusips: list[str]) -> Optional[float]:
    wanted = {cusip.upper().replace(" ", "") for cusip in cusips}
    rows = []
    for record in records:
        cusip = str(_pick(record, ["CUSIP", "cusip"]) or "").upper().replace(" ", "")
        if cusip not in wanted:
            continue
        shares = _parse_float(_pick(record, ["SSHPRNAMT", "sshPrnamt", "shares", "value"]))
        if shares is None:
            continue
        rows.append((_sec_record_period_key(record), shares))
    if len(rows) < 2:
        return None
    totals: dict[tuple, float] = {}
    for period_key, shares in rows:
        totals[period_key] = totals.get(period_key, 0.0) + shares
    if len(totals) < 2:
        return None
    ordered_periods = sorted(totals)
    previous = totals[ordered_periods[-2]]
    latest = totals[ordered_periods[-1]]
    if previous == 0:
        return None
    return (latest - previous) / previous * 100.0


def _records_from_tsv(payload: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(payload), delimiter="\t")
    return [row for row in reader] if reader.fieldnames else []


def _fetch_sec_13f_records(
    data_url: Optional[str] = None,
    user_agent: Optional[str] = None,
    timeout: int = 20,
) -> list[dict]:
    url = data_url or _resolve_secret("SEC_13F_DATA_URL")
    agent = user_agent or _resolve_secret("SEC_USER_AGENT")
    if not url or not agent:
        return []
    response = requests.get(url, headers={"User-Agent": agent}, timeout=timeout)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in archive.namelist():
            upper = name.upper()
            if "INFOTABLE" not in upper or not upper.endswith((".TSV", ".TXT", ".CSV")):
                continue
            raw = archive.read(name).decode("utf-8-sig")
            if upper.endswith(".CSV"):
                reader = csv.DictReader(io.StringIO(raw))
                return [row for row in reader] if reader.fieldnames else []
            return _records_from_tsv(raw)
    return []


def thirteen_f_net_buys_q(ticker):
    if SEC_13F_STUB_MODE:
        return 0.0
    try:
        value = _provider_thirteen_f_net_buys_q(ticker)
    except requests.RequestException as exc:
        _record_provider_flow_runtime_health(
            "sec_13f",
            ticker=ticker,
            status="warning",
            mode="request error neutral",
            error=exc,
        )
        return 0.0
    if value is None:
        _record_provider_flow_runtime_health(
            "sec_13f",
            ticker=ticker,
            status="warning",
            mode="no provider data neutral",
            note="missing CUSIP mapping or insufficient 13F records",
        )
        return 0.0
    result = _neutral_float(value, 0.0)
    _record_provider_flow_runtime_health(
        "sec_13f",
        ticker=ticker,
        status="healthy" if result == value else "warning",
        mode="live ok" if result == value else "invalid provider value neutral",
        value=result,
    )
    return result


def compute_flow_signals(ohlcv):
    reset_provider_flow_runtime_health()
    rows = []
    for t, df in ohlcv.items():
        if str(t).startswith("^"):
            continue
        rows.append({
            "ticker":          t,
            "cmf21":           chaikin_money_flow(df, 21),
            "obv_slope":       obv_slope(df, 20),
            "mfi14":           money_flow_index(df, 14),
            "rvol":            relative_volume(df, 20),
            "dist_days_25":    distribution_day_count(df, 25),
            "obv_divergence":  obv_price_divergence(df, 20),
            "etf_flow_5d_pct": etf_primary_flow_5d_pct(t),
            "block_up_ratio":  block_trade_upside_ratio(t),
            "dark_pool_pct":   dark_pool_pct(t),
            "si_delta_15d":    short_interest_delta_15d(t),
            "thirteen_f_q":    thirteen_f_net_buys_q(t),
        })
    return pd.DataFrame(rows).set_index("ticker")


def flow_composite_z(flow_df):
    def _z(s):
        s = s.astype(float)
        std = s.std(ddof=0)
        if std == 0 or pd.isna(std):
            return s * 0.0
        return (s - s.mean()) / std

    z_cmf = _z(flow_df["cmf21"])
    z_obv = _z(flow_df["obv_slope"])
    z_etf = _z(flow_df["etf_flow_5d_pct"])
    z_blk = _z(flow_df["block_up_ratio"])
    z_vel = _z(flow_df["rvol"])
    z_si = _z(flow_df["si_delta_15d"]) * -1
    F = (0.30 * z_cmf + 0.20 * z_obv + 0.20 * z_etf + 0.10 * z_blk
         + 0.10 * z_vel + 0.10 * z_si).fillna(0)
    F.name = "F"
    return F
