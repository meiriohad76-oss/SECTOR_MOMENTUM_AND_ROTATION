from __future__ import annotations

from src import navigation


def test_initial_drill_ticker_uses_valid_query_param():
    session = {}
    query = {"ticker": ["xlk"]}

    selected = navigation.initialize_drill_ticker(session, query, ["XLF", "XLK"], default="XLF")

    assert selected == "XLK"
    assert session["drill_ticker"] == "XLK"


def test_initial_drill_ticker_falls_back_when_query_param_unknown():
    session = {}
    query = {"ticker": "NOPE"}

    selected = navigation.initialize_drill_ticker(session, query, ["XLF", "XLK"], default="XLF")

    assert selected == "XLF"
    assert session["drill_ticker"] == "XLF"


def test_initial_drill_ticker_keeps_existing_valid_session_value_without_query_param():
    session = {"drill_ticker": "XLK"}
    query = {}

    selected = navigation.initialize_drill_ticker(session, query, ["XLF", "XLK"], default="XLF")

    assert selected == "XLK"
    assert session["drill_ticker"] == "XLK"


def test_select_drill_ticker_updates_session_and_query_params():
    session = {"drill_ticker": "XLF"}
    query = {}

    changed = navigation.select_drill_ticker(session, query, "xlk", ["XLF", "XLK"])

    assert changed is True
    assert session["drill_ticker"] == "XLK"
    assert query["ticker"] == "XLK"


def test_select_drill_ticker_accepts_current_value_without_reporting_change():
    session = {"drill_ticker": "XLK"}
    query = {}

    changed = navigation.select_drill_ticker(session, query, "XLK", ["XLF", "XLK"])

    assert changed is False
    assert session["drill_ticker"] == "XLK"
    assert query["ticker"] == "XLK"


def test_select_drill_ticker_rejects_malformed_or_unknown_values():
    session = {"drill_ticker": "XLF"}
    query = {"ticker": "XLF"}

    changed = navigation.select_drill_ticker(session, query, "not a ticker", ["XLF", "XLK"])

    assert changed is False
    assert session["drill_ticker"] == "XLF"
    assert query["ticker"] == "XLF"
