"""Helpers for marking just-changed ticker states in the dashboard UI."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _date_key(value: object) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def transition_pulse_tickers(
    transitions: Iterable[dict],
    current_date: str | None = None,
) -> set[str]:
    """Return tickers whose latest transition date matches the current UTC date."""
    today = current_date or _today_utc()
    tickers: set[str] = set()
    for transition in transitions:
        if _date_key(transition.get("date")) != today:
            continue
        ticker = str(transition.get("ticker", "")).upper().strip()
        if ticker:
            tickers.add(ticker)
    return tickers


def transition_pulse_class(
    ticker: str,
    transitions: Iterable[dict],
    current_date: str | None = None,
) -> str:
    """Return the CSS pulse class when ``ticker`` changed state today."""
    normalized = str(ticker or "").upper().strip()
    if not normalized:
        return ""
    return "pulse-transition" if normalized in transition_pulse_tickers(transitions, current_date) else ""


def transition_row_pulse_class(
    transition: dict,
    current_date: str | None = None,
) -> str:
    """Return the CSS pulse class only when this transition row is from today."""
    today = current_date or _today_utc()
    ticker = str(transition.get("ticker", "")).upper().strip()
    if not ticker or _date_key(transition.get("date")) != today:
        return ""
    return "pulse-transition"
