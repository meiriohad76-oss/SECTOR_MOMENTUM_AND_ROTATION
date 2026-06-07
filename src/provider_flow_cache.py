"""Persistent cache for optional provider-flow API responses.

The cache stores provider payloads only. It deliberately excludes credentials,
headers, and raw request URLs so it is safe for operational readiness reports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DB_PATH = ROOT / "data" / "provider_flow_cache" / "provider_flow_cache.sqlite"


@dataclass(frozen=True)
class ProviderFlowCacheRecord:
    provider: str
    lane: str
    ticker: str
    request_hash: str
    created_at_utc: str
    payload: list[dict[str, Any]]
    payload_sha256: str
    age_seconds: float
    is_fresh: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_stamp(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_provider(value: str) -> str:
    return str(value).strip().lower()


def _normalize_lane(value: str) -> str:
    return str(value).strip().lower()


def _normalize_ticker(value: str) -> str:
    return str(value).strip().upper()


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc_stamp(value)
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _stable_json(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))


def request_hash(params: Mapping[str, Any] | None = None) -> str:
    return hashlib.sha256(_stable_json(dict(params or {})).encode("utf-8")).hexdigest()


def payload_sha256(payload: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def cache_path(path: str | Path | None = None) -> Path:
    configured = path or os.environ.get("PROVIDER_FLOW_CACHE_PATH") or DEFAULT_CACHE_DB_PATH
    return Path(configured)


def initialize_provider_flow_cache(path: str | Path | None = None) -> None:
    db_path = cache_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_flow_cache (
                provider TEXT NOT NULL,
                lane TEXT NOT NULL,
                ticker TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                PRIMARY KEY (provider, lane, ticker, request_hash)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_provider_flow_cache_latest
                ON provider_flow_cache(provider, lane, ticker, created_at_utc DESC)
            """
        )


def write_provider_flow_cache(
    *,
    provider: str,
    lane: str,
    ticker: str,
    params: Mapping[str, Any] | None,
    payload: list[dict[str, Any]],
    path: str | Path | None = None,
    created_at_utc: datetime | str | None = None,
) -> ProviderFlowCacheRecord:
    rows = [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(created_at_utc, datetime):
        created_at = _utc_stamp(created_at_utc.astimezone(timezone.utc))
    elif created_at_utc:
        created_at = str(created_at_utc)
    else:
        created_at = _utc_stamp()
    digest = payload_sha256(rows)
    req_hash = request_hash(params)
    initialize_provider_flow_cache(path)
    with sqlite3.connect(cache_path(path)) as conn:
        conn.execute(
            """
            INSERT INTO provider_flow_cache (
                provider,
                lane,
                ticker,
                request_hash,
                created_at_utc,
                payload_json,
                payload_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, lane, ticker, request_hash) DO UPDATE SET
                created_at_utc = excluded.created_at_utc,
                payload_json = excluded.payload_json,
                payload_sha256 = excluded.payload_sha256
            """,
            (
                _normalize_provider(provider),
                _normalize_lane(lane),
                _normalize_ticker(ticker),
                req_hash,
                created_at,
                _stable_json(rows),
                digest,
            ),
        )
    return ProviderFlowCacheRecord(
        provider=_normalize_provider(provider),
        lane=_normalize_lane(lane),
        ticker=_normalize_ticker(ticker),
        request_hash=req_hash,
        created_at_utc=created_at,
        payload=rows,
        payload_sha256=digest,
        age_seconds=0.0,
        is_fresh=True,
    )


def _record_from_row(row: sqlite3.Row, *, ttl_seconds: int | float, now: datetime) -> ProviderFlowCacheRecord | None:
    created_at = _parse_utc(str(row["created_at_utc"]))
    if created_at is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list):
        return None
    rows = [dict(item) for item in payload if isinstance(item, Mapping)]
    if payload_sha256(rows) != str(row["payload_sha256"]):
        return None
    age = max(0.0, (now - created_at).total_seconds())
    return ProviderFlowCacheRecord(
        provider=str(row["provider"]),
        lane=str(row["lane"]),
        ticker=str(row["ticker"]),
        request_hash=str(row["request_hash"]),
        created_at_utc=str(row["created_at_utc"]),
        payload=rows,
        payload_sha256=str(row["payload_sha256"]),
        age_seconds=age,
        is_fresh=age <= float(ttl_seconds),
    )


def read_provider_flow_cache(
    *,
    provider: str,
    lane: str,
    ticker: str,
    params: Mapping[str, Any] | None,
    ttl_seconds: int | float,
    path: str | Path | None = None,
    allow_stale: bool = False,
    now: datetime | None = None,
) -> ProviderFlowCacheRecord | None:
    db_path = cache_path(path)
    if not db_path.exists() or db_path.stat().st_size <= 0:
        return None
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    normalized = (
        _normalize_provider(provider),
        _normalize_lane(lane),
        _normalize_ticker(ticker),
        request_hash(params),
    )
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT provider, lane, ticker, request_hash, created_at_utc, payload_json, payload_sha256
                FROM provider_flow_cache
                WHERE provider = ?
                  AND lane = ?
                  AND ticker = ?
                  AND request_hash = ?
                LIMIT 1
                """,
                normalized,
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    record = _record_from_row(row, ttl_seconds=ttl_seconds, now=current)
    if record is None:
        return None
    if record.is_fresh or allow_stale:
        return record
    return None


def provider_flow_cache_status(path: str | Path | None = None) -> dict[str, Any]:
    db_path = cache_path(path)
    status: dict[str, Any] = {
        "path": str(db_path),
        "exists": db_path.exists(),
        "bytes": db_path.stat().st_size if db_path.exists() else 0,
        "rows": None,
        "latest_created_at_utc": "",
        "state": "missing",
    }
    if not db_path.exists() or db_path.stat().st_size <= 0:
        return status
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*), MAX(created_at_utc) FROM provider_flow_cache"
            ).fetchone()
    except sqlite3.Error:
        status["state"] = "unreadable"
        return status
    rows = int(row[0] or 0) if row else 0
    status["rows"] = rows
    status["latest_created_at_utc"] = str(row[1] or "") if row else ""
    status["state"] = "ready" if rows > 0 else "empty"
    return status


def ttl_seconds(minutes: int | float) -> int:
    return int(timedelta(minutes=float(minutes)).total_seconds())
