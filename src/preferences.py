"""View preference helpers for the dashboard."""
from __future__ import annotations

from collections.abc import MutableMapping


BLUF_MODES = ("Verdict", "Compact", "Hidden")
DENSITY_MODES = ("Comfortable", "Compact")
SPARKLINE_STYLES = ("Filled", "Line", "Off")

DEFAULT_BLUF_MODE = "Verdict"
DEFAULT_DENSITY = "Comfortable"
DEFAULT_SPARKLINE_STYLE = "Filled"


def _normalize(value, allowed: tuple[str, ...], default: str) -> str:
    text = str(value).strip() if value is not None else ""
    for option in allowed:
        if text.lower() == option.lower():
            return option
    return default


def initialize_preferences(session_state: MutableMapping) -> None:
    session_state["bluf_mode"] = _normalize(session_state.get("bluf_mode"), BLUF_MODES, DEFAULT_BLUF_MODE)
    session_state["view_density"] = _normalize(session_state.get("view_density"), DENSITY_MODES, DEFAULT_DENSITY)
    session_state["sparkline_style"] = _normalize(
        session_state.get("sparkline_style"),
        SPARKLINE_STYLES,
        DEFAULT_SPARKLINE_STYLE,
    )


def density_class(value: str) -> str:
    density = _normalize(value, DENSITY_MODES, DEFAULT_DENSITY)
    return f"density-{density.lower()}"


def should_render_bluf(value: str) -> bool:
    return _normalize(value, BLUF_MODES, DEFAULT_BLUF_MODE) != "Hidden"


def is_compact_bluf(value: str) -> bool:
    return _normalize(value, BLUF_MODES, DEFAULT_BLUF_MODE) == "Compact"


def sparkline_mode(value: str) -> str:
    return _normalize(value, SPARKLINE_STYLES, DEFAULT_SPARKLINE_STYLE).lower()
