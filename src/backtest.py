"""Pure backtest accounting helpers.

This module has no Streamlit imports, no network calls, and no state-file
writes. It accepts already-loaded prices and target weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestResult:
    prices: pd.DataFrame
    target_weights: pd.DataFrame
    period_weights: pd.DataFrame
    gross_returns: pd.Series
    turnover: pd.Series
    costs: pd.Series
    net_returns: pd.Series
    equity: pd.Series
    metrics: dict[str, float]


@dataclass(frozen=True)
class HistoricalSignalTargets:
    target_weights: pd.DataFrame
    states: pd.DataFrame
    snapshots: dict[pd.Timestamp, pd.DataFrame]


@dataclass(frozen=True)
class MacroVariantRule:
    name: str
    series_id: str
    condition: str
    exposure_multiplier: float = 0.0
    threshold: float = 0.0
    lookback_periods: int = 1
    availability_lag_days: int = 0


ScoreSnapshotFn = Callable[[dict[str, pd.DataFrame], str, str, str], pd.DataFrame]


def _finite_scalar(name: str, value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    out = prices.copy()
    out.index = pd.to_datetime(out.index)
    if not out.index.is_unique:
        raise ValueError("prices index must be unique")
    if not out.columns.is_unique:
        raise ValueError("prices columns must be unique")
    out = out.sort_index()
    out = out.apply(pd.to_numeric, errors="coerce")
    out = out.dropna(how="all").ffill()
    finite = np.isfinite(out.to_numpy(dtype=float))
    positive = out.to_numpy(dtype=float) > 0
    if not finite.all() or not positive.all():
        raise ValueError("prices must be finite and strictly positive")
    return out


def _prepare_target_weights(prices: pd.DataFrame, target_weights: pd.DataFrame) -> pd.DataFrame:
    weights = target_weights.copy()
    weights.index = pd.to_datetime(weights.index)
    if not weights.index.is_unique:
        raise ValueError("target_weights index must be unique")
    weights = weights.sort_index()
    missing_dates = weights.index.difference(prices.index)
    if len(missing_dates):
        raise ValueError("Target weight dates must exist in prices index")
    missing_columns = weights.columns.difference(prices.columns)
    if len(missing_columns):
        raise ValueError("target_weights columns missing from prices")
    weights = weights.reindex(columns=prices.columns, fill_value=0.0).fillna(0.0)
    weights = weights.apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(weights.to_numpy(dtype=float)).all():
        raise ValueError("target_weights must be finite")
    row_abs = weights.abs().sum(axis=1)
    over_allocated = row_abs > 1.0
    if over_allocated.any():
        weights.loc[over_allocated] = weights.loc[over_allocated].div(row_abs.loc[over_allocated], axis=0)
    return weights


def _simulate_periods(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    transaction_cost_bps: float,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    asset_returns = prices.pct_change().iloc[1:].fillna(0.0)
    current_weights = pd.Series(0.0, index=prices.columns, dtype=float)
    period_weight_rows = []
    gross_returns = []
    turnover = []
    costs = []
    cost_rate = transaction_cost_bps / 10_000.0

    for idx, (period_date, returns_row) in enumerate(asset_returns.iterrows(), start=1):
        signal_date = prices.index[idx - 1]
        period_turnover = 0.0
        if signal_date in target_weights.index:
            target = target_weights.loc[signal_date].astype(float)
            period_turnover = float((target - current_weights).abs().sum())
            current_weights = target.copy()

        period_weight_rows.append(current_weights.copy())
        period_gross = float((current_weights * returns_row).sum())
        gross_returns.append(period_gross)
        turnover.append(period_turnover)
        costs.append(period_turnover * cost_rate)

        denominator = 1.0 + period_gross
        if denominator > 0:
            current_weights = current_weights * (1.0 + returns_row) / denominator
        else:
            current_weights = current_weights * 0.0

    index = asset_returns.index
    period_weights = pd.DataFrame(period_weight_rows, index=index, columns=prices.columns)
    return (
        period_weights,
        pd.Series(gross_returns, index=index),
        pd.Series(turnover, index=index),
        pd.Series(costs, index=index),
    )


def equity_curve(returns: pd.Series, initial_capital: float = 1.0) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype=float)
    capital = _finite_scalar("initial_capital", initial_capital)
    if capital <= 0:
        raise ValueError("initial_capital must be positive")
    first_index = returns.index[0]
    try:
        base_index = first_index - pd.Timedelta(nanoseconds=1)
    except TypeError:
        try:
            base_index = first_index - 1
        except TypeError:
            base_index = "__initial__"
    base = pd.Series([capital], index=[base_index])
    curve = capital * (1.0 + returns).cumprod()
    return pd.concat([base, curve])


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def performance_metrics(
    returns: pd.Series,
    equity: Optional[pd.Series] = None,
    turnover: Optional[pd.Series] = None,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    periods = _finite_scalar("periods_per_year", periods_per_year)
    if periods <= 0:
        raise ValueError("periods_per_year must be positive")
    risk_free = _finite_scalar("risk_free_rate", risk_free_rate)
    returns = returns.astype(float).dropna()
    if returns.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "calmar": 0.0,
            "average_turnover": 0.0,
            "annualized_turnover": 0.0,
        }
    if equity is None:
        equity = equity_curve(returns)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) else 0.0
    years = max(len(returns) / periods, 1 / periods)
    cagr = float((1.0 + total_return) ** (1.0 / years) - 1.0) if total_return > -1 else -1.0
    volatility = float(returns.std(ddof=0) * np.sqrt(periods)) if len(returns) else 0.0
    excess = returns - risk_free / periods
    excess_std = excess.std(ddof=0)
    sharpe = float(excess.mean() / excess_std * np.sqrt(periods)) if excess_std else 0.0
    downside = np.minimum(excess, 0.0)
    downside_deviation = float(np.sqrt(np.mean(np.square(downside)))) if len(downside) else 0.0
    sortino = float(excess.mean() / downside_deviation * np.sqrt(periods)) if downside_deviation else 0.0
    mdd = max_drawdown(equity)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0
    average_turnover = float(turnover.mean()) if turnover is not None and len(turnover) else 0.0
    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": calmar,
        "average_turnover": average_turnover,
        "annualized_turnover": average_turnover * periods,
    }


def split_backtest_metrics(
    result: BacktestResult,
    oos_start: str | pd.Timestamp = "2015-01-01",
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> dict[str, dict[str, float]]:
    start = pd.Timestamp(oos_start)

    def metrics_for(mask: pd.Series) -> dict[str, float]:
        returns = result.net_returns.loc[mask].astype(float)
        turnover = result.turnover.reindex(returns.index).fillna(0.0)
        return performance_metrics(
            returns,
            turnover=turnover,
            periods_per_year=periods_per_year,
        )

    full_mask = pd.Series(True, index=result.net_returns.index)
    in_sample_mask = pd.Series(result.net_returns.index < start, index=result.net_returns.index)
    oos_mask = pd.Series(result.net_returns.index >= start, index=result.net_returns.index)
    return {
        "Full period": metrics_for(full_mask),
        "In-sample": metrics_for(in_sample_mask),
        "Out-of-sample": metrics_for(oos_mask),
    }


def _positive_return_rate(returns: pd.Series) -> float:
    values = returns.astype(float).dropna()
    if values.empty:
        return 0.0
    return float((values > 0.0).mean())


def _turnover_trade_count(turnover: pd.Series) -> int:
    if turnover is None or len(turnover) == 0:
        return 0
    values = turnover.astype(float).abs().dropna()
    return int((values > 1e-12).sum())


def _result_validation_stats(
    result: BacktestResult,
    mask: pd.Series | None = None,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> dict[str, float | int]:
    if mask is None:
        returns = result.net_returns.astype(float)
    else:
        returns = result.net_returns.loc[mask].astype(float)
    turnover = result.turnover.reindex(returns.index).fillna(0.0)
    stats = performance_metrics(
        returns,
        turnover=turnover,
        periods_per_year=periods_per_year,
    )
    stats["hit_rate"] = _positive_return_rate(returns)
    stats["trade_count"] = _turnover_trade_count(turnover)
    return stats


def run_weight_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    transaction_cost_bps: float = 0.0,
    initial_capital: float = 1.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> BacktestResult:
    cost_bps = _finite_scalar("transaction_cost_bps", transaction_cost_bps)
    capital = _finite_scalar("initial_capital", initial_capital)
    periods = _finite_scalar("periods_per_year", periods_per_year)
    if cost_bps < 0:
        raise ValueError("transaction_cost_bps must be non-negative")
    if capital <= 0:
        raise ValueError("initial_capital must be positive")
    if periods <= 0:
        raise ValueError("periods_per_year must be positive")
    clean_prices = _clean_prices(prices)
    if len(clean_prices) < 2 or clean_prices.shape[1] == 0:
        raise ValueError("prices must contain at least two rows and one column")
    clean_weights = _prepare_target_weights(clean_prices, target_weights)
    weights, gross_returns, turnover, costs = _simulate_periods(
        clean_prices,
        clean_weights,
        cost_bps,
    )
    net_returns = (1.0 - costs) * (1.0 + gross_returns) - 1.0
    equity = pd.concat(
        [
            pd.Series([capital], index=[clean_prices.index[0]]),
            capital * (1.0 + net_returns).cumprod(),
        ]
    )
    metrics = performance_metrics(
        net_returns,
        equity=equity,
        turnover=turnover,
        periods_per_year=periods,
    )
    return BacktestResult(
        prices=clean_prices,
        target_weights=clean_weights,
        period_weights=weights,
        gross_returns=gross_returns,
        turnover=turnover,
        costs=costs,
        net_returns=net_returns,
        equity=equity,
        metrics=metrics,
    )


def close_matrix_from_ohlcv(ohlcv: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = {}
    for ticker in sorted(ohlcv):
        frame = ohlcv[ticker]
        if frame.empty:
            continue
        column = "adj_close" if "adj_close" in frame.columns else "close"
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        values.index = pd.to_datetime(values.index)
        if not values.index.is_unique:
            raise ValueError("OHLCV index must be unique")
        series[ticker] = values.sort_index()
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index().ffill().dropna(how="any")


def static_weight_targets(index: pd.DatetimeIndex, weights: dict[str, float]) -> pd.DataFrame:
    columns = sorted(weights)
    frame = pd.DataFrame(index=pd.to_datetime(index), columns=columns, dtype=float)
    for ticker in columns:
        frame[ticker] = _finite_scalar(f"weight for {ticker}", weights[ticker])
    if not frame.index.is_unique:
        raise ValueError("target index must be unique")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("weights must be finite")
    if (frame < 0).any().any():
        raise ValueError("weights must be non-negative")
    row_sum = frame.abs().sum(axis=1)
    over_allocated = row_sum > 1.0
    if over_allocated.any():
        frame.loc[over_allocated] = frame.loc[over_allocated].div(row_sum.loc[over_allocated], axis=0)
    return frame.fillna(0.0)


def sixty_forty_targets(
    index: pd.DatetimeIndex,
    equity_ticker: str = "SPY",
    bond_ticker: str = "AGG",
) -> pd.DataFrame:
    if equity_ticker == bond_ticker:
        raise ValueError("equity_ticker and bond_ticker must differ")
    return static_weight_targets(index, {equity_ticker: 0.60, bond_ticker: 0.40})


def equal_weight_targets(index: pd.DatetimeIndex, tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame(index=pd.to_datetime(index))
    if len(set(tickers)) != len(tickers):
        raise ValueError("tickers must be unique")
    weight = 1.0 / len(tickers)
    return static_weight_targets(index, {ticker: weight for ticker in tickers})


def run_cost_scenarios(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps_values: Optional[list[int | float]] = None,
    initial_capital: float = 1.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.DataFrame:
    if cost_bps_values is None:
        cost_bps_values = [3, 5, 10]
    if not cost_bps_values:
        raise ValueError("cost_bps_values must contain at least one value")
    rows = []
    for cost_bps in cost_bps_values:
        result = run_weight_backtest(
            prices,
            target_weights,
            transaction_cost_bps=float(cost_bps),
            initial_capital=initial_capital,
            periods_per_year=periods_per_year,
        )
        row = {"cost_bps": float(cost_bps), **result.metrics}
        rows.append(row)
    return pd.DataFrame(rows).set_index("cost_bps")


def _clean_macro_series(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").dropna()
    values.index = pd.to_datetime(values.index)
    if values.index.tz is not None:
        values.index = values.index.tz_convert(None)
    values = values.sort_index()
    if not values.index.is_unique:
        values = values.groupby(level=0).last()
    return values


def _macro_condition_values(
    series: pd.Series,
    condition: str,
    threshold: float,
    lookback_periods: int,
) -> pd.Series:
    lookback = int(_finite_scalar("lookback_periods", lookback_periods))
    if lookback <= 0:
        raise ValueError("lookback_periods must be positive")
    threshold_value = _finite_scalar("threshold", threshold)
    normalized = str(condition).strip().lower()
    if normalized in {"rising", "falling", "flat"}:
        delta = series.diff(lookback)
        if normalized == "rising":
            return delta > threshold_value
        if normalized == "falling":
            return delta < -threshold_value
        return delta.abs() <= threshold_value
    if normalized == "above":
        return series > threshold_value
    if normalized == "below":
        return series < threshold_value
    if normalized == "positive":
        return series > 0.0
    if normalized == "negative":
        return series < 0.0
    raise ValueError(f"unsupported macro condition: {condition}")


def macro_condition_mask(
    series: pd.Series,
    target_index: pd.DatetimeIndex | Sequence[pd.Timestamp],
    condition: str,
    threshold: float = 0.0,
    lookback_periods: int = 1,
    availability_lag_days: int = 0,
) -> pd.Series:
    values = _clean_macro_series(series)
    target_dates = pd.DatetimeIndex(pd.to_datetime(target_index))
    if target_dates.tz is not None:
        target_dates = target_dates.tz_convert(None)
    if values.empty or len(target_dates) == 0:
        return pd.Series(False, index=target_dates, dtype=bool)

    lag_days = int(_finite_scalar("availability_lag_days", availability_lag_days))
    if lag_days < 0:
        raise ValueError("availability_lag_days must be non-negative")
    condition_values = _macro_condition_values(values, condition, threshold, lookback_periods).fillna(False)
    if lag_days:
        condition_values = condition_values.copy()
        condition_values.index = condition_values.index + pd.Timedelta(days=lag_days)
    aligned_index = condition_values.index.union(target_dates).sort_values()
    aligned = condition_values.reindex(aligned_index).ffill().reindex(target_dates).fillna(False)
    return aligned.astype(bool)


def _macro_adjusted_targets(
    target_weights: pd.DataFrame,
    mask: pd.Series,
    exposure_multiplier: float,
) -> pd.DataFrame:
    multiplier = _finite_scalar("exposure_multiplier", exposure_multiplier)
    if multiplier < 0 or multiplier > 1:
        raise ValueError("exposure_multiplier must be between 0 and 1")
    adjusted = target_weights.copy()
    adjusted.index = pd.to_datetime(adjusted.index)
    aligned_mask = mask.reindex(adjusted.index).fillna(False).astype(bool)
    adjusted.loc[aligned_mask] = adjusted.loc[aligned_mask] * multiplier
    return adjusted


def _variant_metric_row(
    rule: MacroVariantRule,
    mask: pd.Series,
    baseline: BacktestResult,
    variant: BacktestResult,
    periods_per_year: int,
    oos_start: str | pd.Timestamp,
) -> dict[str, float | int | str]:
    start = pd.Timestamp(oos_start)
    oos_mask = pd.Series(baseline.net_returns.index >= start, index=baseline.net_returns.index)
    in_sample_mask = pd.Series(baseline.net_returns.index < start, index=baseline.net_returns.index)
    active_oos = mask.loc[mask.index >= start]
    active_in_sample = mask.loc[mask.index < start]
    baseline_full = _result_validation_stats(baseline, periods_per_year=periods_per_year)
    variant_full = _result_validation_stats(variant, periods_per_year=periods_per_year)
    baseline_in_sample = _result_validation_stats(
        baseline,
        mask=in_sample_mask,
        periods_per_year=periods_per_year,
    )
    variant_in_sample = _result_validation_stats(
        variant,
        mask=in_sample_mask,
        periods_per_year=periods_per_year,
    )
    baseline_oos = _result_validation_stats(
        baseline,
        mask=oos_mask,
        periods_per_year=periods_per_year,
    )
    variant_oos = _result_validation_stats(
        variant,
        mask=oos_mask,
        periods_per_year=periods_per_year,
    )

    row = {
        "variant": rule.name,
        "series_id": rule.series_id,
        "condition": rule.condition,
        "threshold": float(rule.threshold),
        "lookback_periods": int(rule.lookback_periods),
        "availability_lag_days": int(rule.availability_lag_days),
        "exposure_multiplier": float(rule.exposure_multiplier),
        "active_rebalances": int(mask.sum()),
        "active_in_sample_rebalances": int(active_in_sample.sum()),
        "active_oos_rebalances": int(active_oos.sum()),
    }
    _add_variant_metric_fields(row, "", baseline_full, variant_full)
    _add_variant_metric_fields(row, "in_sample_", baseline_in_sample, variant_in_sample)
    _add_variant_metric_fields(row, "oos_", baseline_oos, variant_oos)
    row["promotion_label"] = macro_variant_promotion_label(row)
    return row


def _add_variant_metric_fields(
    row: dict[str, float | int | str],
    prefix: str,
    baseline_stats: dict[str, float | int],
    variant_stats: dict[str, float | int],
) -> None:
    for metric in [
        "total_return",
        "cagr",
        "sharpe",
        "max_drawdown",
        "annualized_turnover",
        "hit_rate",
        "trade_count",
    ]:
        baseline_value = baseline_stats[metric]
        variant_value = variant_stats[metric]
        row[f"{prefix}baseline_{metric}"] = float(baseline_value)
        row[f"{prefix}variant_{metric}"] = float(variant_value)
        row[f"{prefix}{metric}_delta"] = float(variant_value) - float(baseline_value)


def macro_variant_promotion_label(
    row: dict[str, float | int | str],
    min_active_oos_rebalances: int = 20,
    min_oos_sharpe_delta: float = 0.10,
) -> str:
    active_oos = int(row.get("active_oos_rebalances", 0))
    if active_oos < min_active_oos_rebalances:
        return "needs more testing"
    oos_sharpe_delta = _finite_scalar("oos_sharpe_delta", row.get("oos_sharpe_delta", 0.0))
    oos_cagr_delta = _finite_scalar("oos_cagr_delta", row.get("oos_cagr_delta", 0.0))
    oos_drawdown_delta = _finite_scalar("oos_max_drawdown_delta", row.get("oos_max_drawdown_delta", 0.0))
    full_sharpe_delta = _finite_scalar("sharpe_delta", row.get("sharpe_delta", 0.0))
    if (
        oos_sharpe_delta >= min_oos_sharpe_delta
        and oos_cagr_delta >= 0.0
        and oos_drawdown_delta >= 0.0
        and full_sharpe_delta >= 0.0
    ):
        return "candidate"
    if oos_sharpe_delta <= 0.0 and oos_cagr_delta <= 0.0 and oos_drawdown_delta <= 0.0:
        return "do not promote"
    return "needs more testing"


def evaluate_macro_condition_variants(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    macro_data: dict[str, pd.Series],
    rules: Sequence[MacroVariantRule],
    transaction_cost_bps: float = 5.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    oos_start: str | pd.Timestamp = "2015-01-01",
) -> pd.DataFrame:
    if not rules:
        return pd.DataFrame()
    baseline = run_weight_backtest(
        prices,
        target_weights,
        transaction_cost_bps=transaction_cost_bps,
        periods_per_year=periods_per_year,
    )
    rows = []
    for rule in rules:
        series = macro_data.get(rule.series_id)
        if series is None:
            continue
        mask = macro_condition_mask(
            series,
            target_weights.index,
            condition=rule.condition,
            threshold=rule.threshold,
            lookback_periods=rule.lookback_periods,
            availability_lag_days=rule.availability_lag_days,
        )
        if not bool(mask.any()):
            continue
        adjusted_targets = _macro_adjusted_targets(
            target_weights,
            mask,
            exposure_multiplier=rule.exposure_multiplier,
        )
        variant = run_weight_backtest(
            prices,
            adjusted_targets,
            transaction_cost_bps=transaction_cost_bps,
            periods_per_year=periods_per_year,
        )
        rows.append(
            _variant_metric_row(
                rule,
                mask,
                baseline,
                variant,
                periods_per_year=periods_per_year,
                oos_start=oos_start,
            )
        )
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    promotion_rank = {"candidate": 0, "needs more testing": 1, "do not promote": 2}
    frame["_promotion_rank"] = frame["promotion_label"].map(promotion_rank).fillna(9)
    return (
        frame.sort_values(
            ["_promotion_rank", "oos_sharpe_delta", "oos_cagr_delta", "sharpe_delta"],
            ascending=[True, False, False, False],
        )
        .drop(columns=["_promotion_rank"])
        .reset_index(drop=True)
    )


def _required_metric(metrics: dict[str, float], key: str, label: str) -> float:
    if key not in metrics:
        raise ValueError(f"{label} missing required key: {key}")
    return _finite_scalar(f"{label} {key}", metrics[key])


def _gate(
    name: str,
    value: float,
    threshold: float,
    passed: bool,
    evidence: str = "",
) -> dict[str, float | bool | str]:
    return {
        "name": name,
        "value": float(value),
        "threshold": float(threshold),
        "passed": bool(passed),
        "evidence": str(evidence),
    }


def evaluate_acceptance_gates(
    strategy_metrics: dict[str, float],
    equal_weight_metrics: dict[str, float],
    min_oos_sharpe: float = 0.70,
    max_drawdown_ratio: float = 0.75,
    max_annualized_turnover: float = 3.0,
    max_state_transitions_per_ticker_year: float = 4.0,
) -> dict[str, dict | bool]:
    sharpe = _required_metric(strategy_metrics, "sharpe", "strategy_metrics")
    strategy_dd = abs(_required_metric(strategy_metrics, "max_drawdown", "strategy_metrics"))
    annualized_turnover = _required_metric(strategy_metrics, "annualized_turnover", "strategy_metrics")
    transitions = _required_metric(strategy_metrics, "state_transitions_per_ticker_year", "strategy_metrics")
    benchmark_dd = abs(_required_metric(equal_weight_metrics, "max_drawdown", "equal_weight_metrics"))
    max_allowed_dd = benchmark_dd * max_drawdown_ratio
    gates = {
        "oos_sharpe": _gate(
            "Out-of-sample Sharpe",
            sharpe,
            min_oos_sharpe,
            sharpe >= min_oos_sharpe,
            f"strategy OOS Sharpe >= {min_oos_sharpe:.2f}",
        ),
        "max_drawdown": _gate(
            "Max drawdown",
            strategy_dd,
            max_allowed_dd,
            strategy_dd <= max_allowed_dd,
            (
                "absolute strategy OOS drawdown <= "
                f"{max_drawdown_ratio * 100:.0f}% of equal-weight OOS drawdown "
                f"({benchmark_dd:.4f})"
            ),
        ),
        "annualized_turnover": _gate(
            "Annualized turnover",
            annualized_turnover,
            max_annualized_turnover,
            annualized_turnover <= max_annualized_turnover,
            f"strategy OOS annualized turnover <= {max_annualized_turnover * 100:.0f}%",
        ),
        "state_transitions": _gate(
            "State transitions per ticker-year",
            transitions,
            max_state_transitions_per_ticker_year,
            transitions <= max_state_transitions_per_ticker_year,
            (
                "historical state transitions per ticker-year <= "
                f"{max_state_transitions_per_ticker_year:.1f}"
            ),
        ),
    }
    gates["all_passed"] = all(item["passed"] for item in gates.values() if isinstance(item, dict))
    return gates


def target_weights_from_scores(scored_df: pd.DataFrame) -> pd.Series:
    if scored_df.empty or "selected" not in scored_df.columns:
        return pd.Series(dtype=float)
    selected = scored_df[scored_df["selected"]].copy()
    if selected.empty:
        return pd.Series(dtype=float)
    weight = 1.0 / len(selected)
    return pd.Series(weight, index=selected.index, dtype=float).sort_index()


def methodology_score_snapshot(
    ohlcv: dict[str, pd.DataFrame],
    phase: str = "MID",
    bench_ticker: str = "SPY",
    bil_ticker: str = "BIL",
) -> pd.DataFrame:
    """Score one historical snapshot without importing app.py or writing state."""
    from . import flow, indicators, scoring

    indicators_df = indicators.compute_all_indicators(
        ohlcv,
        bench_ticker=bench_ticker,
        bil_ticker=bil_ticker,
    )
    prior_primary_flow_mode = flow.ETF_PRIMARY_FLOW_STUB_MODE
    flow.ETF_PRIMARY_FLOW_STUB_MODE = True
    try:
        flow_df = flow.compute_flow_signals(ohlcv).reindex(indicators_df.index)
    finally:
        flow.ETF_PRIMARY_FLOW_STUB_MODE = prior_primary_flow_mode
    flow_z = flow.flow_composite_z(flow_df)
    return scoring.compute_composite(indicators_df, flow_df, flow_z, phase)


def _slice_ohlcv_through_date(
    ohlcv: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    snapshot = {}
    for ticker, frame in ohlcv.items():
        sliced = frame.copy()
        sliced.index = pd.to_datetime(sliced.index)
        sliced = sliced.sort_index()
        snapshot[ticker] = sliced.loc[sliced.index <= as_of].copy()
    return snapshot


def build_historical_methodology_targets(
    ohlcv: dict[str, pd.DataFrame],
    rebalance_dates: Optional[list[pd.Timestamp] | pd.DatetimeIndex] = None,
    score_snapshot_fn: Optional[ScoreSnapshotFn] = None,
    phase: str = "MID",
    bench_ticker: str = "SPY",
    bil_ticker: str = "BIL",
) -> HistoricalSignalTargets:
    prices = close_matrix_from_ohlcv(ohlcv)
    if prices.empty:
        raise ValueError("ohlcv must contain at least one close price series")
    if rebalance_dates is None:
        rebalance_index = weekly_rebalance_dates(prices)
    else:
        rebalance_index = pd.DatetimeIndex(pd.to_datetime(rebalance_dates))
    rebalance_index = pd.DatetimeIndex(sorted(rebalance_index.unique()))
    missing_dates = rebalance_index.difference(prices.index)
    if len(missing_dates):
        raise ValueError("rebalance_dates must exist in close prices")

    scorer = score_snapshot_fn or methodology_score_snapshot
    from . import scoring

    weight_rows = []
    state_rows = []
    snapshots: dict[pd.Timestamp, pd.DataFrame] = {}
    for as_of in rebalance_index:
        snapshot_ohlcv = _slice_ohlcv_through_date(ohlcv, as_of)
        scored = scorer(snapshot_ohlcv, phase, bench_ticker, bil_ticker).copy()
        snapshots[pd.Timestamp(as_of)] = scored.copy()

        weights = target_weights_from_scores(scored)
        weights.name = as_of
        weight_rows.append(weights)

        states = pd.Series(
            {ticker: scoring.decide_state(row) for ticker, row in scored.iterrows()},
            name=as_of,
            dtype=object,
        )
        state_rows.append(states)

    target_weights = pd.DataFrame(weight_rows, index=rebalance_index).fillna(0.0)
    states = pd.DataFrame(state_rows, index=rebalance_index)
    return HistoricalSignalTargets(
        target_weights=target_weights.sort_index(axis=1),
        states=states.sort_index(axis=1),
        snapshots=snapshots,
    )


def weekly_rebalance_dates(prices: pd.DataFrame) -> pd.DatetimeIndex:
    if prices.empty:
        return pd.DatetimeIndex([])
    ordered = prices.sort_index().dropna(how="all")
    weekly = ordered.groupby(pd.Grouper(freq="W-FRI")).tail(1)
    return pd.DatetimeIndex(weekly.index)


def format_gate_report(gates: dict[str, dict | bool]) -> str:
    lines = ["# Backtest Acceptance Gates", ""]
    for key, gate in gates.items():
        if key == "all_passed" or not isinstance(gate, dict):
            continue
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"- {gate['name']}: {status} "
            f"(value {gate['value']:.4f}, threshold {gate['threshold']:.4f})"
        )
        evidence = str(gate.get("evidence", "")).strip()
        if evidence:
            lines.append(f"  Evidence: {evidence}")
    lines.append("")
    lines.append(f"Overall: {'PASS' if gates.get('all_passed') else 'FAIL'}")
    return "\n".join(lines) + "\n"


def _percent(value: float) -> str:
    return f"{float(value) * 100:.2f}%"


def _number(value: float) -> str:
    return f"{float(value):.2f}"


def _metric_value(metrics: dict[str, float], key: str) -> float:
    if key not in metrics:
        raise ValueError(f"metrics missing required key: {key}")
    return _finite_scalar(f"metrics {key}", metrics[key])


def _strategy_metrics_table(metrics: dict[str, float]) -> list[str]:
    rows = [
        ("Total return", _percent(_metric_value(metrics, "total_return"))),
        ("CAGR", _percent(_metric_value(metrics, "cagr"))),
        ("Sharpe", _number(_metric_value(metrics, "sharpe"))),
        ("Sortino", _number(_metric_value(metrics, "sortino"))),
        ("Max drawdown", _percent(_metric_value(metrics, "max_drawdown"))),
        ("Calmar", _number(_metric_value(metrics, "calmar"))),
        ("Annualized turnover", _percent(_metric_value(metrics, "annualized_turnover"))),
    ]
    lines = ["| Metric | Value |", "|---|---:|"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return lines


def _benchmark_table(benchmark_metrics: dict[str, dict[str, float]]) -> list[str]:
    lines = ["| Benchmark | CAGR | Sharpe | Max Drawdown |", "|---|---:|---:|---:|"]
    for name, metrics in benchmark_metrics.items():
        lines.append(
            f"| {name} | "
            f"{_percent(_metric_value(metrics, 'cagr'))} | "
            f"{_number(_metric_value(metrics, 'sharpe'))} | "
            f"{_percent(_metric_value(metrics, 'max_drawdown'))} |"
        )
    return lines


def _cost_sensitivity_table(cost_scenarios: pd.DataFrame) -> list[str]:
    required = {"cagr", "sharpe", "max_drawdown"}
    missing = required.difference(cost_scenarios.columns)
    if missing:
        raise ValueError("cost_scenarios missing required columns: " + ", ".join(sorted(missing)))
    lines = ["| Cost | CAGR | Sharpe | Max Drawdown |", "|---|---:|---:|---:|"]
    for cost_bps, row in cost_scenarios.sort_index().iterrows():
        label = f"{float(cost_bps):g} bps"
        lines.append(
            f"| {label} | "
            f"{_percent(_finite_scalar('cost_scenarios cagr', row['cagr']))} | "
            f"{_number(_finite_scalar('cost_scenarios sharpe', row['sharpe']))} | "
            f"{_percent(_finite_scalar('cost_scenarios max_drawdown', row['max_drawdown']))} |"
        )
    return lines


def _macro_variant_table(macro_variant_summary: pd.DataFrame) -> list[str]:
    required = {
        "variant",
        "series_id",
        "condition",
        "active_rebalances",
        "total_return_delta",
        "sharpe_delta",
        "max_drawdown_delta",
    }
    missing = required.difference(macro_variant_summary.columns)
    if missing:
        raise ValueError("macro_variant_summary missing required columns: " + ", ".join(sorted(missing)))
    lines = [
        "| Variant | Series | Condition | Active Rebalances | Return Delta | Sharpe Delta | Drawdown Delta |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for _, row in macro_variant_summary.iterrows():
        lines.append(
            f"| {row['variant']} | "
            f"{row['series_id']} | "
            f"{row['condition']} | "
            f"{int(row['active_rebalances'])} | "
            f"{_percent(_finite_scalar('macro variant total_return_delta', row['total_return_delta']))} | "
            f"{_number(_finite_scalar('macro variant sharpe_delta', row['sharpe_delta']))} | "
            f"{_percent(_finite_scalar('macro variant max_drawdown_delta', row['max_drawdown_delta']))} |"
        )
    return lines


def _window_metrics_table(window_metrics: dict[str, dict[str, float]]) -> list[str]:
    lines = ["| Window | Total Return | CAGR | Sharpe | Max Drawdown | Annualized Turnover |"]
    lines.append("|---|---:|---:|---:|---:|---:|")
    for name, metrics in window_metrics.items():
        lines.append(
            f"| {name} | "
            f"{_percent(_metric_value(metrics, 'total_return'))} | "
            f"{_percent(_metric_value(metrics, 'cagr'))} | "
            f"{_number(_metric_value(metrics, 'sharpe'))} | "
            f"{_percent(_metric_value(metrics, 'max_drawdown'))} | "
            f"{_percent(_metric_value(metrics, 'annualized_turnover'))} |"
        )
    return lines


def _simulation_summary_table(summary: dict[str, int | float | str | None]) -> list[str]:
    rows = [
        ("Start date", summary.get("start_date")),
        ("End date", summary.get("end_date")),
        ("Rebalances", summary.get("rebalance_count")),
        ("State tickers", summary.get("state_ticker_count")),
        ("Selected tickers", summary.get("selected_ticker_count")),
        ("State transitions", summary.get("state_transition_count")),
        ("State transitions per ticker-year", summary.get("state_transitions_per_ticker_year")),
    ]
    lines = ["| Evidence | Value |", "|---|---:|"]
    for label, value in rows:
        if value is None:
            formatted = "-"
        elif isinstance(value, float):
            formatted = f"{value:.2f}"
        else:
            formatted = str(value)
        lines.append(f"| {label} | {formatted} |")
    return lines


def format_backtest_report(
    strategy_metrics: dict[str, float],
    benchmark_metrics: dict[str, dict[str, float]],
    cost_scenarios: pd.DataFrame,
    gates: dict[str, dict | bool],
    window_metrics: Optional[dict[str, dict[str, float]]] = None,
    simulation_summary: Optional[dict[str, int | float | str | None]] = None,
    macro_variant_summary: Optional[pd.DataFrame] = None,
    oos_start: str | pd.Timestamp = "2015-01-01",
    title: str = "Backtest Report",
) -> str:
    lines = [f"# {title}", ""]
    lines.extend(["## Strategy Metrics", ""])
    lines.extend(_strategy_metrics_table(strategy_metrics))
    lines.extend(["", "## Benchmark Comparison", ""])
    lines.extend(_benchmark_table(benchmark_metrics))
    lines.extend(["", "## Cost Sensitivity", ""])
    lines.extend(_cost_sensitivity_table(cost_scenarios))
    if simulation_summary:
        lines.extend(["", "## Historical Methodology Simulation", ""])
        lines.extend(_simulation_summary_table(simulation_summary))
    if window_metrics:
        lines.extend(["", "## In-Sample / Out-of-Sample", ""])
        lines.append(f"OOS starts: {pd.Timestamp(oos_start).date().isoformat()}")
        lines.append("")
        lines.extend(_window_metrics_table(window_metrics))
    if macro_variant_summary is not None and not macro_variant_summary.empty:
        lines.extend(["", "## Macro Condition Variants", ""])
        lines.append(
            "Analysis-only exposure filters from historical macro series. "
            "Positive deltas mean the variant beat the baseline methodology metric."
        )
        lines.append("")
        lines.extend(_macro_variant_table(macro_variant_summary))
    lines.extend(["", "## Acceptance Gates", ""])
    lines.extend(format_gate_report(gates).splitlines()[2:])
    return "\n".join(lines).rstrip() + "\n"


def format_methodology_report(
    strategy_metrics: dict[str, float],
    benchmark_metrics: dict[str, dict[str, float]],
    gates: dict[str, dict | bool],
    window_metrics: dict[str, dict[str, float]],
    simulation_summary: dict[str, int | float | str | None],
    macro_variant_summary: Optional[pd.DataFrame] = None,
    title: str = "Historical Methodology Backtest Report",
) -> str:
    lines = [
        f"# {title}",
        "",
        "## Executive Summary",
        "",
        (
            "This report is research evidence, not investment advice. It summarizes the "
            "manual B-011 historical methodology run and should be read alongside the "
            "deterministic pytest suite."
        ),
        "",
        (
            f"The methodology full-period CAGR is {_percent(_metric_value(strategy_metrics, 'cagr'))}, "
            f"Sharpe is {_number(_metric_value(strategy_metrics, 'sharpe'))}, and max drawdown is "
            f"{_percent(_metric_value(strategy_metrics, 'max_drawdown'))}."
        ),
        "",
        "## Methodology Under Test",
        "",
        (
            "The strategy path uses the historical methodology target builder: each rebalance "
            "date slices OHLCV through that date, scores with pure `src/` modules, converts "
            "selected tickers to equal target weights, and records states through `decide_state()` "
            "without calling `apply_state_machine()` or writing `state.json`."
        ),
        "",
        (
            "provider-backed historical flow is neutral until as-of provider snapshots exist, "
            "which avoids current-data leakage in this report."
        ),
        "",
        "## Evidence Tables",
        "",
        "### Historical Methodology Simulation",
        "",
    ]
    lines.extend(_simulation_summary_table(simulation_summary))
    lines.extend(["", "### Strategy Metrics", ""])
    lines.extend(_strategy_metrics_table(strategy_metrics))
    lines.extend(["", "### Benchmark Comparison", ""])
    lines.extend(_benchmark_table(benchmark_metrics))
    lines.extend(["", "### In-Sample / Out-of-Sample", ""])
    lines.extend(_window_metrics_table(window_metrics))
    if macro_variant_summary is not None and not macro_variant_summary.empty:
        lines.extend(["", "### Macro Condition Variants", ""])
        lines.extend(_macro_variant_table(macro_variant_summary))
    lines.extend(["", "## Acceptance Gates", ""])
    lines.extend(format_gate_report(gates).splitlines()[2:])
    lines.extend(
        [
            "",
            "## Limitations And Next Work",
            "",
            "- Manual artifacts are evidence for review, not a live-edge claim.",
            "- provider-backed historical flow is neutral until timestamped as-of feeds are available.",
            "- The notebook/report guide does not replace deterministic tests or live provider validation.",
            "- Backtest results do not guarantee future performance.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def equity_frame(results: dict[str, BacktestResult]) -> pd.DataFrame:
    if not results:
        raise ValueError("results must contain at least one backtest result")
    series = {}
    for name, result in results.items():
        equity = result.equity.copy()
        equity.index = pd.to_datetime(equity.index)
        series[str(name)] = equity.sort_index()
    frame = pd.DataFrame(series).sort_index().ffill()
    frame.index.name = "date"
    return frame


def _state_transition_count(states: pd.DataFrame) -> int:
    count = 0
    for column in states.columns:
        values = states[column].dropna().astype(str)
        if len(values) < 2:
            continue
        count += int(values.ne(values.shift()).iloc[1:].sum())
    return count


def state_transition_rate(states: pd.DataFrame, periods_per_year: int | float = 52) -> float:
    periods = _finite_scalar("periods_per_year", periods_per_year)
    if periods <= 0:
        raise ValueError("periods_per_year must be positive")
    if states.empty or states.shape[1] == 0 or len(states.index) < 2:
        return 0.0
    frame = states.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    transition_count = 0
    observed_intervals = 0
    for column in frame.columns:
        values = frame[column].dropna().astype(str)
        if len(values) < 2:
            continue
        transition_count += int(values.ne(values.shift()).iloc[1:].sum())
        observed_intervals += len(values) - 1
    if transition_count == 0:
        return 0.0
    if observed_intervals == 0:
        return 0.0
    observed_years = observed_intervals / periods
    return float(transition_count / observed_years)


def historical_simulation_summary(
    targets: HistoricalSignalTargets,
    periods_per_year: int | float = 52,
) -> dict[str, int | float | str | None]:
    states = targets.states.copy()
    weights = targets.target_weights.copy()
    if not states.empty:
        states.index = pd.to_datetime(states.index)
        states = states.sort_index()
    if not weights.empty:
        weights.index = pd.to_datetime(weights.index)
        weights = weights.sort_index()

    index = weights.index if len(weights.index) else states.index
    start_date = pd.Timestamp(index[0]).date().isoformat() if len(index) else None
    end_date = pd.Timestamp(index[-1]).date().isoformat() if len(index) else None
    selected_ticker_count = 0
    if not weights.empty:
        numeric_weights = weights.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        selected_ticker_count = int((numeric_weights.abs() > 0).any(axis=0).sum())

    return {
        "start_date": start_date,
        "end_date": end_date,
        "rebalance_count": int(len(index)),
        "state_ticker_count": int(sum(1 for column in states.columns if states[column].notna().any())),
        "selected_ticker_count": selected_ticker_count,
        "state_transition_count": _state_transition_count(states) if not states.empty else 0,
        "state_transitions_per_ticker_year": state_transition_rate(states, periods_per_year=periods_per_year),
    }


def _clean_equity_artifact(equity: pd.DataFrame) -> pd.DataFrame:
    frame = equity.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index().apply(pd.to_numeric, errors="coerce").dropna(how="all").ffill()
    if frame.empty:
        frame.index.name = "date"
        return frame
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (frame <= 0).any().any():
        raise ValueError("equity values must be finite and strictly positive")
    frame.index.name = "date"
    return frame


def normalized_equity_frame(equity: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_equity_artifact(equity)
    if frame.empty:
        return frame
    normalized = frame.div(frame.iloc[0])
    normalized.index.name = "date"
    return normalized


def drawdown_frame(equity: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_equity_artifact(equity)
    if frame.empty:
        return frame
    drawdown = frame.div(frame.cummax()).sub(1.0)
    drawdown.index.name = "date"
    return drawdown
