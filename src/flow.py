"""Pillar 7 - volume & institutional money flow.

LIVE from OHLCV: CMF, OBV slope, MFI, RVOL, distribution days, OBV divergence.
ETF primary flow can be enabled with FLOW_STUB_MODE=false plus Massive/source
configuration. Other provider-backed signals stay neutral until wired.
"""
from __future__ import annotations

import csv
from datetime import datetime
import io
import json
import os
import re
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
PRIMARY_FLOW_SOURCE_ENV_PREFIX = "ETF_PRIMARY_FLOW_URL_"


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
    except requests.RequestException:
        return 0.0
    if not payload:
        return 0.0
    snapshots = parse_primary_flow_snapshots(payload)
    value = primary_flow_5d_pct_from_snapshots(snapshots)
    return float(value) if value is not None else 0.0


def _neutral_float(value: Optional[float], neutral: float) -> float:
    if value is None:
        return neutral
    try:
        number = float(value)
    except (TypeError, ValueError):
        return neutral
    return number if np.isfinite(number) else neutral


def _provider_block_trade_upside_ratio(ticker) -> Optional[float]:
    return None


def block_trade_upside_ratio(ticker):
    if MASSIVE_TRADES_STUB_MODE:
        return 1.0
    try:
        return _neutral_float(_provider_block_trade_upside_ratio(ticker), 1.0)
    except requests.RequestException:
        return 1.0


def _provider_dark_pool_pct(ticker) -> Optional[float]:
    return None


def dark_pool_pct(ticker):
    if FINRA_ATS_STUB_MODE:
        return 0.40
    try:
        return _neutral_float(_provider_dark_pool_pct(ticker), 0.40)
    except requests.RequestException:
        return 0.40


def _provider_short_interest_delta_15d(ticker) -> Optional[float]:
    return None


def short_interest_delta_15d(ticker):
    if FINRA_SHORT_INTEREST_STUB_MODE:
        return 0.0
    try:
        return _neutral_float(_provider_short_interest_delta_15d(ticker), 0.0)
    except requests.RequestException:
        return 0.0


def _provider_thirteen_f_net_buys_q(ticker) -> Optional[float]:
    return None


def thirteen_f_net_buys_q(ticker):
    if SEC_13F_STUB_MODE:
        return 0.0
    try:
        return _neutral_float(_provider_thirteen_f_net_buys_q(ticker), 0.0)
    except requests.RequestException:
        return 0.0


def compute_flow_signals(ohlcv):
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
