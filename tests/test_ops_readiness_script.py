from __future__ import annotations

import json

from scripts import check_ops_readiness


def test_ops_readiness_reports_all_pending_integration_tickets_without_secret_values(tmp_path, monkeypatch, capsys):
    subscriptions_path = tmp_path / "subscriptions.json"
    subscriptions_path.write_text(
        json.dumps(
            {
                "subscriptions": [
                    {
                        "endpoint": "https://push.example.test/sub",
                        "keys": {"p256dh": "browser-public", "auth": "browser-auth"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    data_feed_dir = tmp_path / "data" / "feeds"
    public_feed_dir = tmp_path / "public" / "feeds"
    data_feed_dir.mkdir(parents=True)
    public_feed_dir.mkdir(parents=True)
    (data_feed_dir / "transitions.rss").write_text("<rss />", encoding="utf-8")
    (data_feed_dir / "transitions.ics").write_text("BEGIN:VCALENDAR", encoding="utf-8")
    (public_feed_dir / "transitions.rss").write_text("<rss />", encoding="utf-8")
    (public_feed_dir / "transitions.ics").write_text("BEGIN:VCALENDAR", encoding="utf-8")

    def fake_config(name: str) -> str | None:
        values = {
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "TELEGRAM_CHAT_ID": "123",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret",
            "SMTP_HOST": "smtp.example.test",
            "EMAIL_DIGEST_TO": "ops@example.test",
            "VAPID_PRIVATE_KEY": "data/vapid_private_key.pem",
            "VAPID_PUBLIC_KEY": "public-key",
            "VAPID_CLAIM_EMAIL": "ops@example.test",
            "DISCORD_WEBHOOK_URL": "https://discord.test/secret",
            "BROKER_PROVIDER": "alpaca",
            "ALPACA_API_KEY_ID": "alpaca-key",
            "ALPACA_API_SECRET_KEY": "alpaca-secret",
        }
        return values.get(name)

    monkeypatch.setattr(check_ops_readiness, "resolve_config_value", fake_config)

    exit_code = check_ops_readiness.main(
        [
            "--subscriptions-path",
            str(subscriptions_path),
            "--feed-dir",
            str(data_feed_dir),
            "--public-feed-dir",
            str(public_feed_dir),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    serialized = json.dumps(payload)
    assert exit_code == 0
    assert set(payload) >= {"B-021", "B-120", "B-121", "B-122", "B-123", "B-131"}
    assert payload["B-021"]["telegram"] == "configured"
    assert payload["B-120"]["smtp_delivery"] == "configured"
    assert payload["B-121"]["subscriptions"] == 1
    assert payload["B-122"]["public_feed_artifacts"] == "ready"
    assert payload["B-123"]["discord"] == "configured"
    assert payload["B-131"]["broker_config"] == "ready"
    assert "secret" not in serialized
    assert "telegram-token" not in serialized


def test_ops_readiness_docs_reference_single_command():
    root = check_ops_readiness.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "scripts/check_ops_readiness.py" in readme
    assert "scripts/check_ops_readiness.py" in backlog
