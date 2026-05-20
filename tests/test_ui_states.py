from __future__ import annotations

import pandas as pd

from src.ui_states import DEFENSIVE_BASKET, defensive_basket_rows, loading_skeleton_slots


def test_defensive_basket_order_is_tlt_gld_bil():
    assert DEFENSIVE_BASKET == ("TLT", "GLD", "BIL")


def test_defensive_basket_rows_use_scored_snapshot_when_available():
    scored = pd.DataFrame(
        {
            "state": ["HOLD", "STAGE_2_BULLISH", "STAGE_1_BASING"],
            "S_score": [0.25, 0.72, -0.05],
            "F_score": [0.10, 0.40, 0.00],
        },
        index=["BIL", "TLT", "GLD"],
    )

    rows = defensive_basket_rows(scored)

    assert [row["ticker"] for row in rows] == ["TLT", "GLD", "BIL"]
    assert rows[0]["state"] == "STAGE_2_BULLISH"
    assert rows[0]["s_score"] == 0.72
    assert rows[0]["available"] is True
    assert rows[1]["role"] == "Gold hedge"
    assert rows[2]["role"] == "Cash / T-bill proxy"


def test_defensive_basket_rows_mark_missing_ticker_as_pending():
    scored = pd.DataFrame(
        {"state": ["HOLD"], "S_score": [0.25], "F_score": [0.10]},
        index=["TLT"],
    )

    rows = defensive_basket_rows(scored)
    missing = [row for row in rows if row["ticker"] == "GLD"][0]

    assert missing["available"] is False
    assert missing["state"] == "DATA_PENDING"
    assert missing["s_score"] is None
    assert missing["f_score"] is None


def test_loading_skeleton_slots_clamps_to_non_negative_count():
    assert loading_skeleton_slots(3) == (0, 1, 2)
    assert loading_skeleton_slots(0) == ()
    assert loading_skeleton_slots(-2) == ()
