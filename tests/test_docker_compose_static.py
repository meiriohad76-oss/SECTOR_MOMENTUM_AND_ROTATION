from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_runs_streamlit_on_container_port():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in text
    assert "pip install --no-cache-dir -r requirements.txt" in text
    assert "EXPOSE 8501" in text
    assert "streamlit" in text
    assert "--server.address=0.0.0.0" in text
    assert "--server.port=8501" in text


def test_docker_compose_maps_port_and_persists_local_state():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "sector-dashboard:" in text
    assert "build: ." in text
    assert '"8501:8501"' in text
    assert "OHLCV_PROVIDER: ${OHLCV_PROVIDER:-yfinance}" in text
    assert "STATE_FILE: ${STATE_FILE:-/app/data/state.json}" in text
    assert "./.streamlit:/app/.streamlit:ro" in text
    assert "./data:/app/data" in text
    assert "./state.json:/app/state.json" not in text
    assert "curl -f http://127.0.0.1:8501/?ticker=XLK" in text


def test_dockerignore_excludes_local_secrets_and_generated_data():
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".streamlit/secrets.toml" in text
    assert ".env" in text
    assert ".env.*" in text
    assert "*.pem" in text
    assert "*.key" in text
    assert "*.crt" in text
    assert "*.ppk" in text
    assert "*.p12" in text
    assert "*.pfx" in text
    assert ".ssh/" in text
    assert "id_rsa" in text
    assert "id_ed25519" in text
    assert "*_rsa" in text
    assert "*_ed25519" in text
    assert ".venv/" in text
    assert "data/state.json" in text
    assert "data/run_journal/" in text
    assert "data/feeds/" in text
    assert "state.json" in text
