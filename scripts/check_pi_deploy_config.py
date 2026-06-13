"""Validate GitHub Actions Pi deploy secret names without printing secrets."""
from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = ("PI_HOST", "PI_USER", "PI_SSH_KEY", "PI_KNOWN_HOSTS", "PI_REPO_PATH")
OPTIONAL_FIELDS = ("PI_SERVICE_NAME",)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    configured = [name for name in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS) if _has_value(os.environ.get(name))]
    missing = [name for name in REQUIRED_FIELDS if name not in configured]
    optional_missing = [name for name in OPTIONAL_FIELDS if name not in configured]
    print(
        json.dumps(
            {
                "pi_deploy_config": "ready" if not missing else "missing",
                "configured": configured,
                "missing": missing,
                "optional_missing": optional_missing,
            },
            sort_keys=True,
        )
    )
    return 0


def _has_value(value: str | None) -> bool:
    return bool(str(value).strip()) if value is not None else False


if __name__ == "__main__":
    raise SystemExit(main())
