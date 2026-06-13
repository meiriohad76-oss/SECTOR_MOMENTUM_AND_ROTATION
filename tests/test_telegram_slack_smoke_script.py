from __future__ import annotations

import importlib
import subprocess
import sys


def _script_module():
    return importlib.import_module("scripts.smoke_telegram_slack_alerts")


def test_telegram_slack_smoke_dry_run_reports_config_without_sending(monkeypatch, capsys):
    smoke_telegram_slack_alerts = _script_module()
    monkeypatch.setattr(
        smoke_telegram_slack_alerts,
        "telegram_slack_alert_status",
        lambda: {"telegram": True, "slack": False},
    )

    def fail_send(*_args, **_kwargs):
        raise AssertionError("dry-run must not send alerts")

    monkeypatch.setattr(smoke_telegram_slack_alerts, "send_telegram_slack_test_alert", fail_send)

    exit_code = smoke_telegram_slack_alerts.main(["--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "telegram_slack_smoke=dry_run" in output
    assert "telegram=configured" in output
    assert "slack=missing" in output


def test_telegram_slack_smoke_send_test_uses_explicit_flag(monkeypatch, capsys):
    smoke_telegram_slack_alerts = _script_module()
    calls = []
    monkeypatch.setattr(
        smoke_telegram_slack_alerts,
        "telegram_slack_alert_status",
        lambda: {"telegram": True, "slack": True},
    )

    def fake_send(text, timeout=5):
        calls.append((text, timeout))
        return {"telegram": "sent", "slack": "failed"}

    monkeypatch.setattr(smoke_telegram_slack_alerts, "send_telegram_slack_test_alert", fake_send)

    exit_code = smoke_telegram_slack_alerts.main(["--send-test", "--message", "hello", "--timeout", "9"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert calls == [("hello", 9)]
    assert "telegram_slack_smoke=sent" in output
    assert "telegram=sent" in output
    assert "slack=failed" in output


def test_telegram_slack_smoke_docs_reference_safe_validation_flow():
    smoke_telegram_slack_alerts = _script_module()
    root = smoke_telegram_slack_alerts.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    secrets_example = (root / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

    assert "scripts/smoke_telegram_slack_alerts.py --dry-run" in readme
    assert "scripts/smoke_telegram_slack_alerts.py --send-test" in readme
    assert "smoke_telegram_slack_alerts.py" in backlog
    assert "TELEGRAM_BOT_TOKEN" in secrets_example
    assert "SLACK_WEBHOOK_URL" in secrets_example


def test_telegram_slack_smoke_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/smoke_telegram_slack_alerts.py", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "telegram_slack_smoke=dry_run" in result.stdout
