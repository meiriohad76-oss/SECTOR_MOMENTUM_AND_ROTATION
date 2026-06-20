"""Read-only custom universe analysis payload for the B-170 React migration."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .custom_universe import (
    CustomUniverseAnalysisRow,
    analyze_custom_universe,
)


def _serialize_row(row: CustomUniverseAnalysisRow) -> dict[str, Any]:
    return {
        "ticker":        row.ticker,
        "custom_rank":   row.custom_rank,
        "state":         row.state,
        "asset_class":   row.asset_class,
        "s_score":       row.s_score,
        "f_score":       row.f_score,
        "stage":         row.stage,
        "rrg_quadrant":  row.rrg_quadrant,
        "mom_12_1":      row.mom_12_1,
        "cmf21":         row.cmf21,
        "breadth_50d":   row.breadth_50d,
        "rank_in_class": row.rank_in_class,
        "selected":      row.selected,
        "veto":          row.veto,
        "missing":       row.missing,
        "missing_reason": row.missing_reason,
    }


def _snapshot_rows_to_df(snapshot_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert snapshot API rows to a DataFrame with column names expected by analyze_custom_universe."""
    if not snapshot_rows:
        return pd.DataFrame()

    df = pd.DataFrame(snapshot_rows)

    # Map API field names to the column names analyze_custom_universe expects
    rename = {
        "s_score":      "S_score",
        "f_score":      "F_score",
        "asset_class":  "class",
        "quadrant":     "rrg_quadrant",
        "momentum_pct": "mom_12_1",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "ticker" not in df.columns:
        return pd.DataFrame()

    df = df.drop_duplicates(subset=["ticker"])
    df = df.set_index("ticker")
    return df


def build_universe_analysis_payload(
    tickers: list[str],
    snapshot_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze a custom ticker list against the current snapshot rows."""
    if not tickers:
        return {
            "rows": [],
            "available_count": 0,
            "missing_count": 0,
            "class_counts": {},
            "state_counts": {},
            "action_tickers": {"exit": [], "warning": [], "bullish": []},
        }

    df = _snapshot_rows_to_df(snapshot_rows)

    if df.empty:
        # No snapshot data — all tickers are missing
        normalized = [t.strip().upper() for t in tickers if t]
        return {
            "rows": [
                {
                    "ticker": t,
                    "custom_rank": None,
                    "state": None,
                    "asset_class": None,
                    "s_score": None,
                    "f_score": None,
                    "stage": None,
                    "rrg_quadrant": None,
                    "mom_12_1": None,
                    "cmf21": None,
                    "breadth_50d": None,
                    "rank_in_class": None,
                    "selected": None,
                    "veto": None,
                    "missing": True,
                    "missing_reason": "no snapshot data",
                }
                for t in normalized
            ],
            "available_count": 0,
            "missing_count": len(normalized),
            "class_counts": {},
            "state_counts": {},
            "action_tickers": {"exit": [], "warning": [], "bullish": []},
        }

    analysis = analyze_custom_universe(tickers, df)

    return {
        "rows":           [_serialize_row(r) for r in analysis.rows],
        "available_count": len(analysis.available_tickers),
        "missing_count":   len(analysis.missing_tickers),
        "class_counts":    analysis.class_counts,
        "state_counts":    analysis.state_counts,
        "action_tickers":  analysis.action_tickers,
    }
