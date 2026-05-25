"""Report optional integration readiness without printing secret values."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.broker_config import broker_config_status  # noqa: E402
from src.config_resolver import resolve_config_value  # noqa: E402
from src.pwa_push import load_push_subscriptions  # noqa: E402


def _label(value: str | None) -> str:
    return "configured" if value else "missing"


def _ready_or_missing(paths: list[Path]) -> str:
    return "ready" if all(path.exists() and path.stat().st_size > 0 for path in paths) else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscriptions-path", default=str(ROOT / "data" / "pwa_push_subscriptions.json"))
    parser.add_argument("--feed-dir", default=str(ROOT / "data" / "feeds"))
    parser.add_argument("--public-feed-dir", default=str(ROOT / "public" / "feeds"))
    return parser.parse_args(argv)


def _broker_status() -> dict:
    provider = resolve_config_value("BROKER_PROVIDER") or "none"
    status = broker_config_status(provider, resolver=resolve_config_value)
    return {
        "provider": status.provider,
        "broker_config": status.state,
        "configured": status.configured,
        "missing": status.missing,
        "live_connectivity": status.live_connectivity,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    subscriptions = load_push_subscriptions(args.subscriptions_path)
    feed_dir = Path(args.feed_dir)
    public_feed_dir = Path(args.public_feed_dir)

    payload = {
        "B-021": {
            "telegram": "configured"
            if resolve_config_value("TELEGRAM_BOT_TOKEN") and resolve_config_value("TELEGRAM_CHAT_ID")
            else "missing",
            "slack": _label(resolve_config_value("SLACK_WEBHOOK_URL")),
        },
        "B-120": {
            "smtp_delivery": "configured"
            if resolve_config_value("SMTP_HOST") and resolve_config_value("EMAIL_DIGEST_TO")
            else "missing",
            "smtp_host": _label(resolve_config_value("SMTP_HOST")),
            "email_digest_to": _label(resolve_config_value("EMAIL_DIGEST_TO")),
        },
        "B-121": {
            "vapid_private_key": _label(resolve_config_value("VAPID_PRIVATE_KEY")),
            "vapid_public_key": _label(resolve_config_value("VAPID_PUBLIC_KEY")),
            "vapid_claim_email": _label(resolve_config_value("VAPID_CLAIM_EMAIL")),
            "subscriptions": len(subscriptions),
            "pywebpush": "available" if importlib.util.find_spec("pywebpush") else "missing",
        },
        "B-122": {
            "feed_artifacts": _ready_or_missing([feed_dir / "transitions.rss", feed_dir / "transitions.ics"]),
            "public_feed_artifacts": _ready_or_missing(
                [public_feed_dir / "transitions.rss", public_feed_dir / "transitions.ics"]
            ),
        },
        "B-123": {
            "discord": _label(resolve_config_value("DISCORD_WEBHOOK_URL")),
            "mattermost": _label(resolve_config_value("MATTERMOST_WEBHOOK_URL")),
        },
        "B-131": _broker_status(),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
