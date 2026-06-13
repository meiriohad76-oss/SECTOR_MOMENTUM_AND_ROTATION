from __future__ import annotations

import importlib
import json
import subprocess
import sys


def _script_module():
    return importlib.import_module("scripts.check_pi_deploy_config")


def test_pi_deploy_config_script_reports_missing_required_fields(monkeypatch, capsys):
    check_pi_deploy_config = _script_module()
    monkeypatch.setattr(check_pi_deploy_config.os, "environ", {})

    exit_code = check_pi_deploy_config.main([])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["pi_deploy_config"] == "missing"
    assert payload["missing"] == ["PI_HOST", "PI_USER", "PI_SSH_KEY", "PI_KNOWN_HOSTS", "PI_REPO_PATH"]
    assert payload["optional_missing"] == ["PI_SERVICE_NAME"]


def test_pi_deploy_config_script_reports_ready_without_secret_material(monkeypatch, capsys):
    check_pi_deploy_config = _script_module()
    monkeypatch.setattr(
        check_pi_deploy_config.os,
        "environ",
        {
            "PI_HOST": "ssh.example.test",
            "PI_USER": "ahad",
            "PI_SSH_KEY": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----",
            "PI_KNOWN_HOSTS": "ssh.example.test ssh-ed25519 AAAATEST",
            "PI_REPO_PATH": "/home/ahad/SECTOR_MOMENTUM_AND_ROTATION",
            "PI_SERVICE_NAME": "sector-dashboard",
        },
    )

    exit_code = check_pi_deploy_config.main([])

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 0
    assert payload["pi_deploy_config"] == "ready"
    assert payload["missing"] == []
    assert payload["configured"] == [
        "PI_HOST",
        "PI_USER",
        "PI_SSH_KEY",
        "PI_KNOWN_HOSTS",
        "PI_REPO_PATH",
        "PI_SERVICE_NAME",
    ]
    assert "secret" not in output
    assert "PRIVATE KEY" not in output


def test_pi_deploy_config_docs_reference_preflight_checker():
    check_pi_deploy_config = _script_module()
    root = check_pi_deploy_config.ROOT
    docs = (root / "docs" / "DEPLOY_GITHUB_ACTIONS_PI.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "scripts/check_pi_deploy_config.py" in docs
    assert "scripts/check_pi_deploy_config.py" in backlog
    assert "PI_SSH_KEY" in docs
    assert "private key" in docs.lower()


def test_pi_deploy_config_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/check_pi_deploy_config.py"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["pi_deploy_config"] in {"missing", "ready"}
