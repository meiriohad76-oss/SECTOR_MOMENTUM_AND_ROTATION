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
    assert report["max_drawdown"]["passed"] is True
    assert report["annualized_turnover"]["passed"] is True
    assert report["state_transitions"]["passed"] is True
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
        "oos_sharpe": {"name": "Out-of-sample Sharpe", "value": 0.8, "threshold": 0.7, "passed": True},
        "max_drawdown": {"name": "Max drawdown", "value": 0.2, "threshold": 0.225, "passed": True},
        "all_passed": True,
    }

    text = backtest.format_gate_report(gates)

    assert "Out-of-sample Sharpe: PASS" in text
    assert "Max drawdown: PASS" in text
    assert "Overall: PASS" in text
