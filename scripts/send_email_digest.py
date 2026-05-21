"""Send the optional LOW severity transition email digest."""
from __future__ import annotations

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


def main() -> int:
    transitions = list(reversed(recent_transitions(n=500)))
    sent = send_low_severity_email_digest(transitions) if transitions else False
    print(f"email_digest={'sent' if sent else 'skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
