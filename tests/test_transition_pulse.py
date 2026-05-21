from __future__ import annotations

from src.transition_pulse import (
    transition_pulse_class,
    transition_pulse_tickers,
    transition_row_pulse_class,
)


def test_transition_pulse_class_matches_today_transition_case_insensitive():
    transitions = [{"ticker": "XLK", "date": "2026-05-21", "to": "WARNING"}]

    assert transition_pulse_class("xlk", transitions, current_date="2026-05-21") == "pulse-transition"


def test_transition_pulse_class_ignores_stale_or_unknown_ticker():
    transitions = [{"ticker": "XLF", "date": "2026-05-20", "to": "EXIT"}]

    assert transition_pulse_class("XLF", transitions, current_date="2026-05-21") == ""
    assert transition_pulse_class("XLK", transitions, current_date="2026-05-21") == ""


def test_transition_pulse_tickers_accepts_iso_datetime_dates():
    transitions = [{"ticker": "XLK", "date": "2026-05-21T02:00:00+00:00"}]

    assert transition_pulse_tickers(transitions, current_date="2026-05-21") == {"XLK"}


def test_transition_row_pulse_class_checks_row_date_not_ticker_history():
    stale_row = {"ticker": "XLK", "date": "2026-05-20", "to": "EXIT"}
    today_row = {"ticker": "XLK", "date": "2026-05-21", "to": "WARNING"}

    assert transition_row_pulse_class(stale_row, current_date="2026-05-21") == ""
    assert transition_row_pulse_class(today_row, current_date="2026-05-21") == "pulse-transition"
