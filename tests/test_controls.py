from __future__ import annotations

from src import controls


class FakeCache:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


def test_toggle_theme_flips_dark_to_light():
    session = {"theme": "dark"}

    assert controls.toggle_theme(session) == "light"
    assert session["theme"] == "light"


def test_toggle_theme_flips_light_to_dark():
    session = {"theme": "light"}

    assert controls.toggle_theme(session) == "dark"
    assert session["theme"] == "dark"


def test_toggle_theme_defaults_unknown_theme_to_dark():
    session = {"theme": "solarized"}

    assert controls.toggle_theme(session) == "dark"
    assert session["theme"] == "dark"


def test_refresh_market_data_clears_cache():
    cache = FakeCache()

    assert controls.refresh_market_data(cache) is True
    assert cache.cleared is True
