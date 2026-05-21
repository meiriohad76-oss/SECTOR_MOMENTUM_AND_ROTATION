"""View preference helpers for the dashboard."""
from __future__ import annotations

from collections.abc import MutableMapping


BLUF_MODES = ("Verdict", "Compact", "Hidden")
DENSITY_MODES = ("Comfortable", "Compact")
SPARKLINE_STYLES = ("Filled", "Line", "Off")
PALETTE_OPTIONS = ("Default", "Solarized", "Nord", "Mono")

DEFAULT_BLUF_MODE = "Verdict"
DEFAULT_DENSITY = "Comfortable"
DEFAULT_SPARKLINE_STYLE = "Filled"
DEFAULT_PALETTE = "Default"

_PALETTE_TOKENS = {
    ("solarized", "dark"): {
        "--bg": "#002b36",
        "--bg-elev": "#073642",
        "--panel": "#073642",
        "--panel-2": "#0b3a46",
        "--panel-hover": "#0f4654",
        "--border": "#164c58",
        "--border-strong": "#2aa198",
        "--fg": "#eee8d5",
        "--fg-dim": "#93a1a1",
        "--muted": "#93a1a1",
        "--muted-2": "#a7b6b6",
        "--accent": "#268bd2",
        "--accent-dim": "rgba(38, 139, 210, 0.20)",
        "--green": "#859900",
        "--red": "#dc322f",
        "--amber": "#b58900",
        "--blue": "#268bd2",
    },
    ("solarized", "light"): {
        "--bg": "#fdf6e3",
        "--bg-elev": "#fffaf0",
        "--panel": "#eee8d5",
        "--panel-2": "#f6efd9",
        "--panel-hover": "#e6dfc7",
        "--border": "#d8cfb3",
        "--border-strong": "#b8aa88",
        "--fg": "#073642",
        "--fg-dim": "#586e75",
        "--muted": "#4f6268",
        "--muted-2": "#46575d",
        "--accent": "#268bd2",
        "--accent-dim": "rgba(38, 139, 210, 0.14)",
        "--green": "#859900",
        "--red": "#dc322f",
        "--amber": "#b58900",
        "--blue": "#268bd2",
    },
    ("nord", "dark"): {
        "--bg": "#2e3440",
        "--bg-elev": "#343b49",
        "--panel": "#3b4252",
        "--panel-2": "#434c5e",
        "--panel-hover": "#4c566a",
        "--border": "#4c566a",
        "--border-strong": "#5e81ac",
        "--fg": "#eceff4",
        "--fg-dim": "#d8dee9",
        "--muted": "#aeb8c8",
        "--muted-2": "#8792a2",
        "--accent": "#88c0d0",
        "--accent-dim": "rgba(136, 192, 208, 0.20)",
        "--green": "#a3be8c",
        "--red": "#bf616a",
        "--amber": "#ebcb8b",
        "--blue": "#81a1c1",
    },
    ("nord", "light"): {
        "--bg": "#eceff4",
        "--bg-elev": "#f8f9fb",
        "--panel": "#ffffff",
        "--panel-2": "#e5e9f0",
        "--panel-hover": "#d8dee9",
        "--border": "#c8d0dc",
        "--border-strong": "#aeb8c8",
        "--fg": "#2e3440",
        "--fg-dim": "#3b4252",
        "--muted": "#5f6b7a",
        "--muted-2": "#7d8796",
        "--accent": "#5e81ac",
        "--accent-dim": "rgba(94, 129, 172, 0.14)",
        "--green": "#5e8f4e",
        "--red": "#bf616a",
        "--amber": "#b48a3c",
        "--blue": "#5e81ac",
    },
    ("mono", "dark"): {
        "--bg": "#080808",
        "--bg-elev": "#101010",
        "--panel": "#171717",
        "--panel-2": "#202020",
        "--panel-hover": "#2a2a2a",
        "--border": "#303030",
        "--border-strong": "#4a4a4a",
        "--fg": "#f0f0f0",
        "--fg-dim": "#c9c9c9",
        "--muted": "#8f8f8f",
        "--muted-2": "#666666",
        "--accent": "#d0d0d0",
        "--accent-dim": "rgba(208, 208, 208, 0.16)",
    },
    ("mono", "light"): {
        "--bg": "#f7f7f7",
        "--bg-elev": "#ffffff",
        "--panel": "#ffffff",
        "--panel-2": "#eeeeee",
        "--panel-hover": "#e5e5e5",
        "--border": "#d0d0d0",
        "--border-strong": "#9a9a9a",
        "--fg": "#111111",
        "--fg-dim": "#333333",
        "--muted": "#666666",
        "--muted-2": "#8a8a8a",
        "--accent": "#111111",
        "--accent-dim": "rgba(17, 17, 17, 0.10)",
    },
}


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
    session_state["color_palette"] = _normalize(
        session_state.get("color_palette"),
        PALETTE_OPTIONS,
        DEFAULT_PALETTE,
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


def palette_key(value: str) -> str:
    return _normalize(value, PALETTE_OPTIONS, DEFAULT_PALETTE).lower()


def palette_css_variables(value: str, theme: str) -> str:
    palette = palette_key(value)
    if palette == "default":
        return ""
    theme_key = "light" if str(theme).strip().lower() == "light" else "dark"
    tokens = _PALETTE_TOKENS.get((palette, theme_key))
    if not tokens:
        return ""
    declarations = "\n".join(f"  {name}: {token_value};" for name, token_value in tokens.items())
    return f"\n:root {{\n{declarations}\n}}\n"
