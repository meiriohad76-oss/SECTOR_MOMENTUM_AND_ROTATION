from __future__ import annotations

import pandas as pd
import pytest

from src import backtest


def test_run_weight_backtest_uses_prior_weights_and_charges_turnover_costs():
    dates = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 121.0, 121.0],
            "BBB": [100.0, 100.0, 100.0, 110.0],
        },
        index=dates,
    )
    target_weights = pd.DataFrame(
        {
            "AAA": [1.0, 0.0],
            "BBB": [0.0, 1.0],
        },
        index=[dates[0], dates[2]],
    )

    result = backtest.run_weight_backtest(
        prices,
        target_weights,
        transaction_cost_bps=10.0,
        initial_capital=100.0,
    )

    assert result.gross_returns.tolist() == pytest.approx([0.10, 0.10, 0.10])
    assert result.turnover.tolist() == pytest.approx([1.0, 0.0, 2.0])
    assert result.costs.tolist() == pytest.approx([0.001, 0.0, 0.002])
    assert result.net_returns.tolist() == pytest.approx([0.0989, 0.10, 0.0978])
    assert result.equity.iloc[0] == pytest.approx(100.0)
    assert result.equity.iloc[-1] == pytest.approx(132.7009662)


def test_performance_metrics_reports_drawdown_and_turnover():
    dates = pd.bdate_range("2024-01-01", periods=5)
    returns = pd.Series([0.10, -0.25, 0.10, 0.00], index=dates[1:])
    equity = pd.Series([100.0, 110.0, 82.5, 90.75, 90.75], index=dates)
    turnover = pd.Series([1.0, 0.0, 0.5, 0.0], index=dates[1:])

    metrics = backtest.performance_metrics(
        returns,
        equity=equity,
        turnover=turnover,
        periods_per_year=4,
    )

    assert metrics["total_return"] == pytest.approx(-0.0925)
    assert metrics["max_drawdown"] == pytest.approx(-0.25)
    assert metrics["calmar"] < 0
    assert metrics["average_turnover"] == pytest.approx(0.375)
    assert metrics["annualized_turnover"] == pytest.approx(1.5)


def test_performance_metrics_builds_equity_from_initial_capital_when_missing():
    dates = pd.bdate_range("2024-01-01", periods=3)
    returns = pd.Series([0.10, 0.10], index=dates[1:])

    metrics = backtest.performance_metrics(returns, periods_per_year=2)

    assert metrics["total_return"] == pytest.approx(0.21)


def test_split_backtest_metrics_uses_2015_boundary_for_oos():
    dates = pd.to_datetime(["2014-12-30", "2014-12-31", "2015-01-02", "2015-01-05"])
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 99.0, 118.8]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])
    result = backtest.run_weight_backtest(prices, weights, periods_per_year=252)

    windows = backtest.split_backtest_metrics(result, oos_start="2015-01-01", periods_per_year=252)

    assert list(windows) == ["Full period", "In-sample", "Out-of-sample"]
    assert windows["Full period"]["total_return"] == pytest.approx(0.188)
    assert windows["In-sample"]["total_return"] == pytest.approx(0.10)
    assert windows["Out-of-sample"]["total_return"] == pytest.approx(0.08)
    assert windows["In-sample"]["annualized_turnover"] == pytest.approx(252.0)
    assert windows["Out-of-sample"]["annualized_turnover"] == pytest.approx(0.0)


