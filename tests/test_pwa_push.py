from __future__ import annotations

import json

from src import pwa_push


def test_build_push_notifications_keeps_only_high_severity_transitions():
    transitions = [
        {"ticker": "XLK", "from": "HOLD", "to": "EXIT", "date": "2026-05-20"},
        {"ticker": "XLF", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"},
        {"ticker": "XLE", "from": "EXIT", "to": "BEARISH_STAGE_4", "date": "2026-05-21"},
    ]

    notifications = pwa_push.build_push_notifications(
        transitions,
        dashboard_url="https://dashboard.example.test",
    )

    assert [item["ticker"] for item in notifications] == ["XLK", "XLE"]
    assert notifications[0]["title"] == "XLK EXIT"
    assert "XLK transitioned HOLD -> EXIT on 2026-05-20" in notifications[0]["body"]
    assert notifications[0]["url"] == "https://dashboard.example.test/?ticker=XLK"
    assert notifications[0]["tag"] == "sector-momentum-XLK-2026-05-20-EXIT"


def test_load_push_subscriptions_ignores_invalid_rows(tmp_path):
    path = tmp_path / "subscriptions.json"
    path.write_text(
        json.dumps(
            {
                "subscriptions": [
                    {
                        "endpoint": "https://push.example.test/abc",
                        "keys": {"p256dh": "pkey", "auth": "auth"},
                    },
                    {"endpoint": "", "keys": {"p256dh": "missing"}},
                    {"not": "a subscription"},
                ]
            }
        ),
        encoding="utf-8",
    )

    subscriptions = pwa_push.load_push_subscriptions(path)

    assert subscriptions == [
        {
            "endpoint": "https://push.example.test/abc",
            "keys": {"p256dh": "pkey", "auth": "auth"},
        }
    ]


def test_save_push_subscription_merges_by_endpoint_without_duplicate_rows(tmp_path):
    path = tmp_path / "subscriptions.json"
    existing = {
        "subscriptions": [
            {
                "endpoint": "https://push.example.test/old",
                "keys": {"p256dh": "old-key", "auth": "old-auth"},
                "label": "phone",
            }
        ]
    }
    path.write_text(json.dumps(existing), encoding="utf-8")

    first = pwa_push.save_push_subscription(
        path,
        {
            "endpoint": "https://push.example.test/new",
            "keys": {"p256dh": "new-key", "auth": "new-auth"},
        },
        label="tablet",
        captured_at="2026-05-22T12:30:00Z",
    )
    second = pwa_push.save_push_subscription(
        path,
        {
            "endpoint": "https://push.example.test/new",
            "keys": {"p256dh": "replacement-key", "auth": "replacement-auth"},
        },
        label="tablet-new",
        captured_at="2026-05-22T12:31:00Z",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert first == {"saved": True, "subscriptions": 2}
    assert second == {"saved": True, "subscriptions": 2}
    assert [row["endpoint"] for row in payload["subscriptions"]] == [
        "https://push.example.test/old",
        "https://push.example.test/new",
    ]
    assert payload["subscriptions"][1]["label"] == "tablet-new"
    assert payload["subscriptions"][1]["captured_at"] == "2026-05-22T12:31:00Z"


def test_save_push_subscription_rejects_invalid_subscription(tmp_path):
    path = tmp_path / "subscriptions.json"

    result = pwa_push.save_push_subscription(path, {"endpoint": "missing-keys"})

    assert result == {"saved": False, "subscriptions": 0}
    assert not path.exists()


def test_write_notification_feed_serializes_installable_pwa_payload(tmp_path):
    path = tmp_path / "notification-feed.json"

    count = pwa_push.write_notification_feed(
        [{"ticker": "XLK", "from": "HOLD", "to": "EXIT", "date": "2026-05-20"}],
        path,
        dashboard_url="/dashboard",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert count == 1
    assert payload["version"] == 1
    assert payload["notifications"][0]["ticker"] == "XLK"
    assert payload["notifications"][0]["url"] == "/dashboard?ticker=XLK"


def test_send_web_push_notifications_is_best_effort_and_counts_failures():
    calls = []

    def fake_sender(subscription, data, vapid_private_key, vapid_claims, timeout):
        calls.append((subscription, json.loads(data), vapid_private_key, vapid_claims, timeout))
        if subscription["endpoint"].endswith("/bad"):
            raise RuntimeError("push down")

    summary = pwa_push.send_web_push_notifications(
        [{"ticker": "XLK", "from": "HOLD", "to": "EXIT", "date": "2026-05-20"}],
        [
            {"endpoint": "https://push.example.test/good", "keys": {"p256dh": "pkey", "auth": "auth"}},
            {"endpoint": "https://push.example.test/bad", "keys": {"p256dh": "pkey", "auth": "auth"}},
        ],
        webpush_fn=fake_sender,
        vapid_private_key="private-key",
        vapid_claims={"sub": "mailto:ops@example.test"},
        timeout=9,
    )

    assert summary.attempted == 2
    assert summary.sent == 1
    assert summary.failed == 1
    assert summary.skipped == 0
    assert calls[0][1]["ticker"] == "XLK"
    assert calls[0][2] == "private-key"
    assert calls[0][3] == {"sub": "mailto:ops@example.test"}
    assert calls[0][4] == 9
