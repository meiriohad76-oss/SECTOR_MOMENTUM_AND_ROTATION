"""Optional FastAPI app factory for the dashboard migration path.

The live dashboard still runs through Streamlit. This module is deliberately
small so the backend API can be exercised independently before a React client
replaces the Streamlit presentation layer.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .api_refresh import create_refresh_job, get_refresh_job, list_refresh_events, queued_refresh_response
from .api_refresh_runner import run_refresh_job
from .api_status import build_persisted_status_payload

try:
    from fastapi import BackgroundTasks, Body
except ModuleNotFoundError:  # pragma: no cover - create_app reports the missing runtime dependency.
    BackgroundTasks = Any  # type: ignore[misc, assignment]

    def Body(default: Any = None) -> Any:  # type: ignore[no-redef]
        return default


StatusProvider = Callable[[], dict[str, Any]]
RefreshRunner = Callable[..., dict[str, Any]]


def default_status_provider() -> dict[str, Any]:
    """Return read-only persisted dashboard health without recomputing providers."""
    return build_persisted_status_payload()


def create_app(status_provider: StatusProvider | None = None, refresh_runner: RefreshRunner | None = None):
    """Create the optional FastAPI app without making FastAPI mandatory at import time."""
    try:
        from fastapi import FastAPI, HTTPException
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised when dependency is absent.
        raise RuntimeError("FastAPI is not installed. Install requirements.txt to run the API server.") from exc

    provider = status_provider or default_status_provider
    runner = refresh_runner or run_refresh_job
    app = FastAPI(
        title="Sector Momentum Dashboard API",
        version="0.1.0",
        description="Migration API for the Sector Momentum and Rotation dashboard.",
    )

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return provider()

    @app.get("/api/v1/status")
    def status() -> dict[str, Any]:
        return provider()

    @app.post("/api/v1/refresh", status_code=202)
    def create_refresh(
        background_tasks: BackgroundTasks,
        payload: dict[str, Any] | None = Body(default=None),
    ) -> dict[str, Any]:
        body = payload or {}
        lane_id = body.get("lane_id", "all")
        job = create_refresh_job(
            lane_id=lane_id,
            metadata={
                "source": "api",
                "requested_by": body.get("requested_by", "anonymous"),
                "run_now": bool(body.get("run_now", False)),
            },
        )
        if body.get("run_now"):
            runner_kwargs = {
                "lane_id": lane_id,
                "period": body.get("period", "3y"),
                "force_refresh": bool(body.get("force_refresh", True)),
                "provider_flow_mode": body.get("provider_flow_mode", "cache-only"),
                "allow_stale_provider_cache": bool(body.get("allow_stale_provider_cache", True)),
            }
            if body.get("background", True):
                background_tasks.add_task(runner, job["job_id"], **runner_kwargs)
            else:
                job = runner(job["job_id"], **runner_kwargs)
        return queued_refresh_response(job)

    @app.get("/api/v1/refresh/{job_id}")
    def refresh_job(job_id: str) -> dict[str, Any]:
        job = get_refresh_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Refresh job not found")
        return job

    @app.get("/api/v1/refresh/{job_id}/events")
    def refresh_events(job_id: str) -> dict[str, Any]:
        job = get_refresh_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Refresh job not found")
        return {"job_id": job_id, "events": list_refresh_events(job_id)}

    return app


try:
    app = create_app()
except RuntimeError:
    app = None
