from __future__ import annotations

import json
import importlib
import subprocess
import sys


def _script_module():
    return importlib.import_module("scripts.check_broker_config")


def test_broker_config_script_outputs_sanitized_json(monkeypatch, capsys):
    check_broker_config = _script_module()

    def fake_config(name):
        values = {
            "ALPACA_API_KEY_ID": "alpaca-key",
            "ALPACA_API_SECRET_KEY": "alpaca-secret",
        }
        return values.get(name)

    monkeypatch.setattr(check_broker_config, "_resolve_config", fake_config)

    exit_code = check_broker_config.main(["--provider", "alpaca"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["broker_config"] == "ready"
    assert payload["provider"] == "alpaca"
    assert payload["missing"] == []
    assert payload["live_connectivity"] == "not_attempted"
    assert "alpaca-secret" not in json.dumps(payload)


def test_broker_config_script_returns_zero_for_missing_config(monkeypatch, capsys):
    check_broker_config = _script_module()

    monkeypatch.setattr(check_broker_config, "_resolve_config", lambda name: None)

    exit_code = check_broker_config.main(["--provider", "ibkr"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["broker_config"] == "missing"
    assert payload["missing"] == ["IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID"]


def test_broker_config_docs_reference_diagnostic_flow():
    check_broker_config = _script_module()

    root = check_broker_config.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    secrets_example = (root / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

    assert "scripts/check_broker_config.py --provider alpaca" in readme
    assert "scripts/check_broker_config.py --provider ibkr" in readme
    assert "check_broker_config.py" in backlog
    assert "ALPACA_API_KEY_ID" in secrets_example
    assert "IBKR_CLIENT_ID" in secrets_example


def test_broker_config_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/check_broker_config.py", "--provider", "alpaca"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["provider"] == "alpaca"


def test_broker_config_script_uses_lightweight_config_resolver():
    check_broker_config = _script_module()
    source = (check_broker_config.ROOT / "scripts" / "check_broker_config.py").read_text(encoding="utf-8")

    assert "src.config_resolver" in source
    assert "src.alerts" not in source
