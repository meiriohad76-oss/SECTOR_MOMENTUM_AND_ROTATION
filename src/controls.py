"""Small state helpers for dashboard controls."""
from __future__ import annotations

from collections.abc import MutableMapping


def toggle_theme(session_state: MutableMapping) -> str:
    current = session_state.get("theme")
    next_theme = "light" if current == "dark" else "dark"
    session_state["theme"] = next_theme
    return next_theme


def refresh_market_data(cache) -> bool:
    cache.clear()
    return True
