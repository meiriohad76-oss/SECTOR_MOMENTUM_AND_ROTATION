from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_pi_deploy_workflow_uses_ssh_secrets_and_branch_trigger():
    workflow = ROOT / ".github" / "workflows" / "deploy-pi.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "branches: [main]" in text
    assert "workflow_dispatch:" in text
    assert "PI_HOST: ${{ secrets.PI_HOST }}" in text
    assert "PI_USER: ${{ secrets.PI_USER }}" in text
    assert "PI_SSH_KEY: ${{ secrets.PI_SSH_KEY }}" in text
    assert "PI_KNOWN_HOSTS: ${{ secrets.PI_KNOWN_HOSTS }}" in text
    assert "PI_REPO_PATH: ${{ secrets.PI_REPO_PATH }}" in text
    assert "runs-on: [self-hosted, sector-pi]" in text
    assert "timeout-minutes: 25" in text
    assert "ubuntu-latest" not in text


def test_pi_deploy_workflow_fast_forwards_tests_and_smokes_service():
    workflow = ROOT / ".github" / "workflows" / "deploy-pi.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "git pull --ff-only origin main" in text
    assert "./.venv/bin/python -m pip install -r requirements.txt" in text
    assert "./.venv/bin/python -m playwright install chromium" in text
    assert "./.venv/bin/python -m pytest -q" in text
    assert "./.venv/bin/python scripts/enforce_safe_config.py --secrets-path \"$PI_REPO_PATH/.streamlit/secrets.toml\"" in text
    assert "./.venv/bin/python scripts/install_user_timers.py --repo-root \"$PI_REPO_PATH\"" in text
    assert "./.venv/bin/python scripts/smoke_provider_flow_lanes.py --ticker SPY --limit 25 --timeout 20 --require-massive" in text
    assert "./.venv/bin/python scripts/warm_provider_flow_cache.py --universe us-sectors --timeout 20" in text
    assert "./.venv/bin/python scripts/refresh_dashboard_state.py --period 3y --provider-flow-mode cache-only" in text
    assert "./.venv/bin/python scripts/check_ops_readiness.py --strict-production" in text
    assert "./.venv/bin/python scripts/check_ops_readiness.py --strict-production --require-rendered-smoke" in text
    assert "./.venv/bin/python scripts/restart_sector_dashboard.py" in text
    assert "./.venv/bin/python scripts/rendered_dashboard_smoke.py" in text
    assert "--timeout-ms 120000" in text
    assert "--output-json \"$PI_REPO_PATH/data/rendered_dashboard_smoke/latest.json\"" in text
    assert "systemctl --user reset-failed sector-rendered-dashboard-smoke.service || true" in text
    assert "systemctl --user start sector-rendered-dashboard-smoke.service" in text
    assert "./.venv/bin/python scripts/smoke_deploy_gate.py" in text
    assert "--service \"$PI_SERVICE_NAME\"" in text
    assert "http://127.0.0.1:8501/?ticker=XLK" in text
    assert "https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK" in text
    assert "--state-file \"$PI_REPO_PATH/data/state.json\"" in text
    assert "--min-state-tickers 80" in text
    assert "--max-state-age-seconds 300" in text
    assert "--expect-cloudflare-access" in text
    assert "restart_result=healthy" in text


def test_runtime_requirements_include_rendered_smoke_browser_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "playwright>=1.52" in requirements


def test_github_actions_pi_deploy_docs_reference_required_secrets():
    text = (ROOT / "docs" / "DEPLOY_GITHUB_ACTIONS_PI.md").read_text(encoding="utf-8")

    for secret in ("PI_HOST", "PI_USER", "PI_SSH_KEY", "PI_KNOWN_HOSTS", "PI_REPO_PATH", "PI_SERVICE_NAME"):
        assert secret in text
    assert "branches: [main]" in text or "main" in text
    assert "self-hosted" in text
    assert "sector-pi" in text
    assert "scripts/enforce_safe_config.py --secrets-path \"$PI_REPO_PATH/.streamlit/secrets.toml\"" in text
    assert "scripts/install_user_timers.py --repo-root \"$PI_REPO_PATH\"" in text
    assert "python -m playwright install chromium" in text
    assert "scripts/smoke_provider_flow_lanes.py --ticker SPY --limit 25 --timeout 20 --require-massive" in text
    assert "scripts/warm_provider_flow_cache.py --universe us-sectors --timeout 20" in text
    assert "scripts/refresh_dashboard_state.py --period 3y --provider-flow-mode cache-only" in text
    assert "scripts/check_ops_readiness.py --strict-production" in text
    assert "scripts/check_ops_readiness.py --strict-production --require-rendered-smoke" in text
    assert "scripts/rendered_dashboard_smoke.py --url" in text
    assert "systemctl --user start sector-rendered-dashboard-smoke.service" in text
    assert "data/rendered_dashboard_smoke/latest.json" in text


def test_backlog_records_live_validated_pi_deploy_status():
    text = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    start = text.index("#### B-140")
    section = text[start:text.index("#### B-141", start)]

    assert "IMPLEMENTED / LIVE VALIDATED" in section
    assert "GitHub Actions run `26285814872` completed successfully" in section
    assert "SECRETS CONFIG PENDING" not in section
