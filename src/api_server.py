"""Optional FastAPI app factory for the dashboard migration path.

The live dashboard still runs through Streamlit. This module is deliberately
small so the backend API can be exercised independently before a React client
replaces the Streamlit presentation layer.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .api_contract import build_dashboard_status_payload


StatusProvider = Callable[[], dict[str, Any]]


def default_status_provider() -> dict[str, Any]:
    """Return a minimal process-health payload when no dashboard snapshot is wired."""
    return build_dashboard_status_payload(
        [],
        app_version="unknown",
        git_sha=None,
        generated_at=datetime.now(timezone.utc),
        active_frontend="api",
    )


def create_app(status_provider: StatusProvider | None = None):
    """Create the optional FastAPI app without making FastAPI mandatory at import time."""
    try:
        from fastapi import FastAPI
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised when dependency is absent.
        raise RuntimeError("FastAPI is not installed. Install requirements.txt to run the API server.") from exc

    provider = status_provider or default_status_provider
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

    return app


try:
    app = create_app()
except RuntimeError:
    app = None
