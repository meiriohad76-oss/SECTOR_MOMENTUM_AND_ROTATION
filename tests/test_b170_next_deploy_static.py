from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_b170_api_systemd_unit_is_localhost_candidate_service():
    unit = (ROOT / "systemd" / "sector-api.service").read_text(encoding="utf-8")

    assert "Description=Sector Rotation Dashboard API (FastAPI candidate)" in unit
    assert "User=ahad" in unit
    assert "Group=ahad" in unit
    assert "WorkingDirectory=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION" in unit
    assert "Environment=STATE_FILE=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION/data/state.json" in unit
    assert (
        "Environment=STATE_TRANSITION_JOURNAL=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION/data/state_transitions.jsonl"
        in unit
    )
    assert ".venv/bin/python -m uvicorn src.api_server:create_app --factory" in unit
    assert "--host 127.0.0.1 --port 8000" in unit
    assert "WantedBy=multi-user.target" in unit


def test_b170_next_systemd_unit_is_api_backed_candidate_frontend():
    unit = (ROOT / "systemd" / "sector-next.service").read_text(encoding="utf-8")

    assert "Description=Sector Rotation Dashboard Next.js Frontend (candidate)" in unit
    assert "After=network-online.target sector-api.service" in unit
    assert "WorkingDirectory=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION/web" in unit
    assert "Environment=NODE_ENV=production" in unit
    assert "Environment=API_BASE_URL=http://127.0.0.1:8000" in unit
    assert "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000" not in unit
    assert "ExecStart=/usr/bin/npm run start" in unit
    assert "8501" not in unit


def test_b170_pi_deploy_docs_cover_candidate_install_and_smoke_without_streamlit_retirement():
    docs = (ROOT / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")

    for marker in (
        "Optional B-170 API and Next.js candidate services",
        "sector-api.service",
        "sector-next.service",
        "npm --prefix web ci",
        "npm --prefix web run build",
        "curl -s -f http://127.0.0.1:8000/api/v1/health",
        "curl -s -f http://127.0.0.1:3000/?presentation=c",
        "Do not stop or reroute",
        "sector-dashboard until the parity gates below pass.",
        "feature parity",
        "data parity",
        "visual parity",
        "rollback",
    ):
        assert marker in docs


def test_b170_cloudflare_docs_keep_streamlit_live_and_define_candidate_route_plan():
    docs = (ROOT / "docs" / "DEPLOY_CLOUDFLARE_TUNNEL.md").read_text(encoding="utf-8")

    for marker in (
        "B-170 candidate Next.js route plan",
        "next-sentimentdashboard.ahaddashboards.uk",
        "service: http://localhost:3000",
        "Keep `sentimentdashboard.ahaddashboards.uk` routed to `http://localhost:8501`",
        "Do not expose the FastAPI service directly unless you add a separate Access",
        "policy, CORS policy, rate limits, and explicit API threat model.",
        "rollback path",
    ):
        assert marker in docs


def test_b170_plan_marks_deploy_docs_slice_done_but_streamlit_retirement_open():
    plan = (ROOT / "docs" / "superpowers" / "plans" / "2026-06-08-b170-production-dashboard-migration.md").read_text(
        encoding="utf-8"
    )
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "- [x] Add Pi systemd/API deployment docs and Cloudflare route plan." in plan
    assert "- [ ] Retire the Streamlit route only after feature parity, data parity, visual parity, and rollback path are documented." in plan
    assert "candidate `sector-api.service` and `sector-next.service` templates" in backlog
    assert "Streamlit route remains production" in backlog
