from __future__ import annotations

import pandas as pd

from src.calibration_research import (
    block_bootstrap_hit_rate_delta,
    bootstrap_hit_rate_delta,
    evaluate_expanded_candidates,
    expanded_candidate_grid,
    sector_override_candidates,
)


def test_expanded_candidate_grid_contains_global_and_sector_specific_rules():
    rules = expanded_candidate_grid()
    ids = {rule["candidate_id"] for rule in rules}

    assert "global_positive_score_ge_1_0" in ids
    assert "us_sectors_positive_score_ge_1_0_rel_strength_ge_0_0" in ids
    assert "xlk_positive_score_ge_1_0" in ids
    assert "us_sectors_negative_score_le_minus_0_5" in ids
    assert all(rule["research_only"] is True for rule in rules)


def test_sector_override_candidates_require_sample_size_and_holdout_improvement():
    rows = pd.DataFrame(
        [
            {
                "candidate_id": "xlk_rule",
                "scope": "US Sectors",
                "sector": "XLK",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": True,
                "bootstrap_ci_low": 0.01,
                "promotion_label": "research_candidate",
            },
            {
                "candidate_id": "thin_rule",
                "scope": "US Sectors",
                "sector": "XLU",
                "direction": "positive",
                "train_signal_count": 10,
                "holdout_signal_count": 4,
                "holdout_hit_rate_delta_vs_baseline": 0.40,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.02,
                "fold_stability_passed": True,
                "bootstrap_ci_low": 0.01,
                "promotion_label": "research_candidate",
            },
        ]
    )

    overrides = sector_override_candidates(
        rows,
        min_train_signals=40,
        min_holdout_signals=20,
        min_holdout_hit_rate_delta=0.05,
    )

    assert overrides["candidate_id"].tolist() == ["xlk_rule"]
    assert overrides.loc[0, "sector_weight_multiplier"] > 1.0
    assert overrides.loc[0, "live_promotion_allowed"] is False


def test_sector_override_candidates_require_research_candidate_and_bootstrap_support():
    rows = pd.DataFrame(
        [
            {
                "candidate_id": "weak_ci_rule",
                "scope": "US Sectors",
                "sector": "XLK",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": True,
                "bootstrap_ci_low": -0.01,
                "promotion_label": "needs more testing",
            },
            {
                "candidate_id": "supported_rule",
                "scope": "US Sectors",
                "sector": "XLK",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": True,
                "bootstrap_ci_low": 0.01,
                "promotion_label": "research_candidate",
            },
        ]
    )

    overrides = sector_override_candidates(rows)

    assert overrides["candidate_id"].tolist() == ["supported_rule"]


def test_sector_override_candidates_treat_string_false_as_false():
    rows = pd.DataFrame(
        [
            {
                "candidate_id": "csv_false_rule",
                "scope": "US Sectors",
                "sector": "XLK",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": "False",
                "bootstrap_ci_low": 0.01,
                "promotion_label": "research_candidate",
            }
        ]
    )

    overrides = sector_override_candidates(rows)

    assert overrides.empty


def test_sector_override_candidates_exclude_class_level_rows():
    rows = pd.DataFrame(
        [
            {
                "candidate_id": "us_sectors_class_rule",
                "scope": "US Sectors",
                "sector": "US Sectors",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": True,
                "bootstrap_ci_low": 0.01,
                "promotion_label": "research_candidate",
            }
        ]
    )

    overrides = sector_override_candidates(rows)

    assert overrides.empty


def test_sector_override_candidates_reject_non_etf_sector_names():
    rows = pd.DataFrame(
        [
            {
                "candidate_id": "named_sector_rule",
                "scope": "US Sectors",
                "sector": "Technology",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": True,
                "bootstrap_ci_low": 0.01,
                "promotion_label": "research_candidate",
            }
        ]
    )

    overrides = sector_override_candidates(rows)

    assert overrides.empty


def test_block_bootstrap_hit_rate_delta_resamples_candidate_subset_by_rebalance_block():
    result = block_bootstrap_hit_rate_delta(
        baseline_success=[1, 0, 0, 0, 0, 0],
        candidate_flags=[True, False, False, True, False, False],
        block_keys=[
            "2024-01-05",
            "2024-01-05",
            "2024-01-05",
            "2024-01-12",
            "2024-01-12",
            "2024-01-12",
        ],
        samples=200,
        random_seed=17,
    )

    assert result["method"] == "paired_block_by_rebalance_date"
    assert result["mean_delta"] == 0.333333
    assert result["candidate_sample_count"] == 2
    assert result["baseline_sample_count"] == 6
    assert result["block_count"] == 2
    assert result["valid_resample_count"] == 200
    assert result["invalid_resample_count"] == 0
    assert result == block_bootstrap_hit_rate_delta(
        baseline_success=[1, 0, 0, 0, 0, 0],
        candidate_flags=[True, False, False, True, False, False],
        block_keys=[
            "2024-01-05",
            "2024-01-05",
            "2024-01-05",
            "2024-01-12",
            "2024-01-12",
            "2024-01-12",
        ],
        samples=200,
        random_seed=17,
    )


