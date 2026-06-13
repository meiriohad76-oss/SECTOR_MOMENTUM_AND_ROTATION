from __future__ import annotations

import pandas as pd

from src.comparison_view import (
    comparison_card_rows,
    comparison_default_tickers,
    initialize_comparison_tickers,
)


def test_comparison_default_tickers_starts_with_current_then_active_picks():
    scored = pd.DataFrame(
        {
            "selected": [True, True, False, True],
            "S_score": [0.2, 1.4, 2.0, 0.5],
            "rank_in_class": [2, 1, 1, 3],
        },
        index=["XLK", "XLF", "NVDA", "XLI"],
    )

    assert comparison_default_tickers(scored, current_ticker="NVDA") == ["NVDA", "XLF", "XLK", "XLI"]


def test_comparison_rows_limit_dedup_and_format_metrics():
    scored = pd.DataFrame(
        {
            "state": ["STAGE_2_BULLISH", "WARNING"],
            "class": ["US Sectors", "US Sectors"],
            "S_score": [1.234, -0.456],
            "F_score": [0.25, -0.5],
            "mom_12_1": [0.123, -0.045],
            "stage": [2, 4],
            "rrg_quadrant": ["Leading", "Lagging"],
            "rank_in_class": [1, 9],
            "selected": [True, False],
            "veto": [False, True],
        },
        index=["XLK", "XLF"],
    )

    rows = comparison_card_rows(scored, ["XLK", "XLK", "BAD", "XLF"])

    assert [row["ticker"] for row in rows] == ["XLK", "XLF"]
    assert rows[0]["s_score"] == "+1.23"
    assert rows[0]["momentum"] == "+12.3%"
    assert rows[1]["veto"] == "VETO"


def test_initialize_comparison_tickers_preserves_cleared_session_value():
    scored = pd.DataFrame(
        {"selected": [True], "S_score": [1.0], "rank_in_class": [1]},
        index=["XLK"],
    )
    session = {"comparison_tickers": []}

    initialize_comparison_tickers(session, scored, current_ticker="XLK")

    assert session["comparison_tickers"] == []


def test_comparison_rows_show_dash_for_missing_metrics():
    scored = pd.DataFrame(
        {
            "state": ["HOLD"],
            "class": ["US Sectors"],
            "S_score": [None],
            "F_score": [float("nan")],
            "mom_12_1": [None],
            "stage": [None],
            "rrg_quadrant": [None],
            "rank_in_class": [None],
            "selected": [False],
            "veto": [False],
        },
        index=["XLK"],
    )

    rows = comparison_card_rows(scored, ["XLK"])

    assert rows[0]["s_score"] == "-"
    assert rows[0]["f_score"] == "-"
    assert rows[0]["momentum"] == "-"
    assert rows[0]["rank"] == "-"