def test_split_backtest_metrics_returns_finite_zeroes_for_empty_windows():
    dates = pd.bdate_range("2020-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])
    result = backtest.run_weight_backtest(prices, weights)

    windows = backtest.split_backtest_metrics(result, oos_start="2015-01-01")

    assert windows["In-sample"]["total_return"] == 0.0
    assert windows["In-sample"]["sharpe"] == 0.0
    assert windows["In-sample"]["max_drawdown"] == 0.0


def test_frozen_baseline_config_is_deterministic_and_hash_is_order_independent():
    config = backtest.frozen_baseline_config(
        universe=["XLK", "SPY", "BIL", "XLK"],
        ohlcv_provider="massive",
        transaction_cost_bps=5.0,
        phase="MID",
    )
    same_config = backtest.frozen_baseline_config(
        universe=("BIL", "SPY", "XLK"),
        ohlcv_provider="massive",
        transaction_cost_bps=5.0,
        phase="MID",
    )

    assert config == same_config
    assert config["ticket"] == "B-163"
    assert config["universe"] == ["BIL", "SPY", "XLK"]
    assert config["rebalance"]["cadence"] == "W-FRI"
    assert config["accounting"]["transaction_cost_bps"] == 5.0
    assert config["accounting"]["periods_per_year"] == backtest.TRADING_DAYS_PER_YEAR
    assert config["provider_flags"]["ohlcv_provider"] == "massive"
    assert config["provider_flags"]["historical_provider_flow"] == "neutral_stub"
    assert config["universe_classes"] == {
        "BIL": "Benchmark",
        "SPY": "Benchmark",
        "XLK": "US Sectors",
    }
    assert config["scoring_parameters"]["composite_weights"] == {
        "mom_12_1_z": 0.22,
        "mansfield_rs_z": 0.12,
        "rs_ratio_z": 0.15,
        "rs_momentum_z": 0.08,
        "binary_filters": 0.12,
        "cycle_tilt": 0.08,
        "provider_flow_z": 0.23,
    }
    assert config["scoring_parameters"]["flow_veto"]["threshold_z"] == -0.5
    assert config["scoring_parameters"]["flow_veto"]["replacement_score"] == -9.99
    assert config["scoring_parameters"]["selection_top_n_by_class"]["US Sectors"] == 4
    assert config["scoring_parameters"]["state_machine"]["exit"]["etf_flow_5d_pct_lt"] == -1.5
    assert config["scoring_parameters"]["state_machine"]["warning"]["dist_days_25_gte"] == 4
    assert config["scoring_parameters"]["state_machine"]["stage_2_bullish"]["breadth_50d_gte"] == 0.60
    assert config["algorithm_components"]["target_builder"] == (
        "src.backtest.build_historical_methodology_targets"
    )
    assert config["safety"]["research_only"] is True
    assert config["safety"]["live_promotion_requires_separate_ticket"] is True

    reordered = {key: config[key] for key in reversed(config)}
    reordered["provider_flags"] = {
        key: config["provider_flags"][key] for key in reversed(config["provider_flags"])
    }
    digest = backtest.baseline_config_hash(config)
    assert digest == backtest.baseline_config_hash(reordered)
    assert len(digest) == 64
    int(digest, 16)


def test_walk_forward_calibration_splits_cover_ten_years_without_holdout_leakage():
    dates = pd.bdate_range("2016-01-01", "2025-12-31")

    splits = backtest.walk_forward_calibration_splits(
        dates,
        years=10,
        calibration_years=5,
        validation_years=1,
        final_holdout_years=1,
    )

    assert len(splits) == 4
    assert [split.name for split in splits] == ["fold_01", "fold_02", "fold_03", "fold_04"]
    assert splits[0].calibration_start == pd.Timestamp("2016-01-01")
    assert splits[0].validation_start == pd.Timestamp("2021-01-01")
    assert splits[-1].validation_end < splits[-1].final_holdout_start
    assert {split.final_holdout_start for split in splits} == {pd.Timestamp("2024-12-31")}
    assert {split.final_holdout_end for split in splits} == {pd.Timestamp("2025-12-31")}
    for split in splits:
        assert split.calibration_start <= split.calibration_end < split.validation_start
        assert split.validation_start <= split.validation_end < split.final_holdout_start
        assert split.final_holdout_start <= split.final_holdout_end

    summary = backtest.walk_forward_split_summary(splits)
    assert summary["status"] == "ready"
    assert summary["requested_years"] == 10
    assert summary["window"]["start"] == "2016-01-01"
    assert summary["window"]["end"] == "2025-12-31"
    assert summary["final_holdout"]["start"] == "2024-12-31"
    assert summary["fold_count"] == 4
    assert summary["folds"][0]["calibration_start"] == "2016-01-01"


def test_walk_forward_calibration_splits_accept_short_history_with_minimum_floor():
    dates = pd.bdate_range("2018-06-22", "2026-05-22")

    with pytest.raises(ValueError, match="at least 10 years"):
        backtest.walk_forward_calibration_splits(dates, years=10)

    splits = backtest.walk_forward_calibration_splits(
        dates,
        years=10,
        minimum_years=5,
        calibration_years=5,
        validation_years=1,
        final_holdout_years=1,
    )

    assert splits
    assert splits[0].calibration_start == pd.Timestamp("2018-06-22")
    assert splits[-1].validation_end < splits[-1].final_holdout_start
    summary = backtest.walk_forward_split_summary(
        splits,
        requested_years=10,
        minimum_accepted_years=5,
    )
    assert summary["status"] == "ready"
    assert summary["history_window_status"] == "accepted_short_history"
    assert summary["requested_years"] == 10
    assert summary["minimum_accepted_years"] == 5
    assert summary["coverage_years"] >= 7.8
    assert summary["effective_calibration_years"] == 5
    assert summary["no_lookahead_verified"] is True


def test_fixed_train_holdout_split_uses_five_year_train_and_remaining_holdout():
    dates = pd.bdate_range("2018-06-22", "2026-05-22")

    split = backtest.fixed_train_holdout_calibration_split(
        dates,
        train_years=5,
        minimum_holdout_years=2,
        maximum_holdout_years=3,
    )

    assert split["status"] == "ready"
    assert split["profile"] == "fixed_5y_train_2y_to_3y_holdout"
    assert split["train"]["start"] == "2018-06-22"
    assert split["train"]["end"] < split["holdout"]["start"]
    assert split["holdout"]["years"] >= 2.0
    assert split["holdout"]["years"] <= 3.05
    assert split["no_lookahead_verified"] is True


def test_walk_forward_calibration_splits_adapt_calibration_years_for_five_to_seven_year_history():
    cases = [
        ("2021-05-21", 3),
        ("2020-05-22", 4),
        ("2019-05-22", 5),
    ]

    for start_date, expected_calibration_years in cases:
        dates = pd.bdate_range(start_date, "2026-05-22")

        splits = backtest.walk_forward_calibration_splits(
            dates,
            years=10,
            minimum_years=5,
            calibration_years=5,
            validation_years=1,
            final_holdout_years=1,
        )
        summary = backtest.walk_forward_split_summary(
            splits,
            requested_years=10,
            minimum_accepted_years=5,
        )

        assert splits
        assert summary["status"] == "ready"
        assert summary["history_window_status"] == "accepted_short_history"
        assert summary["effective_calibration_years"] == expected_calibration_years
        assert {split.calibration_years for split in splits} == {expected_calibration_years}


def test_walk_forward_calibration_splits_reject_invalid_or_too_short_history():
    dates = pd.bdate_range("2024-01-01", periods=40)

    with pytest.raises(ValueError, match="at least 10 years"):
        backtest.walk_forward_calibration_splits(dates, years=10)

    gap_after_window_start = pd.DatetimeIndex(
        [pd.Timestamp("2016-01-01")]
    ).append(pd.bdate_range("2016-03-01", "2025-12-31"))
    with pytest.raises(ValueError, match="continuous 10-year window"):
        backtest.walk_forward_calibration_splits(gap_after_window_start, years=10)

    with pytest.raises(ValueError, match="calibration, validation, and holdout"):
        backtest.walk_forward_calibration_splits(
            pd.bdate_range("2016-01-01", "2025-12-31"),
            years=10,
            calibration_years=8,
            validation_years=1,
            final_holdout_years=1,
        )


def test_calibration_candidate_search_evaluates_selected_candidate_on_final_holdout():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                [
                    "2020-01-03",
                    "2020-01-10",
                    "2021-01-08",
                    "2021-01-15",
                    "2022-01-07",
                    "2022-01-14",
                    "2022-12-16",
                ]
            ),
            "ticker": ["XLK", "XLF", "XLK", "XLF", "XLK", "XLF", "XLK"],
            "positive_signal": [True, True, True, True, True, True, True],
            "negative_signal": [False, False, False, False, False, False, False],
            "S_score_after_veto": [1.0, 0.2, 1.0, 0.2, 1.0, 0.2, 1.0],
            "label_available_4w": [True, True, True, True, True, True, True],
            "label_end_date_4w": pd.to_datetime(
                [
                    "2020-01-31",
                    "2020-02-07",
                    "2021-02-05",
                    "2021-02-12",
                    "2022-02-04",
                    "2022-02-11",
                    "2023-01-13",
                ]
            ),
            "positive_success_4w": [True, False, True, False, True, False, False],
            "negative_success_4w": [False, False, False, False, False, False, False],
            "forward_return_4w": [0.08, -0.03, 0.06, -0.02, 0.07, -0.04, -0.20],
            "forward_excess_return_4w": [0.04, -0.02, 0.03, -0.01, 0.04, -0.03, -0.18],
            "post_entry_drawdown_4w": [-0.01, -0.05, -0.01, -0.04, -0.01, -0.08, -0.30],
        }
    )
    split = backtest.WalkForwardSplit(
        name="fold_01",
        calibration_start=pd.Timestamp("2020-01-01"),
        calibration_end=pd.Timestamp("2020-12-31"),
        validation_start=pd.Timestamp("2021-01-01"),
        validation_end=pd.Timestamp("2021-12-31"),
        final_holdout_start=pd.Timestamp("2022-01-01"),
        final_holdout_end=pd.Timestamp("2022-12-31"),
    )

    candidates = backtest.calibration_candidate_search(
        labels,
        [split],
        horizons_weeks=(4,),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="positive_score_ge_0_8",
                positive_min_s_score_after_veto=0.8,
            ),
        ),
        min_direction_signal_count=1,
        evaluate_final_holdout=True,
    )

    selected = candidates[candidates["selected_by_calibration"]].iloc[0]

    assert selected["candidate_id"] == "positive_score_ge_0_8"
    assert selected["selection_source"] == "calibration_window_only"
    assert selected["final_holdout_evaluated"] is True
    assert selected["final_holdout_rows_used"] == 2
    assert selected["final_holdout_positive_hit_rate"] == pytest.approx(1.0)
    assert selected["baseline_final_holdout_positive_hit_rate"] == pytest.approx(0.5)
    assert selected["final_holdout_positive_hit_rate_delta_vs_baseline"] == pytest.approx(0.5)
    assert selected["gate_status"] == "passed_final_holdout_research_candidate"
    assert selected["promotion_label"] == "candidate"
    assert selected["live_promotion_allowed"] is False


def test_calibration_candidate_search_selects_strictly_before_holdout_availability_check():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                [
                    "2018-01-05",
                    "2018-01-12",
                    "2020-01-03",
                    "2020-01-10",
                    "2022-01-07",
                    "2022-01-14",
                ]
            ),
            "ticker": ["XLK", "XLF", "XLK", "XLF", "XLK", "XLF"],
            "positive_signal": [True, True, True, True, True, True],
            "negative_signal": [False, False, False, False, False, False],
            "S_score_after_veto": [1.0, 0.2, 1.0, 0.2, 1.0, 0.2],
            "label_available_4w": [True, True, True, True, True, True],
            "label_end_date_4w": pd.to_datetime(
                [
                    "2018-02-02",
                    "2018-02-09",
                    "2020-01-31",
                    "2020-02-07",
                    "2022-02-04",
                    "2022-02-11",
                ]
            ),
            "positive_success_4w": [True, True, True, True, True, False],
            "negative_success_4w": [False, False, False, False, False, False],
            "forward_return_4w": [0.08, 0.03, 0.06, 0.02, 0.07, -0.04],
            "forward_excess_return_4w": [0.04, 0.02, 0.03, 0.01, 0.04, -0.03],
            "post_entry_drawdown_4w": [-0.01, -0.02, -0.01, -0.02, -0.01, -0.08],
            "label_available_52w": [True, True, True, True, False, False],
            "label_end_date_52w": pd.to_datetime(
                [
                    "2019-01-04",
                    "2019-01-11",
                    "2021-01-01",
                    "2021-01-08",
                    "2023-01-06",
                    "2023-01-13",
                ]
            ),
            "positive_success_52w": [True, False, True, False, False, False],
            "negative_success_52w": [False, False, False, False, False, False],
            "forward_return_52w": [0.18, -0.12, 0.16, -0.10, float("nan"), float("nan")],
            "forward_excess_return_52w": [0.12, -0.08, 0.11, -0.07, float("nan"), float("nan")],
            "post_entry_drawdown_52w": [-0.04, -0.20, -0.03, -0.18, float("nan"), float("nan")],
        }
    )
    split = backtest.WalkForwardSplit(
        name="fold_01",
        calibration_start=pd.Timestamp("2018-01-01"),
        calibration_end=pd.Timestamp("2019-12-31"),
        validation_start=pd.Timestamp("2020-01-01"),
        validation_end=pd.Timestamp("2020-12-31"),
        final_holdout_start=pd.Timestamp("2022-01-01"),
        final_holdout_end=pd.Timestamp("2022-12-31"),
    )

    candidates = backtest.calibration_candidate_search(
        labels,
        [split],
        horizons_weeks=(4, 52),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="positive_score_ge_0_8",
                positive_min_s_score_after_veto=0.8,
            ),
        ),
        min_direction_signal_count=1,
        evaluate_final_holdout=True,
    )

    selected = candidates[candidates["selected_by_calibration"]].iloc[0]

    assert selected["candidate_id"] == "positive_score_ge_0_8"
    assert selected["horizon_weeks"] == 52
    assert selected["selection_source"] == "calibration_window_only"
    assert selected["final_holdout_evaluated"] is False
    assert selected["final_holdout_rows_used"] == 0
    assert selected["gate_status"] == "rejected_final_holdout_no_data"


