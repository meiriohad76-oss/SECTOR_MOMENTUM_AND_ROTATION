"""Smoke-test optional Telegram and Slack transition alerts."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.alerts import send_telegram_slack_test_alert, telegram_slack_alert_status


def _configured_label(value: bool) -> str:
    return "configured" if value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report alert configuration without sending")
    parser.add_argument("--send-test", action="store_true", help="send a synthetic Telegram/Slack test message")
    parser.add_argument("--message", default="Sector Momentum B-021 alert smoke test", help="test message text")
    parser.add_argument("--timeout", type=int, default=5, help="HTTP timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = telegram_slack_alert_status()
    if args.send_test:
        result = send_telegram_slack_test_alert(args.message, timeout=args.timeout)
        print(f"telegram_slack_smoke=sent telegram={result['telegram']} slack={result['slack']}")
        return 0

    print(
        "telegram_slack_smoke=dry_run "
        f"telegram={_configured_label(status['telegram'])} "
        f"slack={_configured_label(status['slack'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
