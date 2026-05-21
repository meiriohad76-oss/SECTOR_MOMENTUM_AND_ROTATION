from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pwa_push import (  # noqa: E402
    load_push_subscriptions,
    send_web_push_notifications,
    write_notification_feed,
)
from src.scoring import recent_transitions  # noqa: E402


FEED_PATH = ROOT / "public" / "notification-feed.json"
SUBSCRIPTIONS_PATH = ROOT / "data" / "pwa_push_subscriptions.json"


def main() -> int:
    transitions = recent_transitions(n=100)
    dashboard_url = os.environ.get("PWA_DASHBOARD_URL", "/")
    feed_count = write_notification_feed(transitions, FEED_PATH, dashboard_url=dashboard_url)

    subscriptions = load_push_subscriptions(SUBSCRIPTIONS_PATH)
    private_key = os.environ.get("VAPID_PRIVATE_KEY")
    claim_email = os.environ.get("VAPID_CLAIM_EMAIL")
    claims = {"sub": f"mailto:{claim_email}"} if claim_email else None
    summary = send_web_push_notifications(
        transitions,
        subscriptions,
        vapid_private_key=private_key,
        vapid_claims=claims,
        dashboard_url=dashboard_url,
    )
    print(
        json.dumps(
            {
                "pwa_push": "ok" if summary.sent else "skipped",
                "feed_notifications": feed_count,
                "attempted": summary.attempted,
                "sent": summary.sent,
                "failed": summary.failed,
                "skipped": summary.skipped,
            },
            sort_keys=True,
        )
    )
    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
