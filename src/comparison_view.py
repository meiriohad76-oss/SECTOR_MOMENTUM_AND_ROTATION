"""Helpers for side-by-side ticker comparison cards."""
from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


COMPARISON_LIMIT = 4


def _finite_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _fmt_signed(value: object) -> str:
    result = _finite_float(value)
    return "-" if result is None else f"{result:+.2f}"


def _fmt_percent(value: object) -> str:
    result = _finite_float(value)
    return "-" if result is None else f"{result * 100:+.1f}%"


def _add_unique(items: list[str], ticker: object, valid: set[str], limit: int) -> None:
    normalized = str(ticker or "").upper().strip()
    if normalized and normalized in valid and normalized not in items and len(items) < limit:
        items.append(normalized)


def comparison_default_tickers(
    scored: pd.DataFrame,
    current_ticker: str | None = None,
    limit: int = COMPARISON_LIMIT,
) -> list[str]:
    """Return a stable default comparison basket from current drill ticker and picks."""
    valid = {str(ticker).upper() for ticker in scored.index}
    defaults: list[str] = []
    _add_unique(defaults, current_ticker, valid, limit)

    selected = scored[scored.get("selected", pd.Series(False, index=scored.index)).astype(bool)].copy()
    if not selected.empty:
        selected = selected.sort_values(
            ["rank_in_class", "S_score"],
            ascending=[True, False],
            na_position="last",
        )
        for ticker in selected.index:
            _add_unique(defaults, ticker, valid, limit)

    if len(defaults) < limit and "S_score" in scored:
        for ticker in scored.sort_values("S_score", ascending=False, na_position="last").index:
            _add_unique(defaults, ticker, valid, limit)

    return defaults


def initialize_comparison_tickers(
    session_state: dict,
    scored: pd.DataFrame,
    current_ticker: str | None = None,
) -> None:
    """Seed comparison tickers only when the session key has never existed."""
    if "comparison_tickers" in session_state:
        return
    session_state["comparison_tickers"] = comparison_default_tickers(
        scored,
        current_ticker=current_ticker,
    )


def comparison_card_rows(
    scored: pd.DataFrame,
    tickers: Iterable[str],
    limit: int = COMPARISON_LIMIT,
) -> list[dict[str, str]]:
    """Return display-ready comparison rows for known tickers."""
    valid = {str(ticker).upper() for ticker in scored.index}
    selected: list[str] = []
    for ticker in tickers:
        _add_unique(selected, ticker, valid, limit)

    rows: list[dict[str, str]] = []
    for ticker in selected:
        row = scored.loc[ticker]
        rank = row.get("rank_in_class")
        rank_label = "-" if pd.isna(rank) else f"#{int(rank)}"
        rows.append(
            {
                "ticker": ticker,
                "state": str(row.get("state", "UNKNOWN")),
                "class": str(row.get("class", "-")),
                "s_score": _fmt_signed(row.get("S_score")),
                "f_score": _fmt_signed(row.get("F_score")),
                "momentum": _fmt_percent(row.get("mom_12_1")),
                "stage": str(row.get("stage", "-")),
                "rrg": str(row.get("rrg_quadrant", "-") or "-").upper(),
                "rank": rank_label,
                "selected": "SELECTED" if bool(row.get("selected", False)) else "WATCH",
                "veto": "VETO" if bool(row.get("veto", False)) else "OK",
            }
        )
    return rows
