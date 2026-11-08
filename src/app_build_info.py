"""Build identity reported by the API health endpoints."""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

# Keep in sync with web/package.json.
APP_VERSION = "0.1.0"
_REPO_ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def get_git_sha() -> str | None:
    """Short git SHA of the running checkout, or None when it cannot be read.

    SECTOR_GIT_SHA overrides the lookup (useful in deployments without a .git dir).
    """
    override = os.environ.get("SECTOR_GIT_SHA", "").strip()
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None
