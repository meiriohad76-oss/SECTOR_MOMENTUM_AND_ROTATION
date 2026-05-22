from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_pi_deploy_workflow_uses_ssh_secrets_and_branch_trigger():
    workflow = ROOT / ".github" / "workflows" / "deploy-pi.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "branches: [backlog-stepwise-qa]" in text
    assert "workflow_dispatch:" in text
    assert "PI_HOST: ${{ secrets.PI_HOST }}" in text
    assert "PI_USER: ${{ secrets.PI_USER }}" in text
    assert "PI_SSH_KEY: ${{ secrets.PI_SSH_KEY }}" in text
    assert "PI_KNOWN_HOSTS: ${{ secrets.PI_KNOWN_HOSTS }}" in text
    assert "PI_REPO_PATH: ${{ secrets.PI_REPO_PATH }}" in text
    assert "runs-on: [self-hosted, sector-pi]" in text
    assert "ubuntu-latest" not in text


def test_pi_deploy_workflow_fast_forwards_tests_and_smokes_service():
    workflow = ROOT / ".github" / "workflows" / "deploy-pi.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "git pull --ff-only origin backlog-stepwise-qa" in text
    assert "./.venv/bin/python -m pip install -r requirements.txt" in text
    assert "./.venv/bin/python -m pytest -q" in text
    assert "systemctl show \"$PI_SERVICE_NAME\" -p MainPID --value" in text
    assert "http://127.0.0.1:8501/?ticker=XLK" in text
    assert "active=$active http=$code" in text


def test_github_actions_pi_deploy_docs_reference_required_secrets():
    text = (ROOT / "docs" / "DEPLOY_GITHUB_ACTIONS_PI.md").read_text(encoding="utf-8")

    for secret in ("PI_HOST", "PI_USER", "PI_SSH_KEY", "PI_KNOWN_HOSTS", "PI_REPO_PATH", "PI_SERVICE_NAME"):
        assert secret in text
    assert "backlog-stepwise-qa" in text
    assert "self-hosted" in text
    assert "sector-pi" in text


def test_backlog_records_live_validated_pi_deploy_status():
    text = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    start = text.index("#### B-140")
    section = text[start:text.index("#### B-141", start)]

    assert "IMPLEMENTED / LIVE VALIDATED" in section
    assert "GitHub Actions run `26285814872` completed successfully" in section
    assert "SECRETS CONFIG PENDING" not in section
