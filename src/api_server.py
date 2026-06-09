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
from .api_data_health import build_provider_data_health_payload
from .api_dashboard_snapshot import build_latest_dashboard_snapshot_payload
from .api_portfolio import build_portfolio_analysis_payload
from .api_status import build_persisted_status_payload

try:
    from fastapi import BackgroundTasks, Body
except ModuleNotFoundError:  # pragma: no cover - create_app reports the missing runtime dependency.
    BackgroundTasks = Any  # type: ignore[misc, assignment]

    def Body(default: Any = None) -> Any:  # type: ignore[no-redef]
        return default


StatusProvider = Callable[[], dict[str, Any]]
DataHealthProvider = Callable[[], dict[str, Any]]
SnapshotProvider = Callable[..., dict[str, Any]]
RefreshRunner = Callable[..., dict[str, Any]]


def default_status_provider() -> dict[str, Any]:
    """Return read-only persisted dashboard health without recomputing providers."""
    return build_persisted_status_payload()


def default_data_health_provider() -> dict[str, Any]:
    """Return read-only provider/data health for future API clients."""
    return build_provider_data_health_payload()


def default_snapshot_provider(**kwargs: Any) -> dict[str, Any]:
    """Return the latest persisted dashboard run snapshot."""
    return build_latest_dashboard_snapshot_payload(**kwargs)


def create_app(
    status_provider: StatusProvider | None = None,
    refresh_runner: RefreshRunner | None = None,
    data_health_provider: DataHealthProvider | None = None,
    snapshot_provider: SnapshotProvider | None = None,
):
    """Create the optional FastAPI app without making FastAPI mandatory at import time."""
    try:
        from fastapi import FastAPI, HTTPException
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised when dependency is absent.
        raise RuntimeError("FastAPI is not installed. Install requirements.txt to run the API server.") from exc

    provider = status_provider or default_status_provider
    data_provider = data_health_provider or default_data_health_provider
    snapshot_reader = snapshot_provider or default_snapshot_provider
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

    @app.get("/api/v1/data-health")
    def data_health() -> dict[str, Any]:
        return data_provider()

    @app.get("/api/v1/provider-health")
    def provider_health() -> dict[str, Any]:
        payload = data_provider()
        lanes = [
            lane
            for lane in payload.get("lanes", [])
            if str(lane.get("lane_id", "")).startswith("provider_")
        ]
        return {
            "api_version": payload.get("api_version", "v1"),
            "generated_at": payload.get("generated_at", ""),
            "app": payload.get("app", {}),
            "health": payload.get("health", {}),
            "provider_flow": payload.get("provider_flow", {}),
            "lanes": lanes,
        }

    @app.get("/api/v1/dashboard-snapshot")
    def dashboard_snapshot(ticker: str | None = None) -> dict[str, Any]:
        return snapshot_reader(focus_ticker=ticker)

    @app.post("/api/v1/portfolio/analyze")
    def portfolio_analyze(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        snapshot = snapshot_reader()
        return build_portfolio_analysis_payload(payload or {}, snapshot_payload=snapshot)

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
