from __future__ import annotations

from src import preferences


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    stripped = value.strip().lstrip("#")
    return (
        int(stripped[0:2], 16) / 255,
        int(stripped[2:4], 16) / 255,
        int(stripped[4:6], 16) / 255,
    )


def _relative_luminance(value: str) -> float:
    def channel(component: float) -> float:
        if component <= 0.03928:
            return component / 12.92
        return ((component + 0.055) / 1.055) ** 2.4

    red, green, blue = (_hex_to_rgb(value))
    return (0.2126 * channel(red)) + (0.7152 * channel(green)) + (0.0722 * channel(blue))


def _contrast_ratio(foreground: str, background: str) -> float:
    lum_a = _relative_luminance(foreground)
    lum_b = _relative_luminance(background)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def _css_tokens(css: str) -> dict[str, str]:
    tokens = {}
    for line in css.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            name, value = stripped.rstrip(";").split(": ", 1)
            tokens[name] = value
    return tokens


def test_initialize_preferences_sets_defaults():
    session = {}

    preferences.initialize_preferences(session)

    assert session["bluf_mode"] == "Verdict"
    assert session["view_density"] == "Comfortable"
    assert session["sparkline_style"] == "Filled"
    assert session["color_palette"] == "Default"


def test_initialize_preferences_normalizes_invalid_values():
    session = {
        "bluf_mode": "NOPE",
        "view_density": "Dense",
        "sparkline_style": "Bars",
        "color_palette": "Sepia",
    }

    preferences.initialize_preferences(session)

    assert session["bluf_mode"] == "Verdict"
    assert session["view_density"] == "Comfortable"
    assert session["sparkline_style"] == "Filled"
    assert session["color_palette"] == "Default"


def test_density_class_only_marks_compact_density():
    assert preferences.density_class("Compact") == "density-compact"
    assert preferences.density_class("Comfortable") == "density-comfortable"


def test_bluf_helpers_report_modes():
    assert preferences.should_render_bluf("Hidden") is False
    assert preferences.should_render_bluf("Compact") is True
    assert preferences.is_compact_bluf("Compact") is True
    assert preferences.is_compact_bluf("Verdict") is False


def test_sparkline_mode_lowercases_valid_style():
    assert preferences.sparkline_mode("Line") == "line"
    assert preferences.sparkline_mode("Off") == "off"
    assert preferences.sparkline_mode("unknown") == "filled"


def test_palette_key_normalizes_palette_names():
    assert preferences.palette_key("Solarized") == "solarized"
    assert preferences.palette_key("Nord") == "nord"
    assert preferences.palette_key("Mono") == "mono"
    assert preferences.palette_key("unknown") == "default"


def test_palette_css_variables_renders_server_side_tokens():
    css = preferences.palette_css_variables("Solarized", "dark")

    assert css.startswith("\n:root {")
    assert "  --bg: #002b36;" in css
    assert "  --muted-2:" in css
    assert "data-palette" not in css


def test_palette_css_variables_handles_default_and_light_theme():
    assert preferences.palette_css_variables("Default", "dark") == ""
    assert preferences.palette_css_variables("Sepia", "light") == ""

    css = preferences.palette_css_variables("Solarized", "light")

    assert "  --bg: #fdf6e3;" in css
    assert "  --muted-2:" in css


def test_solarized_muted_tokens_clear_small_text_contrast_floor():
    for theme in ("dark", "light"):
        tokens = _css_tokens(preferences.palette_css_variables("Solarized", theme))
        for text_token in ("--muted", "--muted-2"):
            for surface_token in ("--bg", "--panel"):
                assert _contrast_ratio(tokens[text_token], tokens[surface_token]) >= 4.5
