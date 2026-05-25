"""Lightweight configuration resolver for scripts and optional integrations."""
from __future__ import annotations

import os
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent.parent


def resolve_config_value(name: str, *, root: str | Path | None = None) -> str | None:
    """Resolve a config value from environment or `.streamlit/secrets.toml`.

    Environment variables win so operational overrides do not require editing
    Streamlit's local secrets file.
    """
    value = os.environ.get(name)
    if value:
        return value.strip()

    base = Path(root) if root is not None else ROOT
    secrets_path = base / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None
    try:
        payload = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    secret = payload.get(name)
    if secret is None:
        return None
    text = str(secret).strip()
    return text or None