def test_block_bootstrap_hit_rate_delta_skips_resamples_without_candidate_blocks():
    result = block_bootstrap_hit_rate_delta(
        baseline_success=[1, 0, 0, 0, 0, 0],
        candidate_flags=[True, False, False, False, False, False],
        block_keys=[
            "2024-01-05",
            "2024-01-05",
            "2024-01-12",
            "2024-01-12",
            "2024-01-19",
            "2024-01-19",
        ],
        samples=200,
        random_seed=19,
    )

    assert 0 < result["valid_resample_count"] < 200
    assert result["invalid_resample_count"] == 200 - result["valid_resample_count"]
    assert result["ci_low"] <= result["mean_delta"] <= result["ci_high"]


def test_bootstrap_hit_rate_delta_is_deterministic_and_reports_interval():
    candidate_success = [1, 1, 1, 0, 1, 1, 0, 1]
    baseline_success = [1, 0, 1, 0, 0, 1, 0, 0]

    result = bootstrap_hit_rate_delta(
        candidate_success,
        baseline_success,
        samples=200,
        random_seed=7,
    )

    assert result["mean_delta"] > 0
    assert result["ci_low"] <= result["mean_delta"] <= result["ci_high"]
    assert result == bootstrap_hit_rate_delta(
        candidate_success,
        baseline_success,
        samples=200,
        random_seed=7,
    )


def test_bootstrap_hit_rate_delta_uses_full_unequal_samples():
    result = bootstrap_hit_rate_delta(
        [1, 1],
        [0, 0, 0, 0],
        samples=100,
        random_seed=11,
    )

    assert result["mean_delta"] == 1.0
    assert result["candidate_sample_count"] == 2
    assert result["baseline_sample_count"] == 4
    assert result["sample_count"] == 6


def test_evaluate_expanded_candidates_filters_sector_rule_to_ticker_and_reports_block_bootstrap():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                [
                    "2019-01-04",
                    "2019-01-04",
                    "2024-01-05",
                    "2024-01-05",
                ]
            ),
            "class": ["US Sectors", "US Sectors", "US Sectors", "US Sectors"],
            "ticker": ["XLK", "XLF", "XLK", "XLF"],
            "positive_signal": [True, True, True, True],
            "negative_signal": [False, False, False, False],
            "S_score_after_veto": [1.1, 1.1, 1.1, 1.1],
            "label_available_13w": [True, True, True, True],
            "positive_success_13w": [True, False, True, False],
            "negative_success_13w": [False, False, False, False],
            "forward_return_13w": [0.05, -0.01, 0.04, -0.02],
            "forward_excess_return_13w": [0.03, -0.02, 0.02, -0.03],
            "post_entry_drawdown_13w": [-0.01, -0.03, -0.01, -0.04],
        }
    )
    split = {
        "status": "ready",
        "train": {"start": "2018-06-22", "end": "2023-06-21"},
        "holdout": {"start": "2023-06-22", "end": "2026-05-22", "years": 2.92},
    }

    result = evaluate_expanded_candidates(
        labels,
        split,
        candidate_rules=[
            {
                "candidate_id": "xlk_positive_score_ge_1_0",
                "scope": "US Sectors",
                "sector": "XLK",
                "direction": "positive",
                "positive_min_s_score_after_veto": 1.0,
                "research_only": True,
            }
        ],
        horizons_weeks=(13,),
        min_train_signals=1,
        min_holdout_signals=1,
    )

    assert result.loc[0, "sector"] == "XLK"
    assert result.loc[0, "train_signal_count"] == 1
    assert result.loc[0, "holdout_signal_count"] == 1
    assert result.loc[0, "bootstrap_method"] == "paired_block_by_rebalance_date"


def test_evaluate_expanded_candidates_rejects_unstable_fold_before_research_candidate():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                ["2019-01-04", "2019-01-11", "2024-01-05", "2024-01-12"]
            ),
            "class": ["US Sectors"] * 4,
            "ticker": ["XLK"] * 4,
            "positive_signal": [True] * 4,
            "negative_signal": [False] * 4,
            "S_score_after_veto": [1.1, 0.2, 1.1, 0.2],
            "label_available_13w": [True] * 4,
            "positive_success_13w": [False, True, True, False],
            "negative_success_13w": [False] * 4,
            "forward_return_13w": [-0.02, 0.03, 0.05, 0.04],
            "forward_excess_return_13w": [-0.03, 0.02, 0.03, 0.02],
            "post_entry_drawdown_13w": [-0.04, -0.01, -0.01, -0.01],
        }
    )
    split = {
        "status": "ready",
        "train": {"start": "2018-06-22", "end": "2023-06-21"},
        "holdout": {"start": "2023-06-22", "end": "2026-05-22", "years": 2.92},
    }

    result = evaluate_expanded_candidates(
        labels,
        split,
        candidate_rules=[
            {
                "candidate_id": "xlk_positive_score_ge_1_0",
                "scope": "US Sectors",
                "sector": "XLK",
                "direction": "positive",
                "positive_min_s_score_after_veto": 1.0,
                "research_only": True,
            }
        ],
        horizons_weeks=(13,),
        min_train_signals=1,
        min_holdout_signals=1,
    )

    assert result.loc[0, "fold_stability_passed"] is False
    assert result.loc[0, "promotion_label"] == "needs more testing"
    assert result.loc[0, "rejection_reasons"] == "fold_unstable"


