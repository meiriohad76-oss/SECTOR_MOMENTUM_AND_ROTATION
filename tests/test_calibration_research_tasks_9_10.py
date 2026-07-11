"""Tests for Task 9 (rank-IC + walk-forward weight grid) and
Task 10 (weight perturbation robustness + state forward-return separation).

All tests use synthetic fixtures; no live data is required.
No live DEFAULT_SCORING_CONFIG change is made.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.calibration_research import (
    PILLAR_Z_COLUMNS,
    rank_ic_per_pillar,
    state_forward_return_separation,
    walk_forward_weight_grid,
    weight_perturbation_robustness,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

def _make_scored_df(n_instruments: int = 20, seed: int = 42) -> pd.DataFrame:
    """Synthetic scored_df with pillar z-scores + forward returns.

    Pillar mom_12_1_z is the strongest predictor of forward_return.
    provider_flow_z has low IC by design.
    """
    rng = np.random.default_rng(seed)
    idx = [f"T{i:03d}" for i in range(n_instruments)]
    mom = rng.standard_normal(n_instruments)
    forward_return = 0.6 * mom + 0.4 * rng.standard_normal(n_instruments)
    return pd.DataFrame(
        {
            "mom_12_1_z": mom,
            "mansfield_rs_z": 0.7 * mom + 0.3 * rng.standard_normal(n_instruments),
            "rs_ratio_z": 0.65 * mom + 0.35 * rng.standard_normal(n_instruments),
            "rs_momentum_z": 0.4 * mom + 0.6 * rng.standard_normal(n_instruments),
            "binary_filters_z": 0.3 * mom + 0.7 * rng.standard_normal(n_instruments),
            "breadth_50d_z": 0.5 * mom + 0.5 * rng.standard_normal(n_instruments),
            "provider_flow_z": rng.standard_normal(n_instruments),  # noise pillar
            "forward_return": forward_return,
            "S_score": mom + 0.2 * rng.standard_normal(n_instruments),
            "state": rng.choice(
                ["STAGE_2_BULLISH", "HOLD", "WARNING", "EXIT"], n_instruments
            ),
        },
        index=idx,
    )


def _make_multi_rebalance_df(n_rebalances: int = 5, n_per: int = 15, seed: int = 0) -> pd.DataFrame:
    """Multiple rebalance dates for walk-forward tests."""
    rng = np.random.default_rng(seed)
    parts = []
    for i in range(n_rebalances):
        idx = [f"T{j:03d}" for j in range(n_per)]
        mom = rng.standard_normal(n_per)
        df = pd.DataFrame(
            {
                "mom_12_1_z": mom,
                "mansfield_rs_z": 0.7 * mom + 0.3 * rng.standard_normal(n_per),
                "rs_ratio_z": 0.65 * mom + 0.35 * rng.standard_normal(n_per),
                "rs_momentum_z": 0.5 * mom + 0.5 * rng.standard_normal(n_per),
                "binary_filters_z": 0.3 * mom + 0.7 * rng.standard_normal(n_per),
                "breadth_50d_z": 0.5 * mom + 0.5 * rng.standard_normal(n_per),
                "provider_flow_z": rng.standard_normal(n_per),
                "forward_return": 0.6 * mom + 0.4 * rng.standard_normal(n_per),
                "rebalance_date": f"2024-0{i + 1}-01",
            },
            index=idx,
        )
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def _make_separation_df() -> pd.DataFrame:
    """Fixture with clear state ordering (BULLISH > HOLD > WARNING > EXIT)."""
    rng = np.random.default_rng(7)
    state_returns = {
        "STAGE_2_BULLISH": 0.08,
        "HOLD": 0.03,
        "WARNING": -0.02,
        "EXIT": -0.07,
        "BEARISH_STAGE_4": -0.12,
    }
    rows = []
    for state, mean in state_returns.items():
        for _ in range(20):
            rows.append({"state": state, "forward_return": mean + rng.normal(0, 0.02)})
    return pd.DataFrame(rows)


# ── Task 9: rank_ic_per_pillar ────────────────────────────────────────────────

class TestRankIcPerPillar:
    def test_returns_one_row_per_present_pillar(self):
        df = _make_scored_df()
        result = rank_ic_per_pillar(df)
        assert len(result) == len([c for c in PILLAR_Z_COLUMNS if c in df.columns])

    def test_columns_are_correct(self):
        df = _make_scored_df()
        result = rank_ic_per_pillar(df)
        assert set(result.columns) == {
            "pillar",
            "mean_ic",
            "ic_std",
            "ic_ir",
            "ic_t_stat",
            "n_rebalances",
            "valid_rebalances",
        }

    def test_mom_has_positive_ic_on_predictive_fixture(self):
        """mom_12_1_z is positively correlated with forward_return in the fixture."""
        df = _make_scored_df(n_instruments=50)
        result = rank_ic_per_pillar(df)
        mom_row = result[result["pillar"] == "mom_12_1_z"].iloc[0]
        assert mom_row["mean_ic"] > 0.0, "mom pillar should have positive IC"

    def test_noise_pillar_has_lower_ic_than_momentum(self):
        df = _make_scored_df(n_instruments=50)
        result = rank_ic_per_pillar(df)
        mom_ic = result.loc[result["pillar"] == "mom_12_1_z", "mean_ic"].iloc[0]
        flow_ic = result.loc[result["pillar"] == "provider_flow_z", "mean_ic"].iloc[0]
        assert mom_ic > flow_ic, "momentum pillar IC should exceed noise pillar IC"

    def test_multi_rebalance_valid_count(self):
        df = _make_multi_rebalance_df(n_rebalances=4)
        result = rank_ic_per_pillar(df)
        # Each rebalance has 15 instruments (> min_cross_section=5) → all 4 valid
        for _, row in result.iterrows():
            assert row["valid_rebalances"] == row["n_rebalances"], (
                f"All rebalances should be valid for {row['pillar']}"
            )

    def test_missing_forward_return_raises(self):
        df = _make_scored_df().drop(columns=["forward_return"])
        with pytest.raises(ValueError, match="forward_return"):
            rank_ic_per_pillar(df)

    def test_custom_pillar_columns_respected(self):
        df = _make_scored_df()
        result = rank_ic_per_pillar(df, pillar_columns=["mom_12_1_z", "breadth_50d_z"])
        assert list(result["pillar"]) == ["mom_12_1_z", "breadth_50d_z"]

    def test_pillar_columns_constant_in_module(self):
        """PILLAR_Z_COLUMNS is the fixed canonical set used across modules."""
        assert "mom_12_1_z" in PILLAR_Z_COLUMNS
        assert "provider_flow_z" in PILLAR_Z_COLUMNS
        assert len(PILLAR_Z_COLUMNS) == 7


# ── Task 9: walk_forward_weight_grid ─────────────────────────────────────────

class TestWalkForwardWeightGrid:
    def test_equal_weight_baseline_always_present(self):
        df = _make_scored_df()
        result = walk_forward_weight_grid([], df)
        assert "equal_weight" in result["label"].values

    def test_equal_weight_custom_label(self):
        df = _make_scored_df()
        result = walk_forward_weight_grid([], df, equal_weight_label="ew_benchmark")
        assert "ew_benchmark" in result["label"].values

    def test_columns_present(self):
        df = _make_scored_df()
        result = walk_forward_weight_grid([], df)
        assert set(result.columns) == {
            "label",
            "mean_ic",
            "ic_ir",
            "ic_t_stat",
            "valid_rebalances",
            "promotion_label",
            "weights",
        }

    def test_momentum_heavy_candidate_included(self):
        df = _make_scored_df(n_instruments=30)
        candidates = [
            {
                "label": "momentum_heavy",
                "weights": {"mom_12_1_z": 0.60, "mansfield_rs_z": 0.10,
                             "rs_ratio_z": 0.10, "breadth_50d_z": 0.10,
                             "provider_flow_z": 0.10},
            }
        ]
        result = walk_forward_weight_grid(candidates, df)
        labels = result["label"].tolist()
        assert "momentum_heavy" in labels
        assert "equal_weight" in labels

    def test_promotion_label_not_promoted_for_noise_pillar(self):
        """A single-pillar config built entirely of noise should be not_promoted."""
        rng = np.random.default_rng(99)
        n = 20
        noise_df = pd.DataFrame(
            {
                "provider_flow_z": rng.standard_normal(n),
                "forward_return": rng.standard_normal(n),  # unrelated
            },
            index=[f"T{i}" for i in range(n)],
        )
        candidates = [
            {
                "label": "pure_noise",
                "weights": {"provider_flow_z": 1.0},
            }
        ]
        result = walk_forward_weight_grid(candidates, noise_df, equal_weight_label="_skip")
        pure_noise = result[result["label"] == "pure_noise"].iloc[0]
        # With a single rebalance and noise, IC t-stat can't be >1 reliably —
        # either not_promoted or research_candidate (never candidate)
        assert pure_noise["promotion_label"] in ("not_promoted", "research_candidate")

    def test_missing_forward_return_raises(self):
        df = _make_scored_df().drop(columns=["forward_return"])
        with pytest.raises(ValueError, match="forward_return"):
            walk_forward_weight_grid([], df)

    def test_multi_rebalance_produces_valid_ic_t_stat(self):
        df = _make_multi_rebalance_df(n_rebalances=6)
        result = walk_forward_weight_grid([], df)
        ew_row = result[result["label"] == "equal_weight"].iloc[0]
        # With 6 rebalances we should have enough data for a finite t-stat
        assert not math.isnan(ew_row["ic_t_stat"]), "t-stat should be finite with 6 rebalances"


# ── Task 10a: weight_perturbation_robustness ──────────────────────────────────

class TestWeightPerturbationRobustness:
    def test_returns_required_keys(self):
        df = _make_scored_df(n_instruments=30)
        weights = {"mom_12_1_z": 0.40, "mansfield_rs_z": 0.20, "rs_ratio_z": 0.15,
                   "breadth_50d_z": 0.15, "provider_flow_z": 0.10}
        result = weight_perturbation_robustness(df, weights)
        for key in (
            "rank_correlations", "top_n_overlaps",
            "mean_rank_correlation", "min_rank_correlation",
            "mean_top_n_overlap", "min_top_n_overlap",
            "n_perturbations", "top_n",
        ):
            assert key in result, f"Missing key: {key}"

    def test_produces_perturbations(self):
        df = _make_scored_df(n_instruments=30)
        weights = {"mom_12_1_z": 0.50, "mansfield_rs_z": 0.25, "breadth_50d_z": 0.25}
        result = weight_perturbation_robustness(df, weights, perturbation_pp=0.10, step_pp=0.05)
        assert result["n_perturbations"] > 0

    def test_highly_correlated_rankings_produce_high_mean_rank_correlation(self):
        """Fixture where all pillars track the same signal → rank barely moves."""
        rng = np.random.default_rng(5)
        n = 30
        signal = rng.standard_normal(n)
        df = pd.DataFrame(
            {
                "mom_12_1_z": signal + 0.1 * rng.standard_normal(n),
                "mansfield_rs_z": signal + 0.1 * rng.standard_normal(n),
                "breadth_50d_z": signal + 0.1 * rng.standard_normal(n),
                "S_score": signal,
            },
            index=[f"T{i}" for i in range(n)],
        )
        weights = {"mom_12_1_z": 0.5, "mansfield_rs_z": 0.3, "breadth_50d_z": 0.2}
        result = weight_perturbation_robustness(df, weights, perturbation_pp=0.10)
        assert result["mean_rank_correlation"] > 0.90, (
            "Correlated pillars should produce stable rank under perturbation"
        )

    def test_top_n_default_is_10(self):
        df = _make_scored_df()
        weights = {"mom_12_1_z": 0.5, "breadth_50d_z": 0.5}
        result = weight_perturbation_robustness(df, weights)
        assert result["top_n"] == 10

    def test_empty_weights_returns_nan(self):
        df = _make_scored_df()
        result = weight_perturbation_robustness(df, {})
        assert result["n_perturbations"] == 0
        assert math.isnan(result["mean_rank_correlation"])

    def test_top_n_overlap_is_between_0_and_1(self):
        df = _make_scored_df(n_instruments=30)
        weights = {"mom_12_1_z": 0.40, "mansfield_rs_z": 0.30, "breadth_50d_z": 0.30}
        result = weight_perturbation_robustness(df, weights, top_n=5)
        for v in result["top_n_overlaps"]:
            assert 0.0 <= v <= 1.0, f"Overlap must be in [0, 1]; got {v}"


# ── Task 10b: state_forward_return_separation ─────────────────────────────────

class TestStateForwardReturnSeparation:
    def test_returns_one_row_per_expected_state(self):
        df = _make_separation_df()
        result = state_forward_return_separation(df)
        assert set(result["state"]) >= {
            "STAGE_2_BULLISH", "HOLD", "WARNING", "EXIT", "BEARISH_STAGE_4"
        }

    def test_separation_met_on_clean_fixture(self):
        """Fixture has clear BULLISH > HOLD > WARNING > EXIT > BEARISH ordering."""
        df = _make_separation_df()
        result = state_forward_return_separation(df)
        assert result["separation_met"].all(), (
            "separation_met should be True when state ordering matches expected"
        )

    def test_separation_not_met_when_inverted(self):
        """If EXIT has higher mean return than BULLISH, separation_met = False."""
        df = pd.DataFrame(
            {
                "state": ["EXIT"] * 20 + ["STAGE_2_BULLISH"] * 20,
                "forward_return": [0.10] * 20 + [-0.10] * 20,  # inverted
            }
        )
        result = state_forward_return_separation(df)
        assert not result["separation_met"].all()

    def test_columns_present(self):
        df = _make_separation_df()
        result = state_forward_return_separation(df)
        assert set(result.columns) >= {
            "state", "mean_return", "median_return", "std_return",
            "count", "rank_by_mean", "expected_rank", "separation_met",
        }

    def test_bullish_has_highest_mean_on_clean_fixture(self):
        df = _make_separation_df()
        result = state_forward_return_separation(df)
        bullish_row = result[result["state"] == "STAGE_2_BULLISH"].iloc[0]
        assert bullish_row["rank_by_mean"] == 1

    def test_missing_state_column_raises(self):
        df = _make_separation_df().drop(columns=["state"])
        with pytest.raises(ValueError, match="state"):
            state_forward_return_separation(df)

    def test_missing_forward_return_raises(self):
        df = _make_separation_df().drop(columns=["forward_return"])
        with pytest.raises(ValueError, match="forward_return"):
            state_forward_return_separation(df)

    def test_custom_state_order(self):
        df = _make_separation_df()
        custom = ["STAGE_2_BULLISH", "WARNING", "EXIT"]
        result = state_forward_return_separation(df, state_order=custom)
        expected_in_result = result[result["expected_rank"].notna()]["state"].tolist()
        assert set(expected_in_result) == set(custom)
