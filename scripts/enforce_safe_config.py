"""Apply secret-safe production config hardening to local Streamlit secrets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
MASSIVE_VERIFY_SSL_RE = re.compile(r'(?m)^(\s*MASSIVE_VERIFY_SSL\s*=\s*)["\']([^"\']*)["\'](\s*)$')
SAFE_SSL_LINE = 'MASSIVE_VERIFY_SSL = "true"'


def enforce_massive_verify_ssl(path: str | Path) -> dict[str, object]:
    secrets_path = Path(path)
    prior_exists = secrets_path.exists()
    text = secrets_path.read_text(encoding="utf-8") if prior_exists else ""
    match = MASSIVE_VERIFY_SSL_RE.search(text)
    if match:
        current_value = match.group(2).strip().lower()
        if current_value == "true":
            updated = text
            action = "already_safe"
        else:
            updated = MASSIVE_VERIFY_SSL_RE.sub(SAFE_SSL_LINE, text, count=1)
            action = "updated"
    else:
        separator = "\n" if text and not text.endswith("\n") else ""
        updated = f"{text}{separator}{SAFE_SSL_LINE}\n"
        action = "added"
    if updated != text or not prior_exists:
        secrets_path.parent.mkdir(parents=True, exist_ok=True)
        secrets_path.write_text(updated, encoding="utf-8")
    return {
        "path": str(secrets_path),
        "exists_before": prior_exists,
        "massive_verify_ssl": "true",
        "action": action,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-path", default=str(DEFAULT_SECRETS_PATH))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = enforce_massive_verify_ssl(args.secrets_path)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
