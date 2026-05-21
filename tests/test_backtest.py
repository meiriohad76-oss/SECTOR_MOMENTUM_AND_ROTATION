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

    def fail_fetch(ticker):
        raise AssertionError("historical target building must stay OHLCV-only")

    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", fail_fetch)
    last_date = market_ohlcv["SPY"].index[-1]

    result = backtest.build_historical_methodology_targets(
        market_ohlcv,
        rebalance_dates=[last_date],
        phase="MID",
    )

    assert result.target_weights.index.tolist() == [last_date]
    assert flow.ETF_PRIMARY_FLOW_STUB_MODE is False
