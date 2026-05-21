from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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


def test_low_severity_digest_transitions_selects_yesterday_non_high_states():
    now = datetime(2026, 5, 21, 8, 0, tzinfo=ZoneInfo("America/New_York"))
    transitions = [
        {"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"},
        {"ticker": "XLE", "from": "WARNING", "to": "EXIT", "date": "2026-05-20"},
        {"ticker": "XLF", "from": "BEARISH_STAGE_4", "to": "STAGE_1_BASING", "date": "2026-05-20"},
        {"ticker": "XLV", "from": "HOLD", "to": "WARNING", "date": "2026-05-21"},
        {"ticker": "XLU", "from": "EXIT", "to": "BEARISH_STAGE_4", "date": "2026-05-20"},
    ]

    digest_rows = alerts.low_severity_digest_transitions(transitions, now=now)

    assert [row["ticker"] for row in digest_rows] == ["XLK", "XLF"]


def test_format_email_digest_builds_subject_and_body():
    digest = alerts.format_email_digest(
        [
            {"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"},
            {"ticker": "XLF", "from": "BEARISH_STAGE_4", "to": "STAGE_1_BASING", "date": "2026-05-20"},
        ],
        digest_date="2026-05-20",
    )

    assert digest["subject"] == "Sector Momentum LOW transition digest - 2026-05-20"
    assert "LOW severity transitions for 2026-05-20" in digest["body"]
    assert "XLK transitioned HOLD -> WARNING on 2026-05-20" in digest["body"]
    assert "XLF transitioned BEARISH_STAGE_4 -> STAGE_1_BASING on 2026-05-20" in digest["body"]


def test_send_low_severity_email_digest_skips_network_when_unconfigured(monkeypatch):
    calls = []
    monkeypatch.setattr(alerts, "_resolve_secret", lambda name: None)
    monkeypatch.setattr(alerts.smtplib, "SMTP", lambda *args, **kwargs: calls.append((args, kwargs)))

    sent = alerts.send_low_severity_email_digest(
        [{"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}],
        now=datetime(2026, 5, 21, 8, 0, tzinfo=ZoneInfo("America/New_York")),
    )

    assert sent is False
    assert calls == []


def test_send_low_severity_email_digest_sends_configured_smtp_message(monkeypatch):
    smtp_calls = []

    def fake_secret(name):
        values = {
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": "2525",
            "SMTP_USERNAME": "smtp-user",
            "SMTP_PASSWORD": "smtp-password",
            "SMTP_STARTTLS": "true",
            "EMAIL_DIGEST_FROM": "digest@example.test",
            "EMAIL_DIGEST_TO": "one@example.test, two@example.test",
        }
        return values.get(name)

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            smtp_calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def starttls(self):
            smtp_calls.append(("starttls",))

        def login(self, username, password):
            smtp_calls.append(("login", username, password))

        def send_message(self, message):
            smtp_calls.append(("send_message", message))

    monkeypatch.setattr(alerts, "_resolve_secret", fake_secret)
    monkeypatch.setattr(alerts.smtplib, "SMTP", FakeSMTP)

    sent = alerts.send_low_severity_email_digest(
        [{"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}],
        now=datetime(2026, 5, 21, 8, 0, tzinfo=ZoneInfo("America/New_York")),
        timeout=9,
    )

    assert sent is True
    assert smtp_calls[0] == ("connect", "smtp.example.test", 2525, 9)
    assert ("starttls",) in smtp_calls
    assert ("login", "smtp-user", "smtp-password") in smtp_calls
    message = smtp_calls[-1][1]
    assert message["From"] == "digest@example.test"
    assert message["To"] == "one@example.test, two@example.test"
    assert message["Subject"] == "Sector Momentum LOW transition digest - 2026-05-20"
    assert "XLK transitioned HOLD -> WARNING" in message.get_content()


def test_send_low_severity_email_digest_ignores_smtp_errors(monkeypatch):
    def fake_secret(name):
        values = {
            "SMTP_HOST": "smtp.example.test",
            "EMAIL_DIGEST_FROM": "digest@example.test",
            "EMAIL_DIGEST_TO": "one@example.test",
        }
        return values.get(name)

    class FailingSMTP:
        def __init__(self, *args, **kwargs):
            raise alerts.smtplib.SMTPException("smtp down")

    monkeypatch.setattr(alerts, "_resolve_secret", fake_secret)
    monkeypatch.setattr(alerts.smtplib, "SMTP", FailingSMTP)

    sent = alerts.send_low_severity_email_digest(
        [{"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}],
        now=datetime(2026, 5, 21, 8, 0, tzinfo=ZoneInfo("America/New_York")),
    )

    assert sent is False
