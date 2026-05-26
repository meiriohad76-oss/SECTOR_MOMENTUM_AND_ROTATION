from __future__ import annotations

import pandas as pd

from src.table_sort import (
    FULL_TABLE_SORT_DIRECTIONS,
    FULL_TABLE_SORT_FIELDS,
    normalize_full_table_sort,
    sort_full_table_frame,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "class": ["Technology", "Energy", "Financials", "Energy"],
            "state": ["HOLD", "STAGE_2_BULLISH", "BEARISH_STAGE_4", "WARNING"],
            "S_score": [0.2, 1.4, -1.5, 0.8],
            "F_score": [0.3, -0.2, -1.1, 1.2],
            "mom_12_1": [0.04, 0.18, -0.08, 0.02],
            "faber": [1, 1, 0, 1],
            "stage": [1, 2, 4, 2],
            "antonacci": [1, 1, 0, 0],
            "rrg_quadrant": ["Improving", "Leading", "Lagging", "Weakening"],
            "breadth_50d": [0.55, 0.72, 0.20, 0.61],
        },
        index=["XLK", "XLE", "XLF", "XOP"],
    )


def test_full_table_sort_options_cover_visible_matrix_columns_and_pillars():
    assert FULL_TABLE_SORT_DIRECTIONS == {"desc": "High to low", "asc": "Low to high"}
    assert {
        "ticker",
        "class",
        "state",
        "pillar_count",
        "S_score",
        "F_score",
        "mom_12_1",
        "faber",
        "stage",
        "antonacci",
        "rrg_quadrant",
        "breadth_50d",
    }.issubset(FULL_TABLE_SORT_FIELDS)


def test_sort_full_table_frame_sorts_by_strength_and_pillar_count():
    frame = _frame()

    assert list(sort_full_table_frame(frame, "S_score", "desc").index) == ["XLE", "XOP", "XLK", "XLF"]
    assert list(sort_full_table_frame(frame, "pillar_count", "desc").index) == ["XLE", "XLK", "XOP", "XLF"]


def test_sort_full_table_frame_supports_custom_ranked_fields():
    frame = _frame()

    assert list(sort_full_table_frame(frame, "state", "desc").index) == ["XLE", "XLK", "XOP", "XLF"]
    assert list(sort_full_table_frame(frame, "rrg_quadrant", "desc").index) == ["XLE", "XLK", "XOP", "XLF"]
    assert list(sort_full_table_frame(frame, "ticker", "asc").index) == ["XLE", "XLF", "XLK", "XOP"]


def test_normalize_full_table_sort_is_fail_closed_to_default():
    assert normalize_full_table_sort("S_score", "desc") == ("S_score", "desc")
    assert normalize_full_table_sort("missing", "sideways") == ("S_score", "desc")
