"""Check broker API configuration readiness without connecting to a broker."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.broker_config import broker_config_status
from src.config_resolver import resolve_config_value


def _resolve_config(name: str) -> str | None:
    return resolve_config_value(name) or os.environ.get(name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        default="",
        help="broker provider to check: alpaca, ibkr, or none; defaults to BROKER_PROVIDER",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    provider = args.provider or _resolve_config("BROKER_PROVIDER") or "none"
    status = broker_config_status(provider, resolver=_resolve_config)
    print(
        json.dumps(
            {
                "broker_config": status.state,
                "provider": status.provider,
                "configured": status.configured,
                "missing": status.missing,
                "optional_configured": status.optional_configured,
                "live_connectivity": status.live_connectivity,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
