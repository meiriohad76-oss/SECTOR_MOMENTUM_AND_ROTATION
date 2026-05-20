"""Drill-down navigation helpers for Streamlit state/query params."""
from __future__ import annotations

import re
from collections.abc import MutableMapping, Sequence


_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_ticker_param(value) -> str | None:
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if _TICKER_RE.match(text) else None


def _valid_tickers(tickers: Sequence[str]) -> set[str]:
    return {str(ticker).upper() for ticker in tickers}


def initialize_drill_ticker(
    session_state: MutableMapping,
    query_params: MutableMapping,
    tickers: Sequence[str],
    default: str = "XLK",
) -> str:
    valid = _valid_tickers(tickers)
    current = normalize_ticker_param(session_state.get("drill_ticker"))
    requested = normalize_ticker_param(query_params.get("ticker"))
    fallback = normalize_ticker_param(default)
    selected = requested if requested in valid else current if current in valid else fallback
    if selected not in valid:
        selected = sorted(valid)[0] if valid else fallback
    session_state["drill_ticker"] = selected
    return selected


def select_drill_ticker(
    session_state: MutableMapping,
    query_params: MutableMapping,
    ticker,
    tickers: Sequence[str],
) -> bool:
    normalized = normalize_ticker_param(ticker)
    if normalized not in _valid_tickers(tickers):
        return False
    changed = session_state.get("drill_ticker") != normalized
    session_state["drill_ticker"] = normalized
    query_params["ticker"] = normalized
    return changed
