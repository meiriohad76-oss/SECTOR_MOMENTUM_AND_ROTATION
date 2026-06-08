"""Persisted refresh job queue for the optional dashboard API."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFRESH_JOB_DB_PATH = ROOT / "data" / "api_refresh" / "refresh_jobs.sqlite"
REFRESH_LANES = (
    "all",
    "market_ohlcv",
    "fred_macro",
    "provider_flow",
    "dashboard_compute",
    "state_persistence",
)
REFRESH_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(payload: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(payload or {}), sort_keys=True, separators=(",", ":"))


def _from_json(payload: str | None) -> dict[str, Any]:
    if not payload:
        return {}
    return json.loads(payload)


def normalize_refresh_lane(lane_id: Any) -> str:
    lane = str(lane_id or "all").strip().lower()
    return lane if lane in REFRESH_LANES else "all"


def normalize_refresh_status(status: Any) -> str:
    value = str(status or "running").strip().lower()
    return value if value in REFRESH_STATUSES else "running"


def _progress(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return max(0, min(100, parsed))


def initialize_refresh_store(db_path: str | Path = DEFAULT_REFRESH_JOB_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_jobs (
                job_id TEXT PRIMARY KEY,
                lane_id TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_at_utc TEXT NOT NULL,
                started_at_utc TEXT,
                completed_at_utc TEXT,
                progress_pct INTEGER NOT NULL,
                message TEXT NOT NULL,
                error TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                status TEXT NOT NULL,
                phase TEXT NOT NULL,
                progress_pct INTEGER NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES refresh_jobs(job_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refresh_events_job
                ON refresh_events(job_id, id ASC)
            """
        )


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["metadata"] = _from_json(data.pop("metadata_json", "{}"))
    return data


def _event_row_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["metadata"] = _from_json(data.pop("metadata_json", "{}"))
    return data


def create_refresh_job(
    *,
    lane_id: Any = "all",
    db_path: str | Path = DEFAULT_REFRESH_JOB_DB_PATH,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    initialize_refresh_store(db_path)
    job_id = uuid4().hex
    lane = normalize_refresh_lane(lane_id)
    now = _utc_now()
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO refresh_jobs (
                job_id,
                lane_id,
                status,
                requested_at_utc,
                started_at_utc,
                completed_at_utc,
                progress_pct,
                message,
                error,
                metadata_json
            )
            VALUES (?, ?, 'queued', ?, NULL, NULL, 0, ?, '', ?)
            """,
            (
                job_id,
                lane,
                now,
                f"Refresh queued for lane {lane}",
                _json(metadata),
            ),
        )
        conn.execute(
            """
            INSERT INTO refresh_events (
                job_id,
                created_at_utc,
                status,
                phase,
                progress_pct,
                message,
                metadata_json
            )
            VALUES (?, ?, 'queued', 'queued', 0, ?, ?)
            """,
            (
                job_id,
                now,
                f"Refresh queued for lane {lane}",
                _json(metadata),
            ),
        )
    job = get_refresh_job(job_id, db_path=db_path)
    if job is None:
        raise RuntimeError("refresh job was not persisted")
    return job


def append_refresh_event(
    job_id: str,
    *,
    status: Any = "running",
    phase: str = "running",
    progress_pct: Any = 0,
    message: str = "",
    error: str = "",
    metadata: Mapping[str, Any] | None = None,
    db_path: str | Path = DEFAULT_REFRESH_JOB_DB_PATH,
) -> dict[str, Any]:
    initialize_refresh_store(db_path)
    normalized_status = normalize_refresh_status(status)
    progress = _progress(progress_pct)
    now = _utc_now()
    completed_at = now if normalized_status in TERMINAL_STATUSES else None
    started_expr = "COALESCE(started_at_utc, ?)" if normalized_status in {"running", "succeeded", "failed"} else "started_at_utc"
    job_metadata_json = _json(metadata) if metadata is not None else None
    params: tuple[Any, ...]
    if started_expr.startswith("COALESCE"):
        params = (
            normalized_status,
            now,
            completed_at,
            progress,
            str(message),
            str(error),
            job_metadata_json,
            str(job_id),
        )
    else:
        params = (
            normalized_status,
            completed_at,
            progress,
            str(message),
            str(error),
            job_metadata_json,
            str(job_id),
        )
    with sqlite3.connect(Path(db_path)) as conn:
        exists = conn.execute("SELECT 1 FROM refresh_jobs WHERE job_id = ?", (str(job_id),)).fetchone()
        if exists is None:
            raise KeyError(f"Refresh job not found: {job_id}")
        conn.execute(
            f"""
            UPDATE refresh_jobs
            SET status = ?,
                started_at_utc = {started_expr},
                completed_at_utc = ?,
                progress_pct = ?,
                message = ?,
                error = ?,
                metadata_json = COALESCE(?, metadata_json)
            WHERE job_id = ?
            """,
            params,
        )
        conn.execute(
            """
            INSERT INTO refresh_events (
                job_id,
                created_at_utc,
                status,
                phase,
                progress_pct,
                message,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job_id),
                now,
                normalized_status,
                str(phase),
                progress,
                str(message),
                _json(metadata),
            ),
        )
    job = get_refresh_job(job_id, db_path=db_path)
    if job is None:
        raise RuntimeError("refresh job disappeared")
    return job


def get_refresh_job(job_id: str, *, db_path: str | Path = DEFAULT_REFRESH_JOB_DB_PATH) -> dict[str, Any] | None:
    path = Path(db_path)
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                job_id,
                lane_id,
                status,
                requested_at_utc,
                started_at_utc,
                completed_at_utc,
                progress_pct,
                message,
                error,
                metadata_json
            FROM refresh_jobs
            WHERE job_id = ?
            """,
            (str(job_id),),
        ).fetchone()
    return _row_dict(row) if row is not None else None


def list_refresh_events(job_id: str, *, db_path: str | Path = DEFAULT_REFRESH_JOB_DB_PATH) -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, job_id, created_at_utc, status, phase, progress_pct, message, metadata_json
            FROM refresh_events
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (str(job_id),),
        ).fetchall()
    return [_event_row_dict(row) for row in rows]


def queued_refresh_response(job: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "job_id": str(job.get("job_id", "")),
        "lane_id": str(job.get("lane_id", "")),
        "status": str(job.get("status", "queued")),
        "progress_pct": int(job.get("progress_pct", 0) or 0),
        "message": str(job.get("message", "")),
        "status_url": f"/api/v1/refresh/{job.get('job_id', '')}",
        "events_url": f"/api/v1/refresh/{job.get('job_id', '')}/events",
    }
