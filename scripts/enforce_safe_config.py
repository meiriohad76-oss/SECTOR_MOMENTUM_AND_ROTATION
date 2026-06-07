"""Apply secret-safe production config hardening to local Streamlit secrets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
SAFE_FLAGS = {
    "MASSIVE_VERIFY_SSL": "true",
    "MASSIVE_TRADES_STUB_MODE": "false",
    "FINRA_ATS_STUB_MODE": "false",
    "FINRA_SHORT_INTEREST_STUB_MODE": "false",
}


def _flag_re(name: str) -> re.Pattern[str]:
    return re.compile(rf'(?m)^(\s*{re.escape(name)}\s*=\s*)["\']([^"\']*)["\'](\s*)$')


def _upsert_flag(text: str, name: str, value: str) -> tuple[str, str]:
    pattern = _flag_re(name)
    safe_line = f'{name} = "{value}"'
    match = pattern.search(text)
    if match:
        current_value = match.group(2).strip().lower()
        if current_value == value:
            return text, "already_safe"
        return pattern.sub(safe_line, text, count=1), "updated"
    separator = "\n" if text and not text.endswith("\n") else ""
    return f"{text}{separator}{safe_line}\n", "added"


def enforce_safe_config(path: str | Path) -> dict[str, object]:
    secrets_path = Path(path)
    prior_exists = secrets_path.exists()
    text = secrets_path.read_text(encoding="utf-8") if prior_exists else ""
    updated = text
    flag_actions: dict[str, str] = {}
    for name, value in SAFE_FLAGS.items():
        updated, flag_actions[name] = _upsert_flag(updated, name, value)
    if any(action == "updated" for action in flag_actions.values()):
        action = "updated"
    elif any(action == "added" for action in flag_actions.values()):
        action = "added"
    else:
        action = "already_safe"
    if updated != text or not prior_exists:
        secrets_path.parent.mkdir(parents=True, exist_ok=True)
        secrets_path.write_text(updated, encoding="utf-8")
    return {
        "path": str(secrets_path),
        "exists_before": prior_exists,
        "massive_verify_ssl": "true",
        "enabled_provider_flow_lanes": [
            "massive_block_trades",
            "finra_ats_dark_pool",
            "finra_short_interest",
        ],
        "flag_actions": flag_actions,
        "action": action,
    }


def enforce_massive_verify_ssl(path: str | Path) -> dict[str, object]:
    """Backward-compatible wrapper for older callers/tests."""
    return enforce_safe_config(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-path", default=str(DEFAULT_SECRETS_PATH))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = enforce_safe_config(args.secrets_path)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
