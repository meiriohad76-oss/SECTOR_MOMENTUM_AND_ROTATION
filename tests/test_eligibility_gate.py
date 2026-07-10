"""Tests for Task 5 — eligibility → rank sequencing.

Acceptance criteria:
- No output row can be selected==True while in a non-eligible state.
- An EXIT instrument with a high raw score is excluded from selected and
  flagged in the ineligible_bucket.
- Dashboard snapshot payload can distinguish eligible vs ranked vs selected.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scoring import (
    ELIGIBLE_STATES,
    apply_eligibility_gate,
    DEFAULT_SCORING_CONFIG,
    COMPOSITE_WEIGHTS,
    FLOW_VETO,
    BINARY_FILTER_COUNT,
    STATE_MACHINE_THRESHOLDS,
    PULLBACK_RISK_THRESHOLDS,
)


def _make_scored_df():
    """Minimal post-apply_state_machine fixture."""
    return pd.DataFrame(
        {
            "state": ["STAGE_2_BULLISH", "HOLD", "EXIT", "WARNING", "STAGE_2_BULLISH"],
            "class": ["US Sectors"] * 5,
            "S_score": [2.5, 1.0, 3.0, 0.5, 0.8],      # EXIT has highest raw score!
            "S_score_after_veto": [2.5, 1.0, 3.0, 0.5, 0.8],
            "veto": [False] * 5,
            "top_n_target": [4] * 5,
            "rank_in_class": [2.0, 3.0, 1.0, 4.0, 5.0],  # old ranks (to be overwritten)
            "selected": [True, True, True, False, False],   # old selection (to be overwritten)
            "flow_pillar_active": [True] * 5,
            "degraded_run": [False] * 5,
        },
        index=["XLK", "XLF", "XLE", "XLY", "XLB"],
    )


class TestEligibilityGate:
    def test_exit_instrument_with_highest_score_is_not_selected(self):
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        # XLE has state=EXIT and highest S_score=3.0 — must NOT be selected
        assert out.loc["XLE", "selected"] is False or not bool(out.loc["XLE", "selected"])

    def test_exit_instrument_is_in_ineligible_bucket(self):
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        assert bool(out.loc["XLE", "ineligible_bucket"]) is True
        assert bool(out.loc["XLE", "eligible"]) is False

    def test_warning_instrument_is_ineligible(self):
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        assert bool(out.loc["XLY", "eligible"]) is False

    def test_stage_2_bullish_and_hold_are_eligible(self):
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        assert bool(out.loc["XLK", "eligible"]) is True
        assert bool(out.loc["XLF", "eligible"]) is True

    def test_selected_only_from_eligible_states(self):
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        # Any row that is selected must be in an eligible state
        selected = out[out["selected"] == True]
        assert set(selected["state"].unique()).issubset(ELIGIBLE_STATES)

    def test_selected_is_never_true_for_ineligible_row(self):
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        ineligible = out[out["eligible"] == False]
        assert (ineligible["selected"] == True).sum() == 0

    def test_ranking_is_only_among_eligible(self):
        """Eligible tickers should receive lower (better) rank numbers."""
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        eligible = out[out["eligible"] == True].sort_values("S_score_after_veto", ascending=False)
        # Top eligible by score must rank 1
        top_eligible = eligible.index[0]
        assert out.loc[top_eligible, "rank_in_class"] == pytest.approx(1.0)

    def test_ineligible_rank_is_nan(self):
        """Ineligible rows should have NaN rank (sorted after all eligible)."""
        df = _make_scored_df()
        out = apply_eligibility_gate(df)

        assert pd.isna(out.loc["XLE", "rank_in_class"])
        assert pd.isna(out.loc["XLY", "rank_in_class"])

    def test_eligible_states_override(self):
        """Passing a custom eligible_states set works correctly."""
        df = _make_scored_df()
        # Only STAGE_2_BULLISH is eligible; HOLD becomes ineligible
        out = apply_eligibility_gate(df, eligible_states={"STAGE_2_BULLISH"})

        assert bool(out.loc["XLF", "eligible"]) is False  # HOLD → ineligible
        assert bool(out.loc["XLK", "eligible"]) is True   # STAGE_2_BULLISH → eligible

    def test_eligible_states_constant_matches_expected_values(self):
        assert "STAGE_2_BULLISH" in ELIGIBLE_STATES
        assert "HOLD" in ELIGIBLE_STATES
        assert "EXIT" not in ELIGIBLE_STATES
        assert "WARNING" not in ELIGIBLE_STATES
        assert "BEARISH_STAGE_4" not in ELIGIBLE_STATES

    def test_requires_state_column(self):
        df = _make_scored_df().drop(columns=["state"])
        with pytest.raises(ValueError, match="state"):
            apply_eligibility_gate(df)

    def test_requires_class_column(self):
        df = _make_scored_df().drop(columns=["class"])
        with pytest.raises(ValueError, match="class"):
            apply_eligibility_gate(df)

    def test_multi_class_eligibility_is_per_class(self):
        """Each class is ranked independently among its eligible members."""
        df = pd.DataFrame(
            {
                "state": ["EXIT", "STAGE_2_BULLISH", "EXIT", "HOLD"],
                "class": ["US Sectors", "US Sectors", "Countries", "Countries"],
                "S_score": [5.0, 1.0, 2.0, 3.0],
                "S_score_after_veto": [5.0, 1.0, 2.0, 3.0],
                "veto": [False] * 4,
                "top_n_target": [2] * 4,
                "rank_in_class": [1.0, 2.0, 1.0, 2.0],
                "selected": [True, True, True, True],
                "flow_pillar_active": [True] * 4,
                "degraded_run": [False] * 4,
            },
            index=["XLK", "XLF", "EWJ", "EWC"],
        )
        out = apply_eligibility_gate(df)

        # XLK (EXIT) must not be selected even in US Sectors
        assert not bool(out.loc["XLK", "selected"])
        # XLF (STAGE_2_BULLISH) must be selected in US Sectors
        assert bool(out.loc["XLF", "selected"])
        # EWJ (EXIT) must not be selected in Countries
        assert not bool(out.loc["EWJ", "selected"])
        # EWC (HOLD) must be selected in Countries
        assert bool(out.loc["EWC", "selected"])