def test_calibration_feature_labels_use_point_in_time_snapshots_and_forward_outcomes():
    dates = pd.to_datetime(["2024-01-05", "2024-01-12", "2024-02-02", "2024-02-09"])
    prices = pd.DataFrame(
        {
            "XLK": [100.0, 90.0, 110.0, 112.0],
            "XLF": [100.0, 85.0, 90.0, 88.0],
            "SPY": [100.0, 98.0, 105.0, 106.0],
        },
        index=dates,
    )
    first_snapshot = pd.DataFrame(
        {
            "class": ["US Sectors", "US Sectors"],
            "selected": [True, False],
            "S_score": [1.2, -0.5],
            "S_score_after_veto": [1.2, -9.99],
            "rank_in_class": [1, 5],
            "top_n_target": [4, 4],
            "veto": [False, True],
        },
        index=["XLK", "XLF"],
    )
    future_snapshot = first_snapshot.copy()
    future_snapshot.loc["XLK", "S_score"] = 99.0
    targets = backtest.HistoricalSignalTargets(
        target_weights=pd.DataFrame({"XLK": [1.0, 0.0], "XLF": [0.0, 0.0]}, index=[dates[0], dates[2]]),
        states=pd.DataFrame({"XLK": ["STAGE_2_BULLISH", "HOLD"], "XLF": ["EXIT", "WARNING"]}, index=[dates[0], dates[2]]),
        snapshots={dates[0]: first_snapshot, dates[2]: future_snapshot},
    )

    labels = backtest.build_calibration_feature_labels(
        targets,
        prices,
        horizons_weeks=(4,),
        benchmark_by_class={"US Sectors": "SPY"},
        drawdown_avoidance_threshold=-0.10,
    )

    first_rows = labels[labels["rebalance_date"] == dates[0]].set_index("ticker")
    assert list(first_rows.index) == ["XLK", "XLF"]
    assert first_rows.loc["XLK", "feature_asof_date"] == dates[0]
    assert first_rows.loc["XLK", "S_score"] == pytest.approx(1.2)
    assert first_rows.loc["XLK", "positive_signal"] is True
    assert first_rows.loc["XLK", "negative_signal"] is False
    assert first_rows.loc["XLK", "label_available_4w"] is True
    assert first_rows.loc["XLK", "label_end_date_4w"] == dates[2]
    assert first_rows.loc["XLK", "forward_return_4w"] == pytest.approx(0.10)
    assert first_rows.loc["XLK", "forward_benchmark_return_4w"] == pytest.approx(0.05)
    assert first_rows.loc["XLK", "forward_excess_return_4w"] == pytest.approx(0.05)
    assert first_rows.loc["XLK", "post_entry_drawdown_4w"] == pytest.approx(-0.10)
    assert first_rows.loc["XLK", "positive_success_4w"] is True

    assert first_rows.loc["XLF", "positive_signal"] is False
    assert first_rows.loc["XLF", "negative_signal"] is True
    assert first_rows.loc["XLF", "forward_return_4w"] == pytest.approx(-0.10)
    assert first_rows.loc["XLF", "forward_excess_return_4w"] == pytest.approx(-0.15)
    assert first_rows.loc["XLF", "post_entry_drawdown_4w"] == pytest.approx(-0.15)
    assert first_rows.loc["XLF", "negative_avoided_underperformance_4w"] is True
    assert first_rows.loc["XLF", "negative_failed_followthrough_4w"] is True
    assert first_rows.loc["XLF", "negative_avoided_drawdown_4w"] is True
    assert first_rows.loc["XLF", "negative_success_4w"] is True


def test_calibration_feature_labels_mark_unavailable_future_horizons_without_filling():
    dates = pd.to_datetime(["2024-01-05", "2024-01-12", "2024-02-02"])
    prices = pd.DataFrame(
        {
            "XLK": [100.0, 101.0, 102.0],
            "SPY": [100.0, 101.0, 102.0],
        },
        index=dates,
    )
    snapshot = pd.DataFrame(
        {
            "class": ["US Sectors"],
            "selected": [True],
            "S_score": [1.0],
        },
        index=["XLK"],
    )
    targets = backtest.HistoricalSignalTargets(
        target_weights=pd.DataFrame({"XLK": [1.0]}, index=[dates[-1]]),
        states=pd.DataFrame({"XLK": ["HOLD"]}, index=[dates[-1]]),
        snapshots={dates[-1]: snapshot},
    )

    labels = backtest.build_calibration_feature_labels(
        targets,
        prices,
        horizons_weeks=(4,),
        benchmark_by_class={"US Sectors": "SPY"},
    )

    row = labels.iloc[0]
    assert row["label_available_4w"] is False
    assert pd.isna(row["label_end_date_4w"])
    assert pd.isna(row["forward_return_4w"])
    assert pd.isna(row["forward_excess_return_4w"])
    assert pd.isna(row["post_entry_drawdown_4w"])
    assert row["positive_success_4w"] is False
    assert row["negative_success_4w"] is False


def test_calibration_feature_labels_do_not_forward_fill_missing_future_prices():
    dates = pd.to_datetime(["2024-01-05", "2024-02-02"])
    prices = pd.DataFrame(
        {
            "XLK": [100.0, None],
            "SPY": [100.0, 105.0],
        },
        index=dates,
    )
    snapshot = pd.DataFrame(
        {
            "class": ["US Sectors"],
            "selected": [True],
            "S_score": [1.0],
        },
        index=["XLK"],
    )
    targets = backtest.HistoricalSignalTargets(
        target_weights=pd.DataFrame({"XLK": [1.0]}, index=[dates[0]]),
        states=pd.DataFrame({"XLK": ["STAGE_2_BULLISH"]}, index=[dates[0]]),
        snapshots={dates[0]: snapshot},
    )

    labels = backtest.build_calibration_feature_labels(
        targets,
        prices,
        horizons_weeks=(4,),
        benchmark_by_class={"US Sectors": "SPY"},
    )

    row = labels.iloc[0]
    assert row["label_available_4w"] is False
    assert pd.isna(row["forward_return_4w"])
    assert pd.isna(row["forward_excess_return_4w"])
    assert row["positive_success_4w"] is False


def test_calibration_label_metrics_reports_directional_success_and_confusion_counts():
    labels = pd.DataFrame(
        {
            "class": ["US Sectors", "US Sectors", "US Sectors", "Bonds"],
            "positive_signal": [True, True, False, False],
            "negative_signal": [False, False, True, False],
            "label_available_4w": [True, True, True, True],
            "positive_success_4w": [True, False, False, False],
            "negative_success_4w": [False, False, True, False],
            "forward_return_4w": [0.10, -0.05, -0.08, 0.04],
            "forward_excess_return_4w": [0.04, -0.03, -0.06, 0.02],
            "post_entry_drawdown_4w": [-0.02, -0.12, -0.15, 0.00],
        }
    )

    metrics = backtest.calibration_label_metrics(labels, horizons_weeks=(4,))

    positive = metrics.set_index(["direction", "horizon_weeks"]).loc[("positive", 4)]
    assert positive["total_count"] == 4
    assert positive["available_count"] == 4
    assert positive["signal_count"] == 2
    assert positive["signal_available_count"] == 2
    assert positive["success_count"] == 1
    assert positive["failure_count"] == 1
    assert positive["hit_rate"] == pytest.approx(0.5)
    assert positive["true_positive"] == 1
    assert positive["false_positive"] == 1
    assert positive["false_negative"] == 1
    assert positive["true_negative"] == 1
    assert positive["precision"] == pytest.approx(0.5)
    assert positive["recall"] == pytest.approx(0.5)
    assert positive["f1"] == pytest.approx(0.5)
    assert positive["average_forward_return"] == pytest.approx(0.025)
    assert positive["average_forward_excess_return"] == pytest.approx(0.005)
    assert positive["average_post_entry_drawdown"] == pytest.approx(-0.07)
    assert positive["average_drawdown_avoided"] == pytest.approx(0.0)

    negative = metrics.set_index(["direction", "horizon_weeks"]).loc[("negative", 4)]
    assert negative["signal_count"] == 1
    assert negative["signal_available_count"] == 1
    assert negative["success_count"] == 1
    assert negative["failure_count"] == 0
    assert negative["hit_rate"] == pytest.approx(1.0)
    assert negative["true_positive"] == 1
    assert negative["false_positive"] == 0
    assert negative["false_negative"] == 1
    assert negative["true_negative"] == 2
    assert negative["precision"] == pytest.approx(1.0)
    assert negative["recall"] == pytest.approx(0.5)
    assert negative["f1"] == pytest.approx(2 / 3)
    assert negative["average_forward_return"] == pytest.approx(-0.08)
    assert negative["average_forward_excess_return"] == pytest.approx(-0.06)
    assert negative["average_post_entry_drawdown"] == pytest.approx(-0.15)
    assert negative["average_drawdown_avoided"] == pytest.approx(0.15)


