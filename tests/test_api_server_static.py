from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_api_server_is_optional_fastapi_boundary_not_streamlit_import():
    source = (ROOT / "src" / "api_server.py").read_text(encoding="utf-8")

    assert "def create_app(" in source
    assert "from fastapi import FastAPI" in source
    assert "from .api_status import build_persisted_status_payload" in source
    assert "return build_persisted_status_payload()" in source
    assert 'app.get("/api/v1/health")' in source
    assert 'app.get("/api/v1/status")' in source
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
