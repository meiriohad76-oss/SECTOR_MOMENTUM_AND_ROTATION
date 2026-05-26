"""Sorting helpers for the dashboard full 7-pillar matrix."""
from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


FULL_TABLE_SORT_FIELDS: Mapping[str, str] = {
    "S_score": "S score",
    "F_score": "F score",
    "pillar_count": "Pillars passed",
    "mom_12_1": "Momentum",
    "faber": "Faber trend",
    "stage": "Weinstein stage",
    "antonacci": "Dual momentum",
    "rrg_quadrant": "RRG quadrant",
    "breadth_50d": "Breadth",
    "state": "State",
    "class": "Class",
    "ticker": "Ticker",
}
FULL_TABLE_SORT_DIRECTIONS: Mapping[str, str] = {
    "desc": "High to low",
    "asc": "Low to high",
}
DEFAULT_FULL_TABLE_SORT = ("S_score", "desc")

_STATE_ORDER = {
    "STAGE_2_BULLISH": 0,
    "HOLD": 1,
    "STAGE_1_BASING": 2,
    "WARNING": 3,
    "EXIT": 4,
    "BEARISH_STAGE_4": 5,
}
_RRG_ORDER = {
    "Leading": 0,
    "Improving": 1,
    "Weakening": 2,
    "Lagging": 3,
}


def normalize_full_table_sort(field: object, direction: object) -> tuple[str, str]:
    """Return a supported full-table sort field and direction."""
    field_text = str(field or "")
    direction_text = str(direction or "")
    if field_text not in FULL_TABLE_SORT_FIELDS:
        field_text = DEFAULT_FULL_TABLE_SORT[0]
    if direction_text not in FULL_TABLE_SORT_DIRECTIONS:
        direction_text = DEFAULT_FULL_TABLE_SORT[1]
    return field_text, direction_text


def _pillar_count(frame: pd.DataFrame) -> pd.Series:
    return pd.DataFrame(
        {
            "momentum": frame.get("mom_12_1", pd.Series(index=frame.index, dtype=float)).fillna(0) > 0,
            "faber": frame.get("faber", pd.Series(index=frame.index, dtype=float)).fillna(0) == 1,
            "stage": frame.get("stage", pd.Series(index=frame.index, dtype=float)).fillna(0) == 2,
            "antonacci": frame.get("antonacci", pd.Series(index=frame.index, dtype=float)).fillna(0) == 1,
            "rrg": frame.get("rrg_quadrant", pd.Series(index=frame.index, dtype=object)).isin(("Leading", "Improving")),
            "breadth": frame.get("breadth_50d", pd.Series(index=frame.index, dtype=float)).fillna(0) >= 0.5,
            "flow": frame.get("F_score", pd.Series(index=frame.index, dtype=float)).fillna(0) > 0,
        },
        index=frame.index,
    ).sum(axis=1)


def sort_full_table_frame(frame: pd.DataFrame, field: object, direction: object) -> pd.DataFrame:
    """Return a sorted copy of the scored dashboard frame."""
    sort_field, sort_direction = normalize_full_table_sort(field, direction)
    ascending = sort_direction == "asc"

    if frame.empty:
        return frame.copy()

    if sort_field == "ticker":
        return frame.sort_index(ascending=ascending)

    sortable = frame.copy()
    if sort_field == "pillar_count":
        sortable["_sort_value"] = _pillar_count(sortable)
    elif sort_field == "state":
        sortable["_sort_value"] = sortable["state"].map(_STATE_ORDER).fillna(99)
        ascending = sort_direction == "desc"
    elif sort_field == "rrg_quadrant":
        sortable["_sort_value"] = sortable["rrg_quadrant"].map(_RRG_ORDER).fillna(99)
        ascending = sort_direction == "desc"
    elif sort_field in sortable.columns:
        sortable["_sort_value"] = sortable[sort_field]
    else:
        sortable["_sort_value"] = sortable["S_score"]

    sorted_frame = sortable.sort_values(
        ["_sort_value", "S_score"],
        ascending=[ascending, False],
        na_position="last",
        kind="mergesort",
    )
    return sorted_frame.drop(columns=["_sort_value"])