def test_calibration_label_metrics_excludes_unavailable_labels_and_groups_rows():
    labels = pd.DataFrame(
        {
            "class": ["US Sectors", "US Sectors", "Bonds"],
            "state": ["STAGE_2_BULLISH", "EXIT", "EXIT"],
            "positive_signal": [True, False, False],
            "negative_signal": [False, True, True],
            "label_available_4w": [False, True, False],
            "positive_success_4w": [False, False, False],
            "negative_success_4w": [False, False, False],
            "forward_return_4w": [float("nan"), 0.03, float("nan")],
            "forward_excess_return_4w": [float("nan"), 0.01, float("nan")],
            "post_entry_drawdown_4w": [float("nan"), -0.01, float("nan")],
        }
    )

    metrics = backtest.calibration_label_metrics(labels, horizons_weeks=(4,), group_by="class")

    grouped = metrics.set_index(["class", "direction", "horizon_weeks"])
    us_negative = grouped.loc[("US Sectors", "negative", 4)]
    assert us_negative["total_count"] == 2
    assert us_negative["available_count"] == 1
    assert us_negative["unavailable_count"] == 1
    assert us_negative["signal_count"] == 1
    assert us_negative["signal_available_count"] == 1
    assert us_negative["signal_unavailable_count"] == 0
    assert us_negative["success_count"] == 0
    assert us_negative["failure_count"] == 1
    assert us_negative["hit_rate"] == pytest.approx(0.0)

    bonds_negative = grouped.loc[("Bonds", "negative", 4)]
    assert bonds_negative["total_count"] == 1
    assert bonds_negative["available_count"] == 0
    assert bonds_negative["unavailable_count"] == 1
    assert bonds_negative["signal_count"] == 1
    assert bonds_negative["signal_available_count"] == 0
    assert bonds_negative["signal_unavailable_count"] == 1
    assert bonds_negative["success_count"] == 0
    assert bonds_negative["failure_count"] == 0
    assert bonds_negative["hit_rate"] == pytest.approx(0.0)


def test_calibration_label_metrics_accepts_columnless_empty_label_table():
    metrics = backtest.calibration_label_metrics(pd.DataFrame(), horizons_weeks=(4,))

    assert metrics.empty
    assert list(metrics.columns) == [
        "direction",
        "horizon_weeks",
        "total_count",
        "available_count",
        "unavailable_count",
        "missing_label_rate",
        "signal_count",
        "signal_available_count",
        "signal_unavailable_count",
        "signal_missing_rate",
        "success_count",
        "failure_count",
        "hit_rate",
        "actual_outcome_count",
        "true_positive",
        "false_positive",
        "false_negative",
        "true_negative",
        "precision",
        "recall",
        "f1",
        "average_forward_return",
        "average_forward_excess_return",
        "average_post_entry_drawdown",
        "average_drawdown_avoided",
    ]


def test_calibration_label_metrics_recomputes_negative_outcomes_with_metrics_threshold():
    labels = pd.DataFrame(
        {
            "positive_signal": [False],
            "negative_signal": [True],
            "label_available_4w": [True],
            "positive_success_4w": [False],
            "negative_success_4w": [True],
            "forward_return_4w": [0.04],
            "forward_excess_return_4w": [0.02],
            "post_entry_drawdown_4w": [-0.06],
        }
    )

    metrics = backtest.calibration_label_metrics(
        labels,
        horizons_weeks=(4,),
        drawdown_avoidance_threshold=-0.10,
    )

    negative = metrics.set_index(["direction", "horizon_weeks"]).loc[("negative", 4)]
    assert negative["success_count"] == 0
    assert negative["failure_count"] == 1
    assert negative["hit_rate"] == pytest.approx(0.0)
    assert negative["actual_outcome_count"] == 0
    assert negative["false_positive"] == 1
    assert negative["true_positive"] == 0


def test_calibration_candidate_search_selects_using_calibration_folds_only():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                [
                    "2020-01-03",
                    "2020-01-10",
                    "2020-01-17",
                    "2021-01-08",
                    "2021-01-15",
                    "2022-01-07",
                ]
            ),
            "ticker": ["XLK", "XLF", "XLE", "XLK", "XLF", "XLK"],
            "positive_signal": [True, True, False, True, False, True],
            "negative_signal": [False, False, True, False, True, False],
            "S_score_after_veto": [1.2, 0.1, -0.8, 1.1, -0.7, 9.9],
            "label_available_4w": [True, True, True, True, True, True],
            "positive_success_4w": [True, False, False, True, False, True],
            "negative_success_4w": [False, False, True, False, True, False],
            "forward_return_4w": [0.08, -0.04, -0.07, 0.05, -0.06, 0.50],
            "forward_excess_return_4w": [0.05, -0.02, -0.04, 0.03, -0.04, 0.45],
            "post_entry_drawdown_4w": [-0.01, -0.05, -0.11, -0.01, -0.09, -0.01],
        }
    )
    split = backtest.WalkForwardSplit(
        name="fold_01",
        calibration_start=pd.Timestamp("2020-01-01"),
        calibration_end=pd.Timestamp("2020-12-31"),
        validation_start=pd.Timestamp("2021-01-01"),
        validation_end=pd.Timestamp("2021-12-31"),
        final_holdout_start=pd.Timestamp("2022-01-01"),
        final_holdout_end=pd.Timestamp("2022-12-31"),
    )

    candidates = backtest.calibration_candidate_search(
        labels,
        [split],
        horizons_weeks=(4,),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="positive_score_ge_0_8",
                positive_min_s_score_after_veto=0.8,
            ),
            backtest.CalibrationCandidateRule(
                candidate_id="future_oracle_score_ge_9",
                positive_min_s_score_after_veto=9.0,
            ),
        ),
        min_direction_signal_count=1,
    )

    selected = candidates[candidates["selected_by_calibration"]].iloc[0]
    future_oracle = candidates[candidates["candidate_id"] == "future_oracle_score_ge_9"].iloc[0]

    assert selected["candidate_id"] == "positive_score_ge_0_8"
    assert selected["selection_source"] == "calibration_window_only"
    assert selected["final_holdout_evaluated"] is False
    assert selected["final_holdout_rows_used"] == 0
    assert "final_holdout_not_evaluated" in selected["rejection_reasons"]
    assert selected["promotion_label"] == "needs more testing"
    assert future_oracle["selected_by_calibration"] is False
    assert future_oracle["calibration_positive_signal_available_count"] == 0
    assert future_oracle["validation_positive_signal_available_count"] == 0


def test_calibration_candidate_search_rejection_gates_label_thin_and_degraded_rows():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                [
                    "2020-01-03",
                    "2020-01-10",
                    "2020-01-17",
                    "2020-01-24",
                    "2021-01-08",
                    "2021-01-15",
                    "2021-01-22",
                ]
            ),
            "ticker": ["XLK", "XLF", "XLE", "XLV", "XLK", "XLF", "XLE"],
            "positive_signal": [True, False, False, False, True, False, False],
            "negative_signal": [False, True, True, True, False, True, True],
            "S_score_after_veto": [1.0, -1.0, 0.5, -0.9, 1.1, 0.5, -1.0],
            "label_available_4w": [True, True, True, True, True, True, True],
            "positive_success_4w": [True, False, False, False, True, False, False],
            "negative_success_4w": [False, True, False, True, False, True, False],
            "forward_return_4w": [0.08, -0.08, 0.04, -0.07, 0.06, -0.06, 0.03],
            "forward_excess_return_4w": [0.04, -0.05, 0.02, -0.05, 0.03, -0.04, 0.02],
            "post_entry_drawdown_4w": [-0.01, -0.12, -0.01, -0.08, -0.01, -0.09, -0.01],
        }
    )
    split = backtest.WalkForwardSplit(
        name="fold_01",
        calibration_start=pd.Timestamp("2020-01-01"),
        calibration_end=pd.Timestamp("2020-12-31"),
        validation_start=pd.Timestamp("2021-01-01"),
        validation_end=pd.Timestamp("2021-12-31"),
        final_holdout_start=pd.Timestamp("2022-01-01"),
        final_holdout_end=pd.Timestamp("2022-12-31"),
    )

    thin = backtest.calibration_candidate_search(
        labels,
        [split],
        horizons_weeks=(4,),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="negative_score_le_0",
                negative_max_s_score_after_veto=0.0,
            ),
        ),
        min_direction_signal_count=2,
    )
    thin_selected = thin[thin["selected_by_calibration"]].iloc[0]

    degraded = backtest.calibration_candidate_search(
        labels,
        [split],
        horizons_weeks=(4,),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="negative_score_le_0",
                negative_max_s_score_after_veto=0.0,
            ),
        ),
        min_direction_signal_count=1,
    )
    degraded_selected = degraded[degraded["selected_by_calibration"]].iloc[0]

    assert thin_selected["candidate_id"] == "negative_score_le_0"
    assert thin_selected["gate_status"] == "rejected_thin_sample"
    assert "thin_sample" in thin_selected["rejection_reasons"]
    assert thin_selected["promotion_label"] == "do not promote"
    assert degraded_selected["candidate_id"] == "negative_score_le_0"
    assert degraded_selected["gate_status"] == "rejected_negative_signal_degraded"
    assert degraded_selected["validation_negative_hit_rate_delta_vs_baseline"] < 0
    assert "negative_signal_degraded" in degraded_selected["rejection_reasons"]
    assert degraded_selected["promotion_label"] == "do not promote"


