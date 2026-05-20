from __future__ import annotations

from src import alerts


def test_send_transition_alerts_skips_network_when_channels_unconfigured(monkeypatch):
    calls = []
    monkeypatch.setattr(alerts, "_resolve_secret", lambda name: None)
    monkeypatch.setattr(alerts.requests, "post", lambda *args, **kwargs: calls.append((args, kwargs)))

    alerts.send_transition_alerts(
        [{"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}]
    )

    assert calls == []


def test_send_transition_alerts_posts_to_telegram_and_slack(monkeypatch):
    calls = []

    def fake_secret(name):
        values = {
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "TELEGRAM_CHAT_ID": "12345",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.test/abc",
        }
        return values.get(name)

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(alerts, "_resolve_secret", fake_secret)
    monkeypatch.setattr(alerts.requests, "post", fake_post)

    alerts.send_transition_alerts(
        [{"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}],
        timeout=7,
    )

    assert calls[0][0] == "https://api.telegram.org/bottelegram-token/sendMessage"
    assert calls[0][1]["json"]["chat_id"] == "12345"
    assert "XLK transitioned HOLD -> WARNING" in calls[0][1]["json"]["text"]
    assert calls[0][1]["timeout"] == 7
    assert calls[1][0] == "https://hooks.slack.test/abc"
    assert "XLK transitioned HOLD -> WARNING" in calls[1][1]["json"]["text"]


def test_send_transition_alerts_ignores_provider_request_errors(monkeypatch):
    def fake_secret(name):
        values = {
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "TELEGRAM_CHAT_ID": "12345",
        }
        return values.get(name)

    def fail_post(url, **kwargs):
        raise alerts.requests.Timeout("alert timed out")

    monkeypatch.setattr(alerts, "_resolve_secret", fake_secret)
    monkeypatch.setattr(alerts.requests, "post", fail_post)

    alerts.send_transition_alerts(
        [{"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}]
    )
