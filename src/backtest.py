"""Pure backtest accounting helpers.

This module has no Streamlit imports, no network calls, and no state-file
writes. It accepts already-loaded prices and target weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