def test_calibration_candidate_search_rejects_unstable_validation_folds():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(
                [
                    "2020-01-03",
                    "2020-01-10",
                    "2021-01-08",
                    "2021-01-15",
                    "2022-01-07",
                    "2022-01-14",
                ]
            ),
            "ticker": ["XLK", "XLF", "XLK", "XLF", "XLK", "XLF"],
            "positive_signal": [True, True, True, True, True, True],
            "negative_signal": [False, False, False, False, False, False],
            "S_score_after_veto": [1.0, 0.2, 1.0, 0.2, 1.0, 0.2],
            "label_available_4w": [True, True, True, True, True, True],
            "positive_success_4w": [True, False, True, False, False, True],
            "negative_success_4w": [False, False, False, False, False, False],
            "forward_return_4w": [0.08, -0.03, 0.06, -0.02, -0.04, 0.05],
            "forward_excess_return_4w": [0.04, -0.02, 0.03, -0.01, -0.03, 0.02],
            "post_entry_drawdown_4w": [-0.01, -0.05, -0.01, -0.04, -0.08, -0.01],
        }
    )
    splits = [
        backtest.WalkForwardSplit(
            name="fold_01",
            calibration_start=pd.Timestamp("2020-01-01"),
            calibration_end=pd.Timestamp("2020-12-31"),
            validation_start=pd.Timestamp("2021-01-01"),
            validation_end=pd.Timestamp("2021-12-31"),
            final_holdout_start=pd.Timestamp("2023-01-01"),
            final_holdout_end=pd.Timestamp("2023-12-31"),
        ),
        backtest.WalkForwardSplit(
            name="fold_02",
            calibration_start=pd.Timestamp("2021-01-01"),
            calibration_end=pd.Timestamp("2021-12-31"),
            validation_start=pd.Timestamp("2022-01-01"),
            validation_end=pd.Timestamp("2022-12-31"),
            final_holdout_start=pd.Timestamp("2023-01-01"),
            final_holdout_end=pd.Timestamp("2023-12-31"),
        ),
    ]

    candidates = backtest.calibration_candidate_search(
        labels,
        splits,
        horizons_weeks=(4,),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="positive_score_ge_0_8",
                positive_min_s_score_after_veto=0.8,
            ),
        ),
        min_direction_signal_count=1,
    )

    selected = candidates[candidates["selected_by_calibration"]].iloc[0]

    assert selected["candidate_id"] == "positive_score_ge_0_8"
    assert selected["calibration_positive_hit_rate_delta_vs_baseline"] > 0
    assert selected["validation_positive_hit_rate_delta_vs_baseline"] == pytest.approx(0.0)
    assert selected["minimum_validation_fold_hit_rate_delta"] < 0
    assert selected["gate_status"] == "rejected_unstable_folds"
    assert "unstable_folds" in selected["rejection_reasons"]
    assert selected["promotion_label"] == "do not promote"


def test_calibration_candidate_search_excludes_validation_labels_that_mature_in_holdout():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(["2020-01-03", "2021-12-31"]),
            "ticker": ["XLK", "XLK"],
            "positive_signal": [True, True],
            "negative_signal": [False, False],
            "S_score_after_veto": [1.0, 1.0],
            "label_available_4w": [True, True],
            "label_end_date_4w": pd.to_datetime(["2020-01-31", "2022-01-28"]),
            "positive_success_4w": [True, True],
            "negative_success_4w": [False, False],
            "forward_return_4w": [0.06, 0.20],
            "forward_excess_return_4w": [0.03, 0.18],
            "post_entry_drawdown_4w": [-0.01, -0.01],
        }
    )
    split = backtest.WalkForwardSplit(
        name="fold_01",
        calibration_start=pd.Timestamp("2020-01-01"),
        calibration_end=pd.Timestamp("2020-12-31"),
        validation_start=pd.Timestamp("2021-01-01"),
        validation_end=pd.Timestamp("2021-12-31"),
        final_holdout_start=pd.Timestamp("2022-01-01"),
        final_holdout_end=pd.Timestamp("2022-12-31"),
    )

    candidates = backtest.calibration_candidate_search(
        labels,
        [split],
        horizons_weeks=(4,),
        candidate_rules=(
            backtest.CalibrationCandidateRule(candidate_id="baseline"),
            backtest.CalibrationCandidateRule(
                candidate_id="positive_score_ge_0_8",
                positive_min_s_score_after_veto=0.8,
            ),
        ),
        min_direction_signal_count=1,
    )

    selected = candidates[candidates["selected_by_calibration"]].iloc[0]

    assert selected["candidate_id"] == "positive_score_ge_0_8"
    assert selected["validation_positive_signal_available_count"] == 0
    assert selected["final_holdout_evaluated"] is False
    assert selected["final_holdout_rows_used"] == 0
    assert selected["gate_status"] == "rejected_thin_sample"
    assert "thin_sample" in selected["rejection_reasons"]


def test_multi_asset_weights_drift_between_rebalance_dates():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 200.0, 200.0],
            "BBB": [100.0, 100.0, 200.0],
        },
        index=dates,
    )
    target_weights = pd.DataFrame({"AAA": [0.5], "BBB": [0.5]}, index=[dates[0]])

    result = backtest.run_weight_backtest(prices, target_weights)

    assert result.gross_returns.tolist() == pytest.approx([0.5, 1 / 3])
    assert result.period_weights.loc[dates[1], "AAA"] == pytest.approx(0.5)
    assert result.period_weights.loc[dates[2], "AAA"] == pytest.approx(2 / 3)
    assert result.equity.iloc[-1] == pytest.approx(2.0)


def test_target_weights_with_off_calendar_dates_raise_clear_error():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=dates)
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[pd.Timestamp("2024-01-06")])

    with pytest.raises(ValueError, match="Target weight dates must exist in prices index"):
        backtest.run_weight_backtest(prices, target_weights)


def test_performance_metrics_uses_downside_semideviation_for_sortino():
    dates = pd.bdate_range("2024-01-01", periods=5)
    returns = pd.Series([0.10, -0.10, 0.00, 0.20], index=dates[1:])

    metrics = backtest.performance_metrics(returns, periods_per_year=4)

    assert metrics["sortino"] == pytest.approx(2.0)


def test_run_weight_backtest_rejects_empty_prices_and_negative_costs():
    dates = pd.bdate_range("2024-01-01", periods=2)
    prices = pd.DataFrame({"AAA": [100.0, 101.0]}, index=dates)
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])

    with pytest.raises(ValueError, match="prices must contain at least two rows"):
        backtest.run_weight_backtest(pd.DataFrame(), target_weights)

    with pytest.raises(ValueError, match="transaction_cost_bps must be non-negative"):
        backtest.run_weight_backtest(prices, target_weights, transaction_cost_bps=-1.0)


def test_run_weight_backtest_rejects_non_positive_or_non_finite_prices():
    dates = pd.bdate_range("2024-01-01", periods=3)
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])

    zero_prices = pd.DataFrame({"AAA": [0.0, 101.0, 102.0]}, index=dates)
    infinite_prices = pd.DataFrame({"AAA": [100.0, float("inf"), 102.0]}, index=dates)

    with pytest.raises(ValueError, match="prices must be finite and strictly positive"):
        backtest.run_weight_backtest(zero_prices, target_weights)

    with pytest.raises(ValueError, match="prices must be finite and strictly positive"):
        backtest.run_weight_backtest(infinite_prices, target_weights)


def test_run_weight_backtest_rejects_duplicate_price_columns():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame(
        [[100.0, 101.0], [101.0, 102.0], [102.0, 103.0]],
        index=dates,
        columns=["AAA", "AAA"],
    )
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])

    with pytest.raises(ValueError, match="prices columns must be unique"):
        backtest.run_weight_backtest(prices, target_weights)


def test_run_weight_backtest_rejects_non_finite_target_weights():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=dates)
    target_weights = pd.DataFrame({"AAA": [float("inf")]}, index=[dates[0]])

    with pytest.raises(ValueError, match="target_weights must be finite"):
        backtest.run_weight_backtest(prices, target_weights)


def test_run_weight_backtest_rejects_target_tickers_missing_from_prices():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=dates)
    target_weights = pd.DataFrame({"AAA": [0.5], "MISSING": [0.5]}, index=[dates[0]])

    with pytest.raises(ValueError, match="target_weights columns missing from prices"):
        backtest.run_weight_backtest(prices, target_weights)


