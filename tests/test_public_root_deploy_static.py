from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_cloudflare_docs_separate_public_root_from_dashboard():
    docs = (ROOT / "docs" / "DEPLOY_CLOUDFLARE_TUNNEL.md").read_text(encoding="utf-8")
    config = (ROOT / "config" / "cloudflared-config.yml.example").read_text(encoding="utf-8")

    assert "Public methodology landing page" in docs
    assert "ahaddashboards.uk" in docs
    assert "www.ahaddashboards.uk" in docs
    assert "dashboard.ahaddashboards.uk" in docs
    assert "http://localhost:8500" in docs
    assert "http://localhost:8501" in docs
    assert "public/" in docs
    assert "Cloudflare Access" in docs
    assert docs.index("http://localhost:8500") < docs.index("http://localhost:8501")

    assert "hostname: ahaddashboards.uk" in config
    assert "hostname: www.ahaddashboards.uk" in config
    assert "service: http://localhost:8500" in config
    assert "hostname: dashboard.ahaddashboards.uk" in config
    assert "service: http://localhost:8501" in config


def test_static_landing_service_template_serves_public_directory():
    service = (ROOT / "systemd" / "methodology-landing.service").read_text(encoding="utf-8")
    user_service = (ROOT / "systemd" / "user" / "methodology-landing.service").read_text(encoding="utf-8")

    assert "Description=Public Methodology Landing Page" in service
    assert "WorkingDirectory=/home/meiri/sector-rotation-dashboard" in service
    assert "python3 -m http.server 8500" in service
    assert "--directory public" in service
    assert "127.0.0.1" in service
    assert "WorkingDirectory=%h/SECTOR_MOMENTUM_AND_ROTATION" in user_service
    assert "python3 -m http.server 8500" in user_service
    assert "--directory public" in user_service
    assert "User=" not in user_service


def test_readme_and_backlog_document_public_landing():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "public/index.html" in readme
    assert "docs/PUBLIC_METHODOLOGY_LANDING.md" in readme
    assert "B-152" in backlog
    assert "public/index.html" in backlog
    assert "public/methodology.html" in backlog
    assert "IMPLEMENTED" in backlog
