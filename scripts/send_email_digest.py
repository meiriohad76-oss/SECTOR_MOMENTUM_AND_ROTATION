"""Send the optional LOW severity transition email digest."""
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.alerts import send_low_severity_email_digest
from src.scoring import recent_transitions


def main() -> int:
    transitions = list(reversed(recent_transitions(n=500)))
    sent = send_low_severity_email_digest(transitions)
    print(f"email_digest={'sent' if sent else 'skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
