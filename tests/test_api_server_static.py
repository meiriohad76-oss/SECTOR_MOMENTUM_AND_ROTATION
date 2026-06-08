from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_api_server_is_optional_fastapi_boundary_not_streamlit_import():
    source = (ROOT / "src" / "api_server.py").read_text(encoding="utf-8")

    assert "def create_app(" in source
    assert "from fastapi import BackgroundTasks, Body" in source
    assert "from fastapi import FastAPI, HTTPException" in source
    assert "except ModuleNotFoundError" in source
    assert "payload: dict[str, Any] | None = Body(default=None)" in source
    assert "HTTPException" in source
    assert "from .api_refresh import create_refresh_job, get_refresh_job, list_refresh_events, queued_refresh_response" in source
    assert "from .api_refresh_runner import run_refresh_job" in source
    assert "from .api_status import build_persisted_status_payload" in source
    assert "return build_persisted_status_payload()" in source
    assert 'app.get("/api/v1/health")' in source
    assert 'app.get("/api/v1/status")' in source
    assert 'app.post("/api/v1/refresh", status_code=202)' in source
    assert 'app.get("/api/v1/refresh/{job_id}")' in source
    assert 'app.get("/api/v1/refresh/{job_id}/events")' in source
    assert "background_tasks.add_task(runner" in source
    assert "job = runner(job[\"job_id\"]" in source
    assert 'raise HTTPException(status_code=404, detail="Refresh job not found")' in source
    assert "import streamlit" not in source
    assert "fetch_ohlcv_result" not in source
    assert "FastAPI is not installed" in source


def test_api_contract_is_pure_and_documents_migration_stage():
    source = (ROOT / "src" / "api_contract.py").read_text(encoding="utf-8")

    assert "def build_dashboard_status_payload(" in source
    assert "def normalize_health_lane(" in source
    assert '"streamlit_compat_api_foundation"' in source
    assert "import streamlit" not in source
    assert "fetch_ohlcv_result" not in source


def test_api_dependencies_are_declared_for_future_service():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "fastapi>=0.115" in requirements
    assert "uvicorn[standard]>=0.30" in requirements
    assert "httpx>=0.27" in requirements
