from __future__ import annotations

import importlib
import subprocess
import sys


def _script_module():
    return importlib.import_module("scripts.smoke_discord_mattermost_webhooks")


def test_discord_mattermost_smoke_dry_run_reports_config_without_sending(monkeypatch, capsys):
    smoke_discord_mattermost_webhooks = _script_module()
    monkeypatch.setattr(
        smoke_discord_mattermost_webhooks,
        "discord_mattermost_webhook_status",
        lambda: {"discord": True, "mattermost": False},
    )

    def fail_send(*_args, **_kwargs):
        raise AssertionError("dry-run must not send webhooks")

    monkeypatch.setattr(smoke_discord_mattermost_webhooks, "send_discord_mattermost_test_alert", fail_send)

    exit_code = smoke_discord_mattermost_webhooks.main(["--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "webhook_smoke=dry_run" in output
    assert "discord=configured" in output
    assert "mattermost=missing" in output


def test_discord_mattermost_smoke_send_test_uses_explicit_flag(monkeypatch, capsys):
    smoke_discord_mattermost_webhooks = _script_module()
    calls = []
    monkeypatch.setattr(
        smoke_discord_mattermost_webhooks,
        "discord_mattermost_webhook_status",
        lambda: {"discord": True, "mattermost": True},
    )

    def fake_send(text, timeout=5):
        calls.append((text, timeout))
        return {"discord": "sent", "mattermost": "failed"}

    monkeypatch.setattr(smoke_discord_mattermost_webhooks, "send_discord_mattermost_test_alert", fake_send)

    exit_code = smoke_discord_mattermost_webhooks.main(["--send-test", "--message", "hello", "--timeout", "9"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert calls == [("hello", 9)]
    assert "webhook_smoke=sent" in output
    assert "discord=sent" in output
    assert "mattermost=failed" in output


def test_discord_mattermost_smoke_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/smoke_discord_mattermost_webhooks.py", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "webhook_smoke=dry_run" in result.stdout


def test_discord_mattermost_smoke_docs_reference_safe_validation_flow():
    smoke_discord_mattermost_webhooks = _script_module()
    root = smoke_discord_mattermost_webhooks.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    secrets_example = (root / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

    assert "scripts/smoke_discord_mattermost_webhooks.py --dry-run" in readme
    assert "scripts/smoke_discord_mattermost_webhooks.py --send-test" in readme
    assert "smoke_discord_mattermost_webhooks.py" in backlog
    assert "DISCORD_WEBHOOK_URL" in secrets_example
    assert "MATTERMOST_WEBHOOK_URL" in secrets_example
