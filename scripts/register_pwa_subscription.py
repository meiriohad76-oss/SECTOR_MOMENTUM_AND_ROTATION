"""Register a browser Push API subscription for B-121 PWA alerts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pwa_push import save_push_subscription  # noqa: E402


SUBSCRIPTIONS_PATH = ROOT / "data" / "pwa_push_subscriptions.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription-file", default="", help="JSON file copied from the PWA subscribe panel")
    parser.add_argument("--subscriptions-path", default=str(SUBSCRIPTIONS_PATH), help="local subscription store path")
    parser.add_argument("--label", default="", help="optional device label stored with the subscription")
    parser.add_argument("--captured-at", default="", help="optional ISO timestamp for deterministic imports")
    return parser.parse_args(argv)


def _read_subscription(args: argparse.Namespace) -> dict | None:
    try:
        if args.subscription_file:
            text = Path(args.subscription_file).read_text(encoding="utf-8")
        else:
            text = sys.stdin.read()
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    subscription = _read_subscription(args)
    if subscription is None:
        print(json.dumps({"pwa_subscription": "invalid", "subscriptions": 0}, sort_keys=True))
        return 2

    result = save_push_subscription(
        args.subscriptions_path,
        subscription,
        label=args.label,
        captured_at=args.captured_at or None,
    )
    status = "saved" if result["saved"] else "invalid"
    print(
        json.dumps(
            {"pwa_subscription": status, "subscriptions": result["subscriptions"]},
            sort_keys=True,
        )
    )
    return 0 if result["saved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
