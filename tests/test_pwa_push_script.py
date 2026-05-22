from __future__ import annotations

import json
import subprocess
import sys

from scripts import send_pwa_push_notifications


def test_pwa_push_script_dry_run_reports_config_without_sending(tmp_path, monkeypatch, capsys):
    subscriptions_path = tmp_path / "subscriptions.json"
    feed_path = tmp_path / "notification-feed.json"
    subscriptions_path.write_text(
        json.dumps(
            {
                "subscriptions": [
                    {
                        "endpoint": "https://push.example.test/sub",
                        "keys": {"p256dh": "pkey", "auth": "auth"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        send_pwa_push_notifications,
        "recent_transitions",
        lambda n=100: [{"ticker": "XLK", "from": "HOLD", "to": "EXIT", "date": "2026-05-21"}],
    )
    monkeypatch.setattr(send_pwa_push_notifications, "_resolve_config", lambda name: None)

    def fail_send(*_args, **_kwargs):
        raise AssertionError("dry-run must not send push notifications")

    monkeypatch.setattr(send_pwa_push_notifications, "send_web_push_notifications", fail_send)

    exit_code = send_pwa_push_notifications.main(
        [
            "--dry-run",
            "--feed-path",
            str(feed_path),
            "--subscriptions-path",
            str(subscriptions_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["pwa_push"] == "dry_run"
    assert payload["feed_notifications"] == 1
    assert payload["subscriptions"] == 1
    assert payload["vapid_private_key"] == "missing"
    assert payload["vapid_claim_email"] == "missing"
    assert "private" not in json.dumps(payload).lower().replace("vapid_private_key", "")
    assert not feed_path.exists()


def test_pwa_push_script_uses_config_and_cli_paths_for_send(tmp_path, monkeypatch, capsys):
    subscriptions_path = tmp_path / "subscriptions.json"
    feed_path = tmp_path / "notification-feed.json"
    subscriptions_path.write_text(
        json.dumps(
            [
                {
                    "endpoint": "https://push.example.test/sub",
                    "keys": {"p256dh": "pkey", "auth": "auth"},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        send_pwa_push_notifications,
        "recent_transitions",
        lambda n=100: [{"ticker": "XLK", "from": "HOLD", "to": "EXIT", "date": "2026-05-21"}],
    )

    def fake_config(name):
        values = {
            "VAPID_PRIVATE_KEY": "secret-key",
            "VAPID_CLAIM_EMAIL": "ops@example.test",
            "PWA_DASHBOARD_URL": "https://dashboard.example.test",
        }
        return values.get(name)

    class Summary:
        attempted = 1
        sent = 1
        failed = 0
        skipped = 0

    send_calls = []

    def fake_send(transitions, subscriptions, **kwargs):
        send_calls.append((list(transitions), list(subscriptions), kwargs))
        return Summary()

    monkeypatch.setattr(send_pwa_push_notifications, "_resolve_config", fake_config)
    monkeypatch.setattr(send_pwa_push_notifications, "send_web_push_notifications", fake_send)

    exit_code = send_pwa_push_notifications.main(
        [
            "--feed-path",
            str(feed_path),
            "--subscriptions-path",
            str(subscriptions_path),
            "--timeout",
            "8",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["pwa_push"] == "ok"
    assert payload["subscriptions"] == 1
    assert payload["vapid_private_key"] == "configured"
    assert payload["vapid_claim_email"] == "configured"
    assert send_calls[0][2]["vapid_private_key"] == "secret-key"
    assert send_calls[0][2]["vapid_claims"] == {"sub": "mailto:ops@example.test"}
    assert send_calls[0][2]["dashboard_url"] == "https://dashboard.example.test"
    assert send_calls[0][2]["timeout"] == 8
    assert "secret-key" not in json.dumps(payload)


def test_pwa_push_script_docs_reference_dry_run_and_config():
    root = send_pwa_push_notifications.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    secrets_example = (root / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

    assert "scripts/send_pwa_push_notifications.py --dry-run" in readme
    assert "without sending or rewriting the feed file" in readme
    assert "VAPID_PRIVATE_KEY" in secrets_example
    assert "VAPID_CLAIM_EMAIL" in secrets_example
    assert "--dry-run" in backlog


def test_pwa_push_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/send_pwa_push_notifications.py", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["pwa_push"] == "dry_run"
