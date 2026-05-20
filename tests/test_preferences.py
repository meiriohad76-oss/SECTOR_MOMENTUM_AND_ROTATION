from __future__ import annotations

from src import preferences


def test_initialize_preferences_sets_defaults():
    session = {}

    preferences.initialize_preferences(session)

    assert session["bluf_mode"] == "Verdict"
    assert session["view_density"] == "Comfortable"
    assert session["sparkline_style"] == "Filled"


def test_initialize_preferences_normalizes_invalid_values():
    session = {
        "bluf_mode": "NOPE",
        "view_density": "Dense",
        "sparkline_style": "Bars",
    }

    preferences.initialize_preferences(session)

    assert session["bluf_mode"] == "Verdict"
    assert session["view_density"] == "Comfortable"
    assert session["sparkline_style"] == "Filled"


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