def test_run_weight_backtest_rejects_duplicate_price_or_target_dates():
    price_dates = pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"])
    duplicate_prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=price_dates)
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[pd.Timestamp("2024-01-01")])

    with pytest.raises(ValueError, match="prices index must be unique"):
        backtest.run_weight_backtest(duplicate_prices, target_weights)

    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=dates)
    duplicate_targets = pd.DataFrame({"AAA": [1.0, 0.0]}, index=[dates[0], dates[0]])

    with pytest.raises(ValueError, match="target_weights index must be unique"):
        backtest.run_weight_backtest(prices, duplicate_targets)


def test_performance_metrics_rejects_invalid_periods_per_year():
    dates = pd.bdate_range("2024-01-01", periods=3)
    returns = pd.Series([0.10, 0.10], index=dates[1:])

    with pytest.raises(ValueError, match="periods_per_year must be positive"):
        backtest.performance_metrics(returns, periods_per_year=0)


def test_performance_metrics_accepts_plain_integer_index_returns():
    returns = pd.Series([0.10, 0.10])

    metrics = backtest.performance_metrics(returns, periods_per_year=2)

    assert metrics["total_return"] == pytest.approx(0.21)


def test_public_helpers_reject_non_finite_scalar_inputs():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 101.0, 102.0]}, index=dates)
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])
    returns = pd.Series([0.10, 0.10], index=dates[1:])

    with pytest.raises(ValueError, match="transaction_cost_bps must be finite"):
        backtest.run_weight_backtest(prices, target_weights, transaction_cost_bps=float("nan"))

    with pytest.raises(ValueError, match="initial_capital must be finite"):
        backtest.run_weight_backtest(prices, target_weights, initial_capital=float("inf"))

    with pytest.raises(ValueError, match="risk_free_rate must be finite"):
        backtest.performance_metrics(returns, risk_free_rate=float("nan"))


def test_close_matrix_prefers_adjusted_close_and_aligns_tickers(ohlcv_frame_factory):
    aaa = ohlcv_frame_factory(days=5, start_price=100.0)
    bbb = ohlcv_frame_factory(days=5, start_price=50.0).drop(columns=["adj_close"])

    out = backtest.close_matrix_from_ohlcv({"BBB": bbb, "AAA": aaa})

    assert list(out.columns) == ["AAA", "BBB"]
    assert out.index.is_monotonic_increasing
    assert out["AAA"].iloc[0] == pytest.approx(aaa["adj_close"].iloc[0])
    assert out["BBB"].iloc[0] == pytest.approx(bbb["close"].iloc[0])


def test_close_matrix_drops_leading_partial_rows_after_alignment(ohlcv_frame_factory):
    aaa = ohlcv_frame_factory(days=5, start="2024-01-01", start_price=100.0)
    bbb = ohlcv_frame_factory(days=5, start="2024-01-03", start_price=50.0)

    out = backtest.close_matrix_from_ohlcv({"AAA": aaa, "BBB": bbb})

    assert out.index[0] == pd.Timestamp("2024-01-03")
    assert not out.isna().any().any()


def test_close_matrix_rejects_duplicate_dates_after_conversion():
    frame = pd.DataFrame(
        {
            "close": [100.0, 101.0],
        },
        index=pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:00"]),
    )

    with pytest.raises(ValueError, match="OHLCV index must be unique"):
        backtest.close_matrix_from_ohlcv({"AAA": frame})


def test_static_weight_benchmark_rebalances_to_requested_weights():
    dates = pd.bdate_range("2024-01-01", periods=3)

    weights = backtest.static_weight_targets(
        dates,
        {"SPY": 0.60, "AGG": 0.40},
    )

    assert list(weights.columns) == ["AGG", "SPY"]
    assert weights.loc[dates[0], "SPY"] == pytest.approx(0.60)
    assert weights.loc[dates[-1], "AGG"] == pytest.approx(0.40)
    assert weights.sum(axis=1).tolist() == pytest.approx([1.0, 1.0, 1.0])


def test_equal_weight_targets_rejects_duplicate_tickers():
    dates = pd.bdate_range("2024-01-01", periods=3)

    with pytest.raises(ValueError, match="tickers must be unique"):
        backtest.equal_weight_targets(dates, ["AAA", "AAA", "BBB"])


def test_sixty_forty_targets_rejects_duplicate_tickers():
    dates = pd.bdate_range("2024-01-01", periods=3)

    with pytest.raises(ValueError, match="equity_ticker and bond_ticker must differ"):
        backtest.sixty_forty_targets(dates, equity_ticker="SPY", bond_ticker="SPY")


def test_run_cost_scenarios_returns_metrics_by_bps():
    dates = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0, 133.1]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])

    scenarios = backtest.run_cost_scenarios(
        prices,
        weights,
        cost_bps_values=[0, 10],
        initial_capital=100.0,
    )

    assert list(scenarios.index) == [0.0, 10.0]
    assert scenarios.loc[0.0, "total_return"] > scenarios.loc[10.0, "total_return"]


def test_macro_condition_mask_uses_past_observations_only():
    dates = pd.bdate_range("2024-01-01", periods=6)
    target_index = pd.DatetimeIndex([dates[1], dates[3], dates[5]])
    series = pd.Series([1.0, 0.5], index=[dates[0], dates[4]])

    mask = backtest.macro_condition_mask(
        series,
        target_index,
        condition="falling",
        lookback_periods=1,
    )

    assert mask.to_dict() == {
        dates[1]: False,
        dates[3]: False,
        dates[5]: True,
    }


def test_macro_condition_mask_applies_availability_lag_before_rebalance_use():
    dates = pd.bdate_range("2024-01-01", periods=8)
    series = pd.Series([1.0, 0.5], index=[dates[0], dates[2]])

    mask = backtest.macro_condition_mask(
        series,
        pd.DatetimeIndex([dates[3], dates[7]]),
        condition="falling",
        lookback_periods=1,
        availability_lag_days=5,
    )

    assert mask.to_dict() == {
        dates[3]: False,
        dates[7]: True,
    }


def test_evaluate_macro_condition_variants_compares_defensive_filter():
    dates = pd.bdate_range("2024-01-01", periods=5)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0, 133.1, 66.55]}, index=dates)
    target_weights = pd.DataFrame({"AAA": [1.0, 1.0]}, index=[dates[0], dates[3]])
    macro_data = {"T10Y2Y": pd.Series([1.0, 0.5], index=[dates[0], dates[2]])}

    summary = backtest.evaluate_macro_condition_variants(
        prices,
        target_weights,
        macro_data,
        rules=[
            backtest.MacroVariantRule(
                name="Curve falling defensive",
                series_id="T10Y2Y",
                condition="falling",
                exposure_multiplier=0.0,
                availability_lag_days=1,
            )
        ],
        transaction_cost_bps=0.0,
        periods_per_year=252,
    )

    assert list(summary["variant"]) == ["Curve falling defensive"]
    row = summary.iloc[0]
    assert row["series_id"] == "T10Y2Y"
    assert row["condition"] == "falling"
    assert row["availability_lag_days"] == 1
    assert row["active_rebalances"] == 1
    assert row["exposure_multiplier"] == pytest.approx(0.0)
    assert row["variant_total_return"] > row["baseline_total_return"]
    assert row["total_return_delta"] > 0.0
    assert row["max_drawdown_delta"] > 0.0


def test_evaluate_macro_condition_variants_adds_validation_evidence_columns():
    dates = pd.bdate_range("2014-12-29", periods=8)
    prices = pd.DataFrame(
        {"AAA": [100.0, 105.0, 110.0, 55.0, 56.0, 57.0, 58.0, 59.0]},
        index=dates,
    )
    target_weights = pd.DataFrame(
        {"AAA": [1.0, 1.0, 1.0, 1.0]},
        index=[dates[0], dates[2], dates[4], dates[6]],
    )
    macro_data = {"T10Y2Y": pd.Series([1.0, 0.5], index=[dates[0], dates[2]])}

    summary = backtest.evaluate_macro_condition_variants(
        prices,
        target_weights,
        macro_data,
        rules=[
            backtest.MacroVariantRule(
                name="Curve falling defensive",
                series_id="T10Y2Y",
                condition="falling",
                exposure_multiplier=0.0,
            )
        ],
        transaction_cost_bps=0.0,
        periods_per_year=252,
    )

    row = summary.iloc[0]
    assert row["active_oos_rebalances"] == 2
    assert row["variant_trade_count"] >= row["baseline_trade_count"]
    assert row["variant_hit_rate"] >= 0.0
    assert row["oos_variant_sharpe"] > row["oos_baseline_sharpe"]
    assert row["oos_max_drawdown_delta"] > 0.0
    assert row["promotion_label"] == "needs more testing"


