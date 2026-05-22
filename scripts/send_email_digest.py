"""Send the optional LOW severity transition email digest."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE_FILE = Path(os.environ.get("STATE_FILE", ROOT / "state.json"))


def recent_transitions(n: int = 25) -> list[dict]:
    if not STATE_FILE.exists():
        return []
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return []
    return list(reversed(payload.get("transitions", [])))[:n]


def send_low_severity_email_digest(transitions: list[dict]) -> bool:
    from src.alerts import send_low_severity_email_digest as send_digest

    return send_digest(transitions)


def _eligible_digest_count(transitions: list[dict], *, digest_date: str | None = None) -> int:
    from src.alerts import low_severity_digest_transitions

    return len(low_severity_digest_transitions(transitions, digest_date=digest_date))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report digest eligibility without sending SMTP email",
    )
    parser.add_argument(
        "--digest-date",
        help="YYYY-MM-DD date to evaluate in dry-run mode; defaults to yesterday in US/Eastern",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="maximum recent transition rows to inspect",
    )
    return parser.parse_args([] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    transitions = list(reversed(recent_transitions(n=args.limit)))
    if args.dry_run:
        eligible_count = _eligible_digest_count(transitions, digest_date=args.digest_date)
        print(
            "email_digest=dry_run "
            f"recent_transitions={len(transitions)} "
            f"eligible_transitions={eligible_count}"
        )
        return 0

    sent = send_low_severity_email_digest(transitions) if transitions else False
    print(f"email_digest={'sent' if sent else 'skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
