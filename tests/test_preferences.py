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
    assert "  --ticker-label:" in css
    assert "  --ticker-label-shadow:" in css
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


def test_preference_profiles_are_saved_normalized_and_overwritten(tmp_path):
    store_path = tmp_path / "preference_profiles.json"

    result = preferences.save_preference_profile(
        " Desk ",
        {
            "bluf_mode": "compact",
            "view_density": "compact",
            "sparkline_style": "line",
            "color_palette": "nord",
        },
        path=store_path,
        now="2026-05-22T10:00:00Z",
    )
    overwritten = preferences.save_preference_profile(
        "desk",
        {
            "bluf_mode": "invalid",
            "view_density": "Comfortable",
            "sparkline_style": "Off",
            "color_palette": "Mono",
        },
        path=store_path,
        now="2026-05-22T11:00:00Z",
    )

    profiles = preferences.load_preference_profiles(store_path)
    assert result.ok is True
    assert overwritten.ok is True
    assert len(profiles) == 1
    assert profiles[0].name == "desk"
    assert profiles[0].bluf_mode == "Verdict"
    assert profiles[0].view_density == "Comfortable"
    assert profiles[0].sparkline_style == "Off"
    assert profiles[0].color_palette == "Mono"
    assert profiles[0].updated_at == "2026-05-22T11:00:00Z"


def test_preference_profiles_apply_and_delete_by_name(tmp_path):
    store_path = tmp_path / "preference_profiles.json"
    preferences.save_preference_profile(
        "Review",
        {
            "bluf_mode": "Hidden",
            "view_density": "Compact",
            "sparkline_style": "Off",
            "color_palette": "Solarized",
        },
        path=store_path,
        now="2026-05-22T10:00:00Z",
    )
    profile = preferences.load_preference_profiles(store_path)[0]
    session = {}

    preferences.apply_preference_profile(session, profile)
    deleted = preferences.delete_preference_profile("review", path=store_path)

    assert session == {
        "bluf_mode": "Hidden",
        "view_density": "Compact",
        "sparkline_style": "Off",
        "color_palette": "Solarized",
    }
    assert deleted is True
    assert preferences.load_preference_profiles(store_path) == []


def test_preference_profile_store_handles_missing_corrupt_and_invalid_inputs(tmp_path):
    store_path = tmp_path / "preference_profiles.json"
    assert preferences.load_preference_profiles(store_path) == []

    store_path.write_text("{bad json", encoding="utf-8")
    assert preferences.load_preference_profiles(store_path) == []

    no_name = preferences.save_preference_profile("", {"bluf_mode": "Hidden"}, path=store_path)
    assert no_name.ok is False
    assert preferences.delete_preference_profile("", path=store_path) is False


def test_preference_profile_path_is_ignored_by_git_and_docker_contexts():
    gitignore = preferences.ROOT.joinpath(".gitignore").read_text(encoding="utf-8")
    dockerignore = preferences.ROOT.joinpath(".dockerignore").read_text(encoding="utf-8")

    assert "data/preference_profiles.json" in gitignore
    assert "data/preference_profiles.json.tmp" in gitignore
    assert "data/preference_profiles.json" in dockerignore
    assert "data/preference_profiles.json.tmp" in dockerignore
