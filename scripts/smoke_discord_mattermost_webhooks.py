"""Smoke-test optional Discord and Mattermost transition webhooks."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.alerts import discord_mattermost_webhook_status, send_discord_mattermost_test_alert


def _configured_label(value: bool) -> str:
    return "configured" if value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report webhook configuration without sending")
    parser.add_argument("--send-test", action="store_true", help="send a synthetic Discord/Mattermost test message")
    parser.add_argument("--message", default="Sector Momentum B-123 webhook smoke test", help="test message text")
    parser.add_argument("--timeout", type=int, default=5, help="HTTP timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = discord_mattermost_webhook_status()
    if args.send_test:
        result = send_discord_mattermost_test_alert(args.message, timeout=args.timeout)
        print(f"webhook_smoke=sent discord={result['discord']} mattermost={result['mattermost']}")
        return 0

    print(
        "webhook_smoke=dry_run "
        f"discord={_configured_label(status['discord'])} "
        f"mattermost={_configured_label(status['mattermost'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
