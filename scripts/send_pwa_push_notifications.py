from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pwa_push import (  # noqa: E402
    build_push_notifications,
    load_push_subscriptions,
    send_web_push_notifications,
    write_notification_feed,
)
from src.scoring import recent_transitions  # noqa: E402
from src.config_resolver import resolve_config_value  # noqa: E402


FEED_PATH = ROOT / "public" / "notification-feed.json"
SUBSCRIPTIONS_PATH = ROOT / "data" / "pwa_push_subscriptions.json"


def _resolve_config(name: str) -> str | None:
    return resolve_config_value(name) or os.environ.get(name)


def _config_label(value: str | None) -> str:
    return "configured" if value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write and optionally send HIGH severity PWA push notifications.")
    parser.add_argument("--dry-run", action="store_true", help="write the feed and report config without sending push")
    parser.add_argument("--feed-path", default=str(FEED_PATH), help="notification feed JSON path")
    parser.add_argument("--subscriptions-path", default=str(SUBSCRIPTIONS_PATH), help="browser subscriptions JSON path")
    parser.add_argument("--dashboard-url", default="", help="dashboard URL for notification click-throughs")
    parser.add_argument("--limit", type=int, default=100, help="maximum recent transition rows to inspect")
    parser.add_argument("--timeout", type=int, default=10, help="Web Push timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    transitions = recent_transitions(n=args.limit)
    dashboard_url = args.dashboard_url or _resolve_config("PWA_DASHBOARD_URL") or "/"

    subscriptions = load_push_subscriptions(args.subscriptions_path)
    private_key = _resolve_config("VAPID_PRIVATE_KEY")
    claim_email = _resolve_config("VAPID_CLAIM_EMAIL")
    claims = {"sub": f"mailto:{claim_email}"} if claim_email else None
    feed_count = len(build_push_notifications(transitions, dashboard_url=dashboard_url))
    payload = {
        "feed_notifications": feed_count,
        "subscriptions": len(subscriptions),
        "vapid_private_key": _config_label(private_key),
        "vapid_claim_email": _config_label(claim_email),
    }
    if args.dry_run:
        print(json.dumps({"pwa_push": "dry_run", **payload}, sort_keys=True))
        return 0

    feed_count = write_notification_feed(transitions, args.feed_path, dashboard_url=dashboard_url)
    payload["feed_notifications"] = feed_count
    summary = send_web_push_notifications(
        transitions,
        subscriptions,
        vapid_private_key=private_key,
        vapid_claims=claims,
        dashboard_url=dashboard_url,
        timeout=args.timeout,
    )
    print(
        json.dumps(
            {
                "pwa_push": "ok" if summary.sent else "skipped",
                **payload,
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
