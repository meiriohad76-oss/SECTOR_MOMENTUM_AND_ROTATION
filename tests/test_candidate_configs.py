"""Tests for Tasks 3, 4, and 6 candidate ScoringConfig factories.

These tests verify:
  - Weight sums for all three candidate configs
  - Task 4: flow weight is actually reduced
  - Task 6: RRG removed from EXIT and WARNING gates; RS threshold raised
  - decide_state() behavioural changes under the tightened config vs DEFAULT

IMPORTANT: None of these tests change DEFAULT_SCORING_CONFIG or live behaviour.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.scoring import (
    DEFAULT_SCORING_CONFIG,
    make_flow_demoted_candidate_config,
    make_four_pillar_candidate_config,
    make_tightened_gate_candidate_config,
    decide_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _healthy_row(**overrides) -> pd.Series:
    """Return a row representing a healthy Stage-2 sector.

    All gate conditions are green by default; override individual fields to
    trigger specific gates.
    """
    base = {
        "stage": 2,
        "above_30wma": True,
        "ma_slope_pos": True,
        "mansfield_rs": 3.0,       # well above both 0.0 and -5.0 thresholds
        "antonacci": 1,
        "rrg_quadrant": "Leading",
        "breadth_50d": 0.70,
        "cmf21": 0.10,
        "return_5d": 0.02,
        "return_1d": 0.001,
        "return_2d": 0.001,
        "rvol": 1.0,
        "etf_flow_5d_pct": 1.0,
        "block_up_ratio": 0.85,
        "obv_divergence": False,
        "dist_days_25": 1,
    }
    base.update(overrides)
    return pd.Series(base)


# ---------------------------------------------------------------------------
# Task 3: Four-pillar candidate config
# ---------------------------------------------------------------------------


def test_four_pillar_weights_sum_to_one():
    cfg = make_four_pillar_candidate_config()
    total = sum(cfg.composite_weights.values())
    assert abs(total - 1.0) < 1e-9, f"Weights do not sum to 1.0: {total}"


def test_four_pillar_default_pillar_values():
    cfg = make_four_pillar_candidate_config()
    w = cfg.composite_weights
    # trend pillar: 80/20 split of 0.25
    assert abs(w["mom_12_1_z"] - 0.20) < 1e-9
    assert abs(w["binary_filters"] - 0.05) < 1e-9
    # RS pillar: 50/50 split of 0.25
    assert abs(w["mansfield_rs_z"] - 0.125) < 1e-9
    assert abs(w["rs_ratio_z"] - 0.125) < 1e-9
    # flow pillar: full 0.25
    assert abs(w["provider_flow_z"] - 0.25) < 1e-9
    # confirmation pillar: 80/20 split of 0.25
    assert abs(w["rs_momentum_z"] - 0.20) < 1e-9
    assert abs(w["cycle_tilt"] - 0.05) < 1e-9


def test_four_pillar_custom_weights_sum_to_one():
    cfg = make_four_pillar_candidate_config(
        trend_weight=0.30,
        rs_weight=0.20,
        flow_weight=0.20,
        confirmation_weight=0.30,
    )
    total = sum(cfg.composite_weights.values())
    assert abs(total - 1.0) < 1e-9, f"Custom weights do not sum to 1.0: {total}"


def test_four_pillar_does_not_change_default_config():
    # Calling the factory must not mutate DEFAULT_SCORING_CONFIG.
    before = dict(DEFAULT_SCORING_CONFIG.composite_weights)
    make_four_pillar_candidate_config()
    after = dict(DEFAULT_SCORING_CONFIG.composite_weights)
    assert before == after, "DEFAULT_SCORING_CONFIG was mutated by make_four_pillar_candidate_config()"


def test_four_pillar_state_machine_unchanged():
    cfg = make_four_pillar_candidate_config()
    assert cfg.state_machine_thresholds == DEFAULT_SCORING_CONFIG.state_machine_thresholds


# ---------------------------------------------------------------------------
# Task 4: Flow-demoted candidate config
# ---------------------------------------------------------------------------


def test_flow_demoted_weights_sum_to_one():
    cfg = make_flow_demoted_candidate_config()
    total = sum(cfg.composite_weights.values())
    assert abs(total - 1.0) < 1e-9, f"Flow-demoted weights do not sum to 1.0: {total}"


def test_flow_demoted_flow_weight_is_reduced():
    default_flow = DEFAULT_SCORING_CONFIG.composite_weights.get("provider_flow_z", 0.0)
    cfg = make_flow_demoted_candidate_config(flow_pillar_weight=0.10)
    assert cfg.composite_weights["provider_flow_z"] == pytest.approx(0.10)
    assert cfg.composite_weights["provider_flow_z"] < default_flow


def test_flow_demoted_non_flow_weights_scaled_up():
    cfg = make_flow_demoted_candidate_config(flow_pillar_weight=0.10)
    default_mom = DEFAULT_SCORING_CONFIG.composite_weights["mom_12_1_z"]
    assert cfg.composite_weights["mom_12_1_z"] > default_mom


def test_flow_demoted_graded_veto_config():
    cfg = make_flow_demoted_candidate_config(
        graded_penalty_threshold_z=-1.5,
        graded_penalty_max_deduction=0.20,
    )
    fv = cfg.flow_veto
    assert fv["threshold_z"] == pytest.approx(-1.5)
    assert fv["graded"] is True
    assert fv["graded_penalty_max_deduction"] == pytest.approx(0.20)
    assert fv["replacement_score"] is None


def test_flow_demoted_does_not_change_default_config():
    before_weights = dict(DEFAULT_SCORING_CONFIG.composite_weights)
    before_veto = dict(DEFAULT_SCORING_CONFIG.flow_veto)
    make_flow_demoted_candidate_config()
    assert DEFAULT_SCORING_CONFIG.composite_weights == before_weights
    assert DEFAULT_SCORING_CONFIG.flow_veto == before_veto


# ---------------------------------------------------------------------------
# Task 6: Tightened gate candidate config
# ---------------------------------------------------------------------------


def test_tightened_gate_removes_rrg_from_exit():
    cfg = make_tightened_gate_candidate_config()
    assert "rrg_quadrant_eq" not in cfg.state_machine_thresholds["exit"]


def test_tightened_gate_removes_rrg_from_warning():
    cfg = make_tightened_gate_candidate_config()
    assert "rrg_quadrant_eq" not in cfg.state_machine_thresholds["warning"]


def test_tightened_gate_rs_threshold_raised():
    cfg = make_tightened_gate_candidate_config(mansfield_rs_exit_lt=-5.0)
    assert cfg.state_machine_thresholds["exit"]["mansfield_rs_lt"] == pytest.approx(-5.0)


def test_tightened_gate_require_price_break_documented():
    cfg = make_tightened_gate_candidate_config(require_price_break_for_exit=True)
    assert cfg.state_machine_thresholds["exit"].get("require_above_30wma_false_for_rs_exit") is True


def test_tightened_gate_does_not_change_default_config():
    before = {k: dict(v) for k, v in DEFAULT_SCORING_CONFIG.state_machine_thresholds.items()}
    make_tightened_gate_candidate_config()
    after = {k: dict(v) for k, v in DEFAULT_SCORING_CONFIG.state_machine_thresholds.items()}
    assert before == after, "DEFAULT_SCORING_CONFIG state_machine_thresholds was mutated"


def test_tightened_gate_bearish_gate_unchanged():
    cfg = make_tightened_gate_candidate_config()
    assert cfg.state_machine_thresholds["bearish_stage_4"] == \
        DEFAULT_SCORING_CONFIG.state_machine_thresholds["bearish_stage_4"]


# ---------------------------------------------------------------------------
# decide_state() behavioural tests with tightened config
# ---------------------------------------------------------------------------


def test_decide_state_with_tightened_config_keeps_weakening_rrg_out_of_warning():
    """Weakening RRG + otherwise healthy indicators must NOT be forced to WARNING
    when using the tightened config (rrg_quadrant_eq removed from warning gate).
    """
    cfg = make_tightened_gate_candidate_config()
    row = _healthy_row(rrg_quadrant="Weakening")
    state = decide_state(row, config=cfg)
    assert state != "WARNING", (
        f"Expected not WARNING under tightened config with Weakening RRG, got {state!r}"
    )


def test_decide_state_with_tightened_config_rs_minus_three_does_not_exit():
    """mansfield_rs=-3.0 is above the new -5.0 threshold; should NOT trigger EXIT
    under tightened config (provided other gates pass).
    """
    cfg = make_tightened_gate_candidate_config(mansfield_rs_exit_lt=-5.0)
    row = _healthy_row(mansfield_rs=-3.0, above_30wma=True)
    state = decide_state(row, config=cfg)
    assert state != "EXIT", (
        f"Expected not EXIT under tightened config with mansfield_rs=-3.0, got {state!r}"
    )


def test_default_config_still_exits_on_rs_minus_three():
    """Regression guard: mansfield_rs=-3.0 IS below the default 0.0 threshold,
    so DEFAULT_SCORING_CONFIG must still assign EXIT.
    """
    row = _healthy_row(mansfield_rs=-3.0, above_30wma=True)
    state = decide_state(row, config=DEFAULT_SCORING_CONFIG)
    assert state == "EXIT", (
        f"Expected EXIT under DEFAULT_SCORING_CONFIG with mansfield_rs=-3.0, got {state!r}"
    )


def test_decide_state_with_tightened_config_lagging_rrg_does_not_exit():
    """RRG 'Lagging' must NOT force EXIT under tightened config."""
    cfg = make_tightened_gate_candidate_config()
    row = _healthy_row(rrg_quadrant="Lagging", mansfield_rs=2.0, above_30wma=True)
    state = decide_state(row, config=cfg)
    assert state != "EXIT", (
        f"Expected not EXIT under tightened config with Lagging RRG, got {state!r}"
    )


def test_default_config_lagging_rrg_exits():
    """Regression guard: RRG 'Lagging' DOES force EXIT under DEFAULT_SCORING_CONFIG."""
    row = _healthy_row(rrg_quadrant="Lagging", mansfield_rs=2.0, above_30wma=True)
    state = decide_state(row, config=DEFAULT_SCORING_CONFIG)
    assert state == "EXIT", (
        f"Expected EXIT under DEFAULT_SCORING_CONFIG with Lagging RRG, got {state!r}"
    )


def test_default_config_weakening_rrg_warns():
    """Regression guard: RRG 'Weakening' DOES force WARNING under DEFAULT_SCORING_CONFIG."""
    row = _healthy_row(rrg_quadrant="Weakening")
    state = decide_state(row, config=DEFAULT_SCORING_CONFIG)
    assert state == "WARNING", (
        f"Expected WARNING under DEFAULT_SCORING_CONFIG with Weakening RRG, got {state!r}"
    )
