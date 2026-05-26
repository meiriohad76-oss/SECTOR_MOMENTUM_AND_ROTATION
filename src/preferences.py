"""View preference helpers for the dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from collections.abc import MutableMapping
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFERENCE_PROFILES_PATH = ROOT / "data" / "preference_profiles.json"
BLUF_MODES = ("Verdict", "Compact", "Hidden")
DENSITY_MODES = ("Comfortable", "Compact")
SPARKLINE_STYLES = ("Filled", "Line", "Off")
PALETTE_OPTIONS = ("Default", "Solarized", "Nord", "Mono")
STORE_VERSION = 1

DEFAULT_BLUF_MODE = "Verdict"
DEFAULT_DENSITY = "Comfortable"
DEFAULT_SPARKLINE_STYLE = "Filled"
DEFAULT_PALETTE = "Default"


@dataclass(frozen=True)
class PreferenceProfile:
    name: str
    bluf_mode: str
    view_density: str
    sparkline_style: str
    color_palette: str
    updated_at: str


@dataclass(frozen=True)
class PreferenceProfileSaveResult:
    ok: bool
    message: str
    profile: PreferenceProfile | None = None

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
        "--ticker-label": "#fff6df",
        "--ticker-label-shadow": "0 0 8px rgba(255, 246, 223, 0.18)",
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
        "--ticker-label": "#073642",
        "--ticker-label-shadow": "none",
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
        "--ticker-label": "#f8fbff",
        "--ticker-label-shadow": "0 0 8px rgba(248, 251, 255, 0.18)",
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
        "--ticker-label": "#202631",
        "--ticker-label-shadow": "none",
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
        "--ticker-label": "#ffffff",
        "--ticker-label-shadow": "0 0 8px rgba(255, 255, 255, 0.16)",
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
        "--ticker-label": "#111111",
        "--ticker-label-shadow": "none",
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


def load_preference_profiles(path: str | Path | None = None) -> list[PreferenceProfile]:
    store_path = _profile_store_path(path)
    if not store_path.exists():
        return []
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    items = payload.get("profiles", [])
    if not isinstance(items, list):
        return []

    profiles: list[PreferenceProfile] = []
    for item in items:
        profile = _preference_profile_from_payload(item)
        if profile is not None:
            profiles.append(profile)
    return sorted(profiles, key=lambda profile: profile.name.casefold())


def save_preference_profile(
    name: str,
    preferences: Mapping,
    path: str | Path | None = None,
    now: str | None = None,
) -> PreferenceProfileSaveResult:
    clean_name = _clean_profile_name(name)
    if clean_name is None:
        return PreferenceProfileSaveResult(False, "name is required")

    profile = PreferenceProfile(
        name=clean_name,
        bluf_mode=_normalize(preferences.get("bluf_mode"), BLUF_MODES, DEFAULT_BLUF_MODE),
        view_density=_normalize(preferences.get("view_density"), DENSITY_MODES, DEFAULT_DENSITY),
        sparkline_style=_normalize(
            preferences.get("sparkline_style"),
            SPARKLINE_STYLES,
            DEFAULT_SPARKLINE_STYLE,
        ),
        color_palette=_normalize(preferences.get("color_palette"), PALETTE_OPTIONS, DEFAULT_PALETTE),
        updated_at=now or _utc_now(),
    )
    existing = [item for item in load_preference_profiles(path) if item.name.casefold() != clean_name.casefold()]
    existing.append(profile)
    _write_preference_profiles(existing, path)
    return PreferenceProfileSaveResult(True, f"saved profile {clean_name}", profile)


def delete_preference_profile(name: str, path: str | Path | None = None) -> bool:
    clean_name = _clean_profile_name(name)
    if clean_name is None:
        return False
    profiles = load_preference_profiles(path)
    keep = [profile for profile in profiles if profile.name.casefold() != clean_name.casefold()]
    if len(keep) == len(profiles):
        return False
    _write_preference_profiles(keep, path)
    return True


def apply_preference_profile(session_state: MutableMapping, profile: PreferenceProfile) -> None:
    session_state["bluf_mode"] = profile.bluf_mode
    session_state["view_density"] = profile.view_density
    session_state["sparkline_style"] = profile.sparkline_style
    session_state["color_palette"] = profile.color_palette


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


def _preference_profile_from_payload(payload) -> PreferenceProfile | None:
    if not isinstance(payload, dict):
        return None
    name = _clean_profile_name(payload.get("name"))
    if name is None:
        return None
    return PreferenceProfile(
        name=name,
        bluf_mode=_normalize(payload.get("bluf_mode"), BLUF_MODES, DEFAULT_BLUF_MODE),
        view_density=_normalize(payload.get("view_density"), DENSITY_MODES, DEFAULT_DENSITY),
        sparkline_style=_normalize(payload.get("sparkline_style"), SPARKLINE_STYLES, DEFAULT_SPARKLINE_STYLE),
        color_palette=_normalize(payload.get("color_palette"), PALETTE_OPTIONS, DEFAULT_PALETTE),
        updated_at=str(payload.get("updated_at") or ""),
    )


def _write_preference_profiles(profiles: list[PreferenceProfile], path: str | Path | None) -> None:
    store_path = _profile_store_path(path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "profiles": [
            {
                "name": profile.name,
                "bluf_mode": profile.bluf_mode,
                "view_density": profile.view_density,
                "sparkline_style": profile.sparkline_style,
                "color_palette": profile.color_palette,
                "updated_at": profile.updated_at,
            }
            for profile in sorted(profiles, key=lambda item: item.name.casefold())
        ],
    }
    tmp_path = store_path.with_suffix(store_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(store_path)


def _clean_profile_name(name) -> str | None:
    cleaned = str(name or "").strip()
    return cleaned[:80] if cleaned else None


def _profile_store_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else DEFAULT_PREFERENCE_PROFILES_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