def test_evaluate_expanded_candidates_returns_fail_closed_holdout_labels():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(["2019-01-04", "2024-01-05"]),
            "class": ["US Sectors", "US Sectors"],
            "ticker": ["XLK", "XLK"],
            "positive_signal": [True, True],
            "negative_signal": [False, False],
            "S_score_after_veto": [1.1, 1.1],
            "rs_ratio_z": [0.2, 0.2],
            "label_available_13w": [True, True],
            "positive_success_13w": [True, True],
            "negative_success_13w": [False, False],
            "forward_return_13w": [0.05, 0.04],
            "forward_excess_return_13w": [0.03, 0.02],
            "post_entry_drawdown_13w": [-0.01, -0.01],
        }
    )
    split = {
        "status": "ready",
        "train": {"start": "2018-06-22", "end": "2023-06-21"},
        "holdout": {"start": "2023-06-22", "end": "2026-05-22", "years": 2.92},
    }

    result = evaluate_expanded_candidates(
        labels,
        split,
        candidate_rules=[
            {
                "candidate_id": "global_positive_score_ge_1_0",
                "scope": "global",
                "direction": "positive",
                "positive_min_s_score_after_veto": 1.0,
                "research_only": True,
            }
        ],
        horizons_weeks=(13,),
        min_train_signals=1,
        min_holdout_signals=1,
    )

    assert result.loc[0, "candidate_id"] == "global_positive_score_ge_1_0"
    assert result.loc[0, "holdout_evaluated"] is True
    assert result.loc[0, "live_promotion_allowed"] is False


def test_evaluate_expanded_candidates_excludes_holdout_labels_that_mature_after_holdout():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(["2019-01-04", "2024-01-05"]),
            "class": ["US Sectors", "US Sectors"],
            "ticker": ["XLK", "XLK"],
            "positive_signal": [True, True],
            "negative_signal": [False, False],
            "S_score_after_veto": [1.1, 1.1],
            "label_available_52w": [True, True],
            "label_end_date_52w": pd.to_datetime(["2020-01-03", "2027-01-01"]),
            "positive_success_52w": [True, True],
            "negative_success_52w": [False, False],
            "forward_return_52w": [0.05, 0.04],
            "forward_excess_return_52w": [0.03, 0.02],
            "post_entry_drawdown_52w": [-0.01, -0.01],
        }
    )
    split = {
        "status": "ready",
        "train": {"start": "2018-06-22", "end": "2023-06-21"},
        "holdout": {"start": "2023-06-22", "end": "2026-05-22", "years": 2.92},
    }

    result = evaluate_expanded_candidates(
        labels,
        split,
        candidate_rules=[
            {
                "candidate_id": "global_positive_score_ge_1_0",
                "scope": "global",
                "direction": "positive",
                "positive_min_s_score_after_veto": 1.0,
                "research_only": True,
            }
        ],
        horizons_weeks=(52,),
        min_train_signals=1,
        min_holdout_signals=1,
    )

    assert result.loc[0, "holdout_signal_count"] == 0
    assert result.loc[0, "holdout_evaluated"] is False
    assert result.loc[0, "promotion_label"] == "do not promote"


def test_evaluate_expanded_candidates_marks_thin_zero_sample_as_unstable():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(["2019-01-04", "2024-01-05"]),
            "class": ["US Sectors", "US Sectors"],
            "ticker": ["XLK", "XLK"],
            "positive_signal": [True, True],
            "negative_signal": [False, False],
            "S_score_after_veto": [0.1, 0.1],
            "label_available_13w": [True, True],
            "positive_success_13w": [True, True],
            "negative_success_13w": [False, False],
            "forward_return_13w": [0.05, 0.04],
            "forward_excess_return_13w": [0.03, 0.02],
            "post_entry_drawdown_13w": [-0.01, -0.01],
        }
    )
    split = {
        "status": "ready",
        "train": {"start": "2018-06-22", "end": "2023-06-21"},
        "holdout": {"start": "2023-06-22", "end": "2026-05-22", "years": 2.92},
    }

    result = evaluate_expanded_candidates(
        labels,
        split,
        candidate_rules=[
            {
                "candidate_id": "global_positive_score_ge_1_0",
                "scope": "global",
                "direction": "positive",
                "positive_min_s_score_after_veto": 1.0,
                "research_only": True,
            }
        ],
        horizons_weeks=(13,),
        min_train_signals=1,
        min_holdout_signals=1,
    )

    assert result.loc[0, "train_signal_count"] == 0
    assert result.loc[0, "holdout_signal_count"] == 0
    assert result.loc[0, "fold_stability_passed"] is False
    assert result.loc[0, "promotion_label"] == "do not promote"
