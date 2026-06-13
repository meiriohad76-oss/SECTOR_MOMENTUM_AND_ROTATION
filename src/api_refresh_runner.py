"""Run persisted API refresh jobs through the real dashboard refresh path."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .api_refresh import DEFAULT_REFRESH_JOB_DB_PATH, append_refresh_event, get_refresh_job
from .run_journal import DEFAULT_JOURNAL_PATH


DEFAULT_REFRESH_PERIOD = "3y"
DEFAULT_PROVIDER_FLOW_MODE = "cache-only"


def _clean_metadata(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return {str(key): value for key, value in dict(payload or {}).items() if value is not None}


def _result_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _clean_metadata(
        {
            "ok": bool(payload.get("ok")),
            "provider": payload.get("provider"),
            "period": payload.get("period"),
            "ticker_count": payload.get("ticker_count"),
            "state_counts": payload.get("state_counts"),
            "bluf_counts": payload.get("bluf_counts"),
            "regime": payload.get("regime"),
            "journal": payload.get("journal"),
        }
    )


def run_refresh_job(
    job_id: str,
    *,
    lane_id: str | None = None,
    db_path: str | Path = DEFAULT_REFRESH_JOB_DB_PATH,
    period: str = DEFAULT_REFRESH_PERIOD,
    force_refresh: bool = True,
    provider_flow_mode: str = DEFAULT_PROVIDER_FLOW_MODE,
    allow_stale_provider_cache: bool = True,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    dedupe_journal: bool = True,
) -> dict[str, Any]:
    """Execute a queued refresh job and persist progress events.

    The actual provider fetch, FRED macro load, indicator computation, state
    machine update, and run-journal append remain owned by the existing
    headless refresh script. This wrapper only adds API-job observability.
    """
    job = get_refresh_job(str(job_id), db_path=db_path)
    if job is None:
        raise KeyError(f"Refresh job not found: {job_id}")

    lane = str(lane_id or job.get("lane_id") or "all")
    append_refresh_event(
        str(job_id),
        status="running",
        phase="starting",
        progress_pct=5,
        message=f"Starting refresh for lane {lane}",
        metadata={
            "lane_id": lane,
            "period": period,
            "force_refresh": bool(force_refresh),
            "provider_flow_mode": provider_flow_mode,
        },
        db_path=db_path,
    )

    def progress_callback(
        phase: str,
        progress_pct: int,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        append_refresh_event(
            str(job_id),
            status="running",
            phase=phase,
            progress_pct=progress_pct,
            message=message,
            metadata=_clean_metadata(metadata),
            db_path=db_path,
        )

    try:
        from scripts import refresh_dashboard_state as dashboard_refresh

        payload = dashboard_refresh.refresh_dashboard_state(
            period=period,
            force_refresh=bool(force_refresh),
            provider_flow_mode=provider_flow_mode,
            allow_stale_provider_cache=bool(allow_stale_provider_cache),
            journal_path=journal_path,
            dedupe_journal=bool(dedupe_journal),
            progress_callback=progress_callback,
        )
        if not payload.get("ok"):
            error = str(payload.get("error") or "refresh_failed")
            return append_refresh_event(
                str(job_id),
                status="failed",
                phase="failed",
                progress_pct=100,
                message="Refresh failed",
                error=error,
                metadata=_result_metadata(payload),
                db_path=db_path,
            )
        return append_refresh_event(
            str(job_id),
            status="succeeded",
            phase="complete",
            progress_pct=100,
            message="Refresh complete",
            metadata=_result_metadata(payload),
            db_path=db_path,
        )
    except Exception as exc:
        return append_refresh_event(
            str(job_id),
            status="failed",
            phase="failed",
            progress_pct=100,
            message="Refresh failed",
            error=type(exc).__name__,
            metadata={"lane_id": lane},
            db_path=db_path,
        )
