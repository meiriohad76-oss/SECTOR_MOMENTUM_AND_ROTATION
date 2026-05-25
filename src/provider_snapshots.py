"""Historical provider snapshot store and as-of replay helpers.

This module is deliberately offline/pure storage. It does not fetch provider
data and it does not wire snapshots into live scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DB_PATH = ROOT / "data" / "provider_snapshots" / "provider_snapshots.sqlite"


@dataclass(frozen=True)
class ProviderSnapshotRecord:
    provider: str
    dataset: str
    ticker: str
    as_of: str
    captured_at_utc: str
    payload: dict[str, Any]
    payload_sha256: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()


def _normalize_provider(value: str) -> str:
    return str(value).strip().lower()


def _normalize_dataset(value: str) -> str:
    return str(value).strip().lower()


def _normalize_ticker(value: str) -> str:
    return str(value).strip().upper()


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _to_payload_dict(payload: Mapping[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    if isinstance(payload, list):
        return {"records": payload}
    raise TypeError("payload must be a mapping or list")


def _payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), default=_json_default, sort_keys=True, separators=(",", ":"))


def payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_payload_json(payload).encode("utf-8")).hexdigest()


def initialize_snapshot_store(db_path: str | Path = DEFAULT_SNAPSHOT_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_snapshots (
                provider TEXT NOT NULL,
                dataset TEXT NOT NULL,
                ticker TEXT NOT NULL,
                as_of TEXT NOT NULL,
                captured_at_utc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                PRIMARY KEY (provider, dataset, ticker, as_of)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_provider_snapshots_asof
                ON provider_snapshots(provider, dataset, ticker, as_of DESC)
            """
        )


def _record_from_row(row: sqlite3.Row) -> ProviderSnapshotRecord:
    payload = json.loads(row["payload_json"])
    return ProviderSnapshotRecord(
        provider=row["provider"],
        dataset=row["dataset"],
        ticker=row["ticker"],
        as_of=row["as_of"],
        captured_at_utc=row["captured_at_utc"],
        payload=payload,
        payload_sha256=row["payload_sha256"],
    )


def upsert_provider_snapshot(
    db_path: str | Path,
    *,
    provider: str,
    dataset: str,
    ticker: str,
    as_of: str | date | datetime,
    payload: Mapping[str, Any] | list[Any],
    captured_at_utc: str | None = None,
) -> ProviderSnapshotRecord:
    initialize_snapshot_store(db_path)
    payload_dict = _to_payload_dict(payload)
    payload_json = _payload_json(payload_dict)
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    record = ProviderSnapshotRecord(
        provider=_normalize_provider(provider),
        dataset=_normalize_dataset(dataset),
        ticker=_normalize_ticker(ticker),
        as_of=_normalize_date(as_of),
        captured_at_utc=str(captured_at_utc or _utc_now()),
        payload=payload_dict,
        payload_sha256=digest,
    )
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO provider_snapshots (
                provider,
                dataset,
                ticker,
                as_of,
                captured_at_utc,
                payload_json,
                payload_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, dataset, ticker, as_of) DO UPDATE SET
                captured_at_utc = excluded.captured_at_utc,
                payload_json = excluded.payload_json,
                payload_sha256 = excluded.payload_sha256
            """,
            (
                record.provider,
                record.dataset,
                record.ticker,
                record.as_of,
                record.captured_at_utc,
                payload_json,
                digest,
            ),
        )
    return record


def load_provider_snapshot_as_of(
    db_path: str | Path,
    *,
    provider: str,
    dataset: str,
    ticker: str,
    as_of: str | date | datetime,
) -> ProviderSnapshotRecord | None:
    path = Path(db_path)
    if not path.exists():
        return None
    target = _normalize_date(as_of)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT provider, dataset, ticker, as_of, captured_at_utc, payload_json, payload_sha256
            FROM provider_snapshots
            WHERE provider = ?
              AND dataset = ?
              AND ticker = ?
              AND as_of <= ?
            ORDER BY as_of DESC, captured_at_utc DESC
            LIMIT 1
            """,
            (
                _normalize_provider(provider),
                _normalize_dataset(dataset),
                _normalize_ticker(ticker),
                target,
            ),
        ).fetchone()
    return _record_from_row(row) if row is not None else None


def list_provider_snapshots(
    db_path: str | Path,
    *,
    provider: str,
    dataset: str,
    ticker: str,
) -> list[ProviderSnapshotRecord]:
    path = Path(db_path)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT provider, dataset, ticker, as_of, captured_at_utc, payload_json, payload_sha256
            FROM provider_snapshots
            WHERE provider = ?
              AND dataset = ?
              AND ticker = ?
            ORDER BY as_of ASC
            """,
            (
                _normalize_provider(provider),
                _normalize_dataset(dataset),
                _normalize_ticker(ticker),
            ),
        ).fetchall()
    return [_record_from_row(row) for row in rows]


def _trades_from_payload(payload: Mapping[str, Any]) -> list[dict]:
    rows = payload.get("trades", payload.get("results", payload.get("records", [])))
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def block_trade_upside_ratio_from_snapshot(snapshot: ProviderSnapshotRecord) -> float | None:
    from .flow import block_trade_upside_ratio_from_massive_trades

    return block_trade_upside_ratio_from_massive_trades(_trades_from_payload(snapshot.payload))


def block_trade_upside_ratio_as_of(
    db_path: str | Path,
    *,
    ticker: str,
    as_of: str | date | datetime,
) -> float | None:
    snapshot = load_provider_snapshot_as_of(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker=ticker,
        as_of=as_of,
    )
    if snapshot is None:
        return None
    return block_trade_upside_ratio_from_snapshot(snapshot)