def test_evaluate_acceptance_gates_compares_oos_to_equal_weight_benchmark():
    report = backtest.evaluate_acceptance_gates(
        strategy_metrics={
            "sharpe": 0.80,
            "max_drawdown": -0.20,
            "annualized_turnover": 2.50,
            "state_transitions_per_ticker_year": 3.0,
        },
        equal_weight_metrics={"max_drawdown": -0.30},
    )

    assert report["oos_sharpe"]["passed"] is True
    assert "strategy OOS Sharpe >= 0.70" in report["oos_sharpe"]["evidence"]
    assert report["max_drawdown"]["passed"] is True
    assert "75% of equal-weight OOS drawdown" in report["max_drawdown"]["evidence"]
    assert report["annualized_turnover"]["passed"] is True
    assert "strategy OOS annualized turnover <= 300%" in report["annualized_turnover"]["evidence"]
    assert report["state_transitions"]["passed"] is True
    assert "historical state transitions per ticker-year <= 4.0" in report["state_transitions"]["evidence"]
    assert report["all_passed"] is True


def test_evaluate_acceptance_gates_requires_explicit_metrics():
    with pytest.raises(ValueError, match="strategy_metrics missing required key"):
        backtest.evaluate_acceptance_gates(
            strategy_metrics={
                "sharpe": 0.80,
                "max_drawdown": -0.20,
                "annualized_turnover": 2.50,
            },
            equal_weight_metrics={"max_drawdown": -0.30},
        )

    with pytest.raises(ValueError, match="equal_weight_metrics missing required key"):
        backtest.evaluate_acceptance_gates(
            strategy_metrics={
                "sharpe": 0.80,
                "max_drawdown": -0.20,
                "annualized_turnover": 2.50,
                "state_transitions_per_ticker_year": 3.0,
            },
            equal_weight_metrics={},
        )


def test_run_cost_scenarios_rejects_empty_cost_list():
    dates = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0, 133.1]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])

    with pytest.raises(ValueError, match="cost_bps_values must contain at least one value"):
        backtest.run_cost_scenarios(prices, weights, cost_bps_values=[])


def test_target_weights_from_scores_uses_selected_tickers_only():
    scores = pd.DataFrame(
        {
            "selected": [True, True, False],
            "S_score_after_veto": [2.0, 1.0, -9.99],
        },
        index=["XLK", "XLF", "XLE"],
    )

    weights = backtest.target_weights_from_scores(scores)

    assert weights.to_dict() == pytest.approx({"XLF": 0.5, "XLK": 0.5})
    assert "XLE" not in weights


def test_weekly_rebalance_dates_returns_friday_index():
    dates = pd.bdate_range("2024-01-01", periods=10)
    prices = pd.DataFrame({"AAA": range(10, 20)}, index=dates)

    out = backtest.weekly_rebalance_dates(prices)

    assert out.tolist() == [pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-12")]


def test_weekly_rebalance_dates_uses_last_actual_trading_day_when_friday_missing():
    dates = pd.bdate_range("2024-03-25", "2024-03-28")
    prices = pd.DataFrame({"AAA": range(10, 14)}, index=dates)

    out = backtest.weekly_rebalance_dates(prices)

    assert out.tolist() == [pd.Timestamp("2024-03-28")]


def test_format_gate_report_includes_pass_fail_lines():
    gates = {
        "oos_sharpe": {
            "name": "Out-of-sample Sharpe",
            "value": 0.8,
            "threshold": 0.7,
            "passed": True,
            "evidence": "strategy OOS Sharpe >= 0.70",
        },
        "max_drawdown": {"name": "Max drawdown", "value": 0.2, "threshold": 0.225, "passed": True},
        "all_passed": True,
    }

    text = backtest.format_gate_report(gates)

    assert "Out-of-sample Sharpe: PASS" in text
    assert "Max drawdown: PASS" in text
    assert "Evidence: strategy OOS Sharpe >= 0.70" in text
    assert "Overall: PASS" in text


def test_format_backtest_report_includes_benchmarks_costs_and_gates():
    strategy_metrics = {
        "total_return": 0.24,
        "cagr": 0.12,
        "sharpe": 0.91,
        "sortino": 1.30,
        "max_drawdown": -0.18,
        "calmar": 0.67,
        "annualized_turnover": 1.20,
    }
    benchmark_metrics = {
        "60/40 SPY/AGG": {"cagr": 0.08, "sharpe": 0.70, "max_drawdown": -0.22},
        "Equal-weight sectors": {"cagr": 0.10, "sharpe": 0.74, "max_drawdown": -0.25},
    }
    cost_scenarios = pd.DataFrame(
        {
            "cagr": [0.121, 0.118],
            "sharpe": [0.91, 0.89],
            "max_drawdown": [-0.18, -0.181],
        },
        index=pd.Index([3.0, 10.0], name="cost_bps"),
    )
    gates = backtest.evaluate_acceptance_gates(
        strategy_metrics={**strategy_metrics, "state_transitions_per_ticker_year": 2.0},
        equal_weight_metrics=benchmark_metrics["Equal-weight sectors"],
    )

    text = backtest.format_backtest_report(
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        cost_scenarios=cost_scenarios,
        gates=gates,
        window_metrics={
            "In-sample": {**strategy_metrics, "total_return": 0.30},
            "Out-of-sample": {**strategy_metrics, "total_return": 0.12, "sharpe": 0.82},
        },
        simulation_summary={
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "rebalance_count": 9,
            "state_ticker_count": 11,
            "selected_ticker_count": 4,
            "state_transition_count": 7,
            "state_transitions_per_ticker_year": 2.75,
        },
        title="Manual Backtest Smoke Report",
    )

    assert "# Manual Backtest Smoke Report" in text
    assert "## Strategy Metrics" in text
    assert "| CAGR | 12.00% |" in text
    assert "## Benchmark Comparison" in text
    assert "| 60/40 SPY/AGG |" in text
    assert "## Cost Sensitivity" in text
    assert "| 10 bps |" in text
    assert "## In-Sample / Out-of-Sample" in text
    assert "OOS starts: 2015-01-01" in text
    assert "| Out-of-sample | 12.00% |" in text
    assert "## Historical Methodology Simulation" in text
    assert "| State transitions per ticker-year | 2.75 |" in text
    assert "## Acceptance Gates" in text
    assert "Out-of-sample Sharpe: PASS" in text


def test_format_backtest_report_includes_macro_variant_table():
    strategy_metrics = {
        "total_return": 0.24,
        "cagr": 0.12,
        "sharpe": 0.91,
        "sortino": 1.30,
        "max_drawdown": -0.18,
        "calmar": 0.67,
        "annualized_turnover": 1.20,
    }
    macro_variants = pd.DataFrame(
        [
            {
                "variant": "Curve falling defensive",
                "series_id": "T10Y2Y",
                "condition": "falling",
                "active_rebalances": 4,
                "baseline_total_return": 0.24,
                "variant_total_return": 0.30,
                "total_return_delta": 0.06,
                "baseline_sharpe": 0.91,
                "variant_sharpe": 1.10,
                "sharpe_delta": 0.19,
                "baseline_max_drawdown": -0.18,
                "variant_max_drawdown": -0.12,
                "max_drawdown_delta": 0.06,
            }
        ]
    )

    text = backtest.format_backtest_report(
        strategy_metrics=strategy_metrics,
        benchmark_metrics={"Methodology": strategy_metrics},
        cost_scenarios=pd.DataFrame(
            {"cagr": [0.12], "sharpe": [0.91], "max_drawdown": [-0.18]},
            index=pd.Index([5.0], name="cost_bps"),
        ),
        gates={"all_passed": True},
        macro_variant_summary=macro_variants,
    )

    assert "## Macro Condition Variants" in text
    assert "Curve falling defensive" in text
    assert "T10Y2Y" in text
    assert "| Curve falling defensive | T10Y2Y | falling | 4 | 6.00% | 0.19 | 6.00% |" in text


def test_format_methodology_report_includes_research_narrative_sections():
    strategy_metrics = {
        "total_return": 0.24,
        "cagr": 0.12,
        "sharpe": 0.91,
        "sortino": 1.30,
        "max_drawdown": -0.18,
        "calmar": 0.67,
        "annualized_turnover": 1.20,
    }
    benchmark_metrics = {
        "Methodology": strategy_metrics,
        "60/40 SPY/AGG": {"cagr": 0.08, "sharpe": 0.70, "max_drawdown": -0.22},
        "Equal-weight sectors": {"cagr": 0.10, "sharpe": 0.74, "max_drawdown": -0.25},
    }
    gates = backtest.evaluate_acceptance_gates(
        strategy_metrics={**strategy_metrics, "state_transitions_per_ticker_year": 2.0},
        equal_weight_metrics=benchmark_metrics["Equal-weight sectors"],
    )

    text = backtest.format_methodology_report(
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        gates=gates,
        window_metrics={
            "Methodology full period": strategy_metrics,
            "Methodology out-of-sample": {**strategy_metrics, "total_return": 0.12},
        },
        simulation_summary={
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "rebalance_count": 9,
            "state_ticker_count": 11,
            "selected_ticker_count": 4,
            "state_transition_count": 7,
            "state_transitions_per_ticker_year": 2.75,
        },
    )

    assert "# Historical Methodology Backtest Report" in text
    assert "## Executive Summary" in text
    assert "## Methodology Under Test" in text
    assert "## Evidence Tables" in text
    assert "## Acceptance Gates" in text
    assert "## Limitations And Next Work" in text
    assert "research evidence, not investment advice" in text
    assert "provider-backed historical flow is neutral" in text


def test_equity_frame_combines_named_results_on_date_index():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])
    result = backtest.run_weight_backtest(prices, weights, initial_capital=100.0)

    frame = backtest.equity_frame({"Strategy": result})

    assert list(frame.columns) == ["Strategy"]
    assert frame.index.name == "date"
    assert frame.iloc[0, 0] == pytest.approx(100.0)
    assert frame.iloc[-1, 0] == pytest.approx(121.0)


def test_state_transition_rate_counts_changes_per_ticker_year():
    dates = pd.bdate_range("2024-01-01", periods=4)
    states = pd.DataFrame(
        {
            "AAA": ["HOLD", "HOLD", "WARNING", "WARNING"],
            "BBB": ["EXIT", "HOLD", "HOLD", "STAGE_2_BULLISH"],
        },
        index=dates,
    )

    rate = backtest.state_transition_rate(states, periods_per_year=4)

    assert rate == pytest.approx(2.0)


def test_state_transition_rate_uses_observed_intervals_for_sparse_state_history():
    dates = pd.bdate_range("2024-01-01", periods=5)
    states = pd.DataFrame(
        {
            "AAA": ["HOLD", "WARNING", None, None, None],
            "BBB": [None, None, None, "EXIT", "HOLD"],
        },
        index=dates,
    )

    rate = backtest.state_transition_rate(states, periods_per_year=4)

    assert rate == pytest.approx(4.0)


def test_historical_simulation_summary_reports_rebalance_state_and_selection_evidence():
    dates = pd.bdate_range("2024-01-01", periods=4)
    targets = backtest.HistoricalSignalTargets(
        target_weights=pd.DataFrame(
            {"AAA": [1.0, 0.5, 0.0, 0.0], "BBB": [0.0, 0.5, 1.0, 1.0]},
            index=dates,
        ),
        states=pd.DataFrame(
            {
                "AAA": ["HOLD", "HOLD", "WARNING", "WARNING"],
                "BBB": ["EXIT", "HOLD", "HOLD", "HOLD"],
            },
            index=dates,
        ),
        snapshots={},
    )

    summary = backtest.historical_simulation_summary(targets, periods_per_year=4)

    assert summary["rebalance_count"] == 4
    assert summary["state_ticker_count"] == 2
    assert summary["selected_ticker_count"] == 2
    assert summary["state_transition_count"] == 2
    assert summary["state_transitions_per_ticker_year"] == pytest.approx(4 / 3)


def test_normalized_equity_frame_rebases_each_series_to_one():
    dates = pd.bdate_range("2024-01-01", periods=3)
    equity = pd.DataFrame(
        {
            "Methodology": [100.0, 110.0, 121.0],
            "Benchmark": [50.0, 45.0, 60.0],
        },
        index=dates,
    )

    normalized = backtest.normalized_equity_frame(equity)

    assert normalized.index.name == "date"
    assert normalized.loc[dates[0]].to_dict() == pytest.approx(
        {"Methodology": 1.0, "Benchmark": 1.0}
    )
    assert normalized.loc[dates[-1]].to_dict() == pytest.approx(
        {"Methodology": 1.21, "Benchmark": 1.20}
    )


def test_drawdown_frame_reports_percent_below_running_high():
    dates = pd.bdate_range("2024-01-01", periods=4)
    equity = pd.DataFrame(
        {
            "Methodology": [100.0, 120.0, 90.0, 126.0],
            "Benchmark": [50.0, 40.0, 60.0, 54.0],
        },
        index=dates,
    )

    drawdown = backtest.drawdown_frame(equity)

    assert drawdown.index.name == "date"
    assert drawdown["Methodology"].tolist() == pytest.approx([0.0, 0.0, -0.25, 0.0])
    assert drawdown["Benchmark"].tolist() == pytest.approx([0.0, -0.20, 0.0, -0.10])


def test_build_historical_methodology_targets_slices_inputs_without_lookahead():
    dates = pd.bdate_range("2024-01-01", periods=8)
    ohlcv = {
        "AAA": pd.DataFrame({"close": range(100, 108)}, index=dates),
        "BBB": pd.DataFrame({"close": range(200, 208)}, index=dates),
        "SPY": pd.DataFrame({"close": range(300, 308)}, index=dates),
        "BIL": pd.DataFrame({"close": range(400, 408)}, index=dates),
    }
    rebalance_dates = pd.DatetimeIndex([dates[4], dates[7]])
    observed_max_dates = []

    def fake_score_snapshot(snapshot_ohlcv, phase, bench_ticker, bil_ticker):
        del phase, bench_ticker, bil_ticker
        max_date = max(frame.index.max() for frame in snapshot_ohlcv.values())
        observed_max_dates.append(max_date)
        select_aaa = max_date == dates[4]
        return pd.DataFrame(
            {
                "selected": [select_aaa, not select_aaa],
                "stage": [2, 4],
                "above_30wma": [True, False],
                "ma_slope_pos": [True, False],
                "mansfield_rs": [1.0, -1.0],
                "antonacci": [1, 0],
                "rrg_quadrant": ["Leading", "Lagging"],
                "breadth_50d": [0.70, 0.30],
                "cmf21": [0.10, -0.20],
                "rvol": [1.2, 1.1],
                "etf_flow_5d_pct": [0.2, -2.0],
                "block_up_ratio": [1.1, 0.6],
                "obv_divergence": [False, True],
                "dist_days_25": [0, 5],
            },
            index=["AAA", "BBB"],
        )

    result = backtest.build_historical_methodology_targets(
        ohlcv,
        rebalance_dates=rebalance_dates,
        score_snapshot_fn=fake_score_snapshot,
        phase="MID",
    )

    assert observed_max_dates == [dates[4], dates[7]]
    assert result.target_weights.loc[dates[4]].to_dict() == pytest.approx({"AAA": 1.0, "BBB": 0.0})
    assert result.target_weights.loc[dates[7]].to_dict() == pytest.approx({"AAA": 0.0, "BBB": 1.0})
    assert result.states.loc[dates[4], "AAA"] == "STAGE_2_BULLISH"
    assert result.states.loc[dates[4], "BBB"] == "BEARISH_STAGE_4"


def test_build_historical_methodology_targets_uses_pure_scoring_without_state_writes(
    monkeypatch,
    market_ohlcv,
):
    from src import scoring

    def fail_apply_state_machine(scored_df):
        raise AssertionError("historical backtest must not write state.json")

    monkeypatch.setattr(scoring, "apply_state_machine", fail_apply_state_machine)
    last_date = market_ohlcv["SPY"].index[-1]

    result = backtest.build_historical_methodology_targets(
        market_ohlcv,
        rebalance_dates=[last_date],
        phase="MID",
    )

    assert result.target_weights.index.tolist() == [last_date]
    assert "SPY" not in result.target_weights.columns
    assert set(result.states.index) == {last_date}


def test_historical_methodology_targets_do_not_fetch_provider_flow(
    monkeypatch,
    market_ohlcv,
):
    from src import flow

    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)
    monkeypatch.setattr(flow, "MASSIVE_TRADES_STUB_MODE", False)
    monkeypatch.setattr(flow, "FINRA_ATS_STUB_MODE", False)
    monkeypatch.setattr(flow, "FINRA_SHORT_INTEREST_STUB_MODE", False)
    monkeypatch.setattr(flow, "SEC_13F_STUB_MODE", False)

    def fail_fetch(ticker):
        raise AssertionError("historical target building must stay OHLCV-only")

    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", fail_fetch)
    monkeypatch.setattr(flow, "_fetch_massive_stock_trades", fail_fetch)
    monkeypatch.setattr(flow, "_fetch_finra_ats_weekly_summary", fail_fetch)
    monkeypatch.setattr(flow, "_fetch_finra_short_interest", fail_fetch)
    last_date = market_ohlcv["SPY"].index[-1]

    result = backtest.build_historical_methodology_targets(
        market_ohlcv,
        rebalance_dates=[last_date],
        phase="MID",
    )

    assert result.target_weights.index.tolist() == [last_date]
    assert flow.ETF_PRIMARY_FLOW_STUB_MODE is False
    assert flow.MASSIVE_TRADES_STUB_MODE is False
    assert flow.FINRA_ATS_STUB_MODE is False
    assert flow.FINRA_SHORT_INTEREST_STUB_MODE is False
    assert flow.SEC_13F_STUB_MODE is False
