"""Pure backtest accounting helpers.

This module has no Streamlit imports, no network calls, and no state-file
writes. It accepts already-loaded prices and target weights.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

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


@dataclass(frozen=True)
class CalibrationCandidateRule:
    candidate_id: str
    positive_min_s_score_after_veto: float | None = None
    negative_max_s_score_after_veto: float | None = None


@dataclass(frozen=True)
class WalkForwardSplit:
    name: str
    calibration_start: pd.Timestamp
    calibration_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    final_holdout_start: pd.Timestamp
    final_holdout_end: pd.Timestamp


ScoreSnapshotFn = Callable[[dict[str, pd.DataFrame], str, str, str], pd.DataFrame]


def _finite_scalar(name: str, value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _sorted_unique_strings(name: str, values: Sequence[str]) -> list[str]:
    out = sorted({str(value).strip().upper() for value in values if str(value).strip()})
    if not out:
        raise ValueError(f"{name} must contain at least one value")
    return out


def _positive_int(name: str, value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if number <= 0 or float(number) != float(value):
        raise ValueError(f"{name} must be a positive integer")
    return number


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("configuration contains non-finite numeric value")
        return number
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value)]
    return value


def baseline_config_hash(config: dict) -> str:
    payload = json.dumps(
        _json_safe(config),
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def frozen_baseline_config(
    universe: Sequence[str],
    *,
    benchmark_tickers: Sequence[str] = ("AGG", "SPY"),
    rebalance_cadence: str = "W-FRI",
    phase: str = "MID",
    bench_ticker: str = "SPY",
    bil_ticker: str = "BIL",
    ohlcv_provider: str = "auto",
    transaction_cost_bps: float = 5.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    requested_years: int = 10,
    calibration_years: int = 5,
    validation_years: int = 1,
    final_holdout_years: int = 1,
    signal_horizons_weeks: Sequence[int] = (4, 13, 26, 52),
) -> dict:
    cost_bps = _finite_scalar("transaction_cost_bps", transaction_cost_bps)
    if cost_bps < 0:
        raise ValueError("transaction_cost_bps must be non-negative")
    periods = _positive_int("periods_per_year", periods_per_year)
    horizons = sorted({_positive_int("signal_horizons_weeks", value) for value in signal_horizons_weeks})
    if not horizons:
        raise ValueError("signal_horizons_weeks must contain at least one value")
    universe_tickers = _sorted_unique_strings("universe", universe)
    from . import scoring, universe as universe_module

    return {
        "ticket": "B-163",
        "slice": "B-163.1",
        "purpose": "research_only_10_year_walk_forward_calibration",
        "universe": universe_tickers,
        "universe_classes": {
            ticker: universe_module.class_of(ticker)
            for ticker in universe_tickers
        },
        "benchmarks": _sorted_unique_strings("benchmark_tickers", benchmark_tickers),
        "rebalance": {
            "cadence": str(rebalance_cadence),
            "date_builder": "src.backtest.weekly_rebalance_dates",
        },
        "methodology": {
            "phase": str(phase),
            "bench_ticker": str(bench_ticker).strip().upper(),
            "bil_ticker": str(bil_ticker).strip().upper(),
            "selection_policy": "equal_weight_selected_tickers",
            "target_normalization": "absolute_weight_sum_capped_at_1",
        },
        "accounting": {
            "transaction_cost_bps": cost_bps,
            "periods_per_year": periods,
        },
        "walk_forward": {
            "requested_years": _positive_int("requested_years", requested_years),
            "calibration_years": _positive_int("calibration_years", calibration_years),
            "validation_years": _positive_int("validation_years", validation_years),
            "final_holdout_years": _positive_int("final_holdout_years", final_holdout_years),
        },
        "signal_labels": {
            "forward_horizons_weeks": horizons,
            "positive_success": [
                "forward_absolute_return",
                "forward_excess_return_vs_class_benchmark",
                "post_entry_drawdown",
            ],
            "negative_success": [
                "avoided_underperformance",
                "avoided_drawdown",
                "failed_positive_follow_through",
                "risk_off_or_reduce_exposure_success",
            ],
        },
        "provider_flags": {
            "ohlcv_provider": str(ohlcv_provider),
            "historical_provider_flow": "neutral_stub",
            "fred_macro": "analysis_only_point_in_time_when_enabled",
            "massive_provider_flow": "analysis_only_snapshot_replay_when_available",
        },
        "scoring_parameters": scoring.methodology_scoring_parameters(),
        "algorithm_components": {
            "indicator_builder": "src.indicators.compute_all_indicators",
            "flow_builder": "src.flow.compute_flow_signals",
            "score_builder": "src.scoring.compute_composite",
            "state_function": "src.scoring.decide_state",
            "target_builder": "src.backtest.build_historical_methodology_targets",
            "weight_builder": "src.backtest.target_weights_from_scores",
            "accounting_engine": "src.backtest.run_weight_backtest",
        },
        "state_machine": {
            "historical_policy": "recompute_state_per_rebalance_snapshot",
            "state_file_writes": "disabled",
        },
        "safety": {
            "research_only": True,
            "live_promotion_requires_separate_ticket": True,
            "no_live_scoring_changes": True,
        },
    }


def _clean_datetime_index(name: str, dates: Sequence[pd.Timestamp] | pd.DatetimeIndex) -> pd.DatetimeIndex:
    try:
        index = pd.DatetimeIndex(pd.to_datetime(dates))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be datetime-like") from exc
    index = index[~index.isna()]
    if index.empty:
        raise ValueError(f"{name} must contain at least one date")
    return pd.DatetimeIndex(sorted(index.unique()))


def _first_on_or_after(index: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Timestamp | None:
    matches = index[index >= target]
    if matches.empty:
        return None
    return pd.Timestamp(matches[0])


def _last_before(index: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Timestamp | None:
    matches = index[index < target]
    if matches.empty:
        return None
    return pd.Timestamp(matches[-1])


def walk_forward_calibration_splits(
    dates: Sequence[pd.Timestamp] | pd.DatetimeIndex,
    *,
    years: int = 10,
    calibration_years: int = 5,
    validation_years: int = 1,
    final_holdout_years: int = 1,
) -> list[WalkForwardSplit]:
    years = _positive_int("years", years)
    calibration_years = _positive_int("calibration_years", calibration_years)
    validation_years = _positive_int("validation_years", validation_years)
    final_holdout_years = _positive_int("final_holdout_years", final_holdout_years)
    if calibration_years + validation_years + final_holdout_years >= years:
        raise ValueError(
            "calibration, validation, and holdout years must leave rolling history before "
            "the final holdout"
        )

    index = _clean_datetime_index("dates", dates)
    window_end = pd.Timestamp(index[-1])
    window_start_target = window_end - pd.DateOffset(years=years) + pd.Timedelta(days=1)
    if pd.Timestamp(index[0]) > window_start_target:
        raise ValueError(f"dates must span at least {years} years")
    window_dates = index[index >= window_start_target]
    if window_dates.empty:
        raise ValueError(f"dates must span at least {years} years")
    if pd.Timestamp(window_dates[0]) - window_start_target > pd.Timedelta(days=7):
        raise ValueError("dates must provide a continuous 10-year window without large gaps")
    if len(window_dates) > 1:
        max_gap = pd.Series(window_dates).diff().dropna().max()
        if pd.notna(max_gap) and max_gap > pd.Timedelta(days=45):
            raise ValueError("dates must provide a continuous 10-year window without large gaps")
    window_start = pd.Timestamp(window_dates[0])
    holdout_start_target = window_end - pd.DateOffset(years=final_holdout_years)
    holdout_start = _first_on_or_after(window_dates, holdout_start_target)
    if holdout_start is None:
        raise ValueError("final holdout window cannot be built from available dates")

    splits: list[WalkForwardSplit] = []
    calibration_start = window_start
    while True:
        validation_start_target = calibration_start + pd.DateOffset(years=calibration_years)
        validation_start = _first_on_or_after(window_dates, validation_start_target)
        if validation_start is None or validation_start >= holdout_start:
            break
        calibration_end = _last_before(window_dates, validation_start)
        validation_end_target = validation_start + pd.DateOffset(years=validation_years)
        validation_end_limit = min(validation_end_target, holdout_start)
        validation_end = _last_before(window_dates, validation_end_limit)
        if calibration_end is None or validation_end is None:
            break
        if not (calibration_start <= calibration_end < validation_start <= validation_end < holdout_start):
            break
        splits.append(
            WalkForwardSplit(
                name=f"fold_{len(splits) + 1:02d}",
                calibration_start=pd.Timestamp(calibration_start),
                calibration_end=pd.Timestamp(calibration_end),
                validation_start=pd.Timestamp(validation_start),
                validation_end=pd.Timestamp(validation_end),
                final_holdout_start=pd.Timestamp(holdout_start),
                final_holdout_end=pd.Timestamp(window_end),
            )
        )
        next_start_target = calibration_start + pd.DateOffset(years=validation_years)
        next_start = _first_on_or_after(window_dates, next_start_target)
        if next_start is None or next_start <= calibration_start:
            break
        calibration_start = pd.Timestamp(next_start)

    if not splits:
        raise ValueError("walk-forward split parameters produced no calibration folds")
    return splits


def _date_string(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).date().isoformat()


def _split_to_record(split: WalkForwardSplit) -> dict[str, str]:
    return {
        "name": split.name,
        "calibration_start": _date_string(split.calibration_start),
        "calibration_end": _date_string(split.calibration_end),
        "validation_start": _date_string(split.validation_start),
        "validation_end": _date_string(split.validation_end),
        "final_holdout_start": _date_string(split.final_holdout_start),
        "final_holdout_end": _date_string(split.final_holdout_end),
    }


def walk_forward_split_summary(
    splits: Sequence[WalkForwardSplit],
    *,
    requested_years: int = 10,
) -> dict:
    requested_years = _positive_int("requested_years", requested_years)
    if not splits:
        return {
            "status": "no_splits",
            "requested_years": requested_years,
            "fold_count": 0,
            "folds": [],
        }
    no_lookahead_verified = all(
        split.calibration_start <= split.calibration_end < split.validation_start
        and split.validation_start <= split.validation_end < split.final_holdout_start
        and split.final_holdout_start <= split.final_holdout_end
        for split in splits
    )
    window_start = min(split.calibration_start for split in splits)
    window_end = max(split.final_holdout_end for split in splits)
    holdout_start = min(split.final_holdout_start for split in splits)
    holdout_end = max(split.final_holdout_end for split in splits)
    return {
        "status": "ready",
        "requested_years": requested_years,
        "fold_count": len(splits),
        "window": {
            "start": _date_string(window_start),
            "end": _date_string(window_end),
        },
        "final_holdout": {
            "start": _date_string(holdout_start),
            "end": _date_string(holdout_end),
        },
        "no_lookahead_verified": no_lookahead_verified,
        "folds": [_split_to_record(split) for split in splits],
    }


def _scalar_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _float_or_nan(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if np.isfinite(number) else float("nan")


def _state_at(states: pd.DataFrame, as_of: pd.Timestamp, ticker: str, fallback: str = "") -> str:
    if states.empty or as_of not in states.index or ticker not in states.columns:
        return fallback
    value = states.loc[as_of, ticker]
    if value is None or pd.isna(value):
        return fallback
    return str(value)


def _target_weight_at(target_weights: pd.DataFrame, as_of: pd.Timestamp, ticker: str) -> float:
    if target_weights.empty or as_of not in target_weights.index or ticker not in target_weights.columns:
        return 0.0
    return _float_or_nan(target_weights.loc[as_of, ticker])


def _class_benchmark_for(
    ticker: str,
    ticker_class: str,
    prices: pd.DataFrame,
    benchmark_by_class: dict[str, str] | None,
) -> str | None:
    mapping = {str(key): str(value).upper() for key, value in (benchmark_by_class or {}).items()}
    benchmark = mapping.get(str(ticker_class))
    if benchmark and benchmark in prices.columns:
        return benchmark
    if ticker in prices.columns and ticker_class == "Benchmark":
        return ticker
    return "SPY" if "SPY" in prices.columns else None


def _forward_label_values(
    prices: pd.DataFrame,
    *,
    ticker: str,
    benchmark: str | None,
    as_of: pd.Timestamp,
    horizon_weeks: int,
) -> dict:
    horizon_weeks = _positive_int("horizon_weeks", horizon_weeks)
    empty = {
        "available": False,
        "end_date": None,
        "forward_return": float("nan"),
        "benchmark_return": float("nan"),
        "excess_return": float("nan"),
        "drawdown": float("nan"),
    }
    if ticker not in prices.columns or benchmark is None or benchmark not in prices.columns:
        return empty
    if as_of not in prices.index:
        raise ValueError("rebalance dates must exist in prices index")
    end_target = pd.Timestamp(as_of) + pd.DateOffset(weeks=horizon_weeks)
    end_date = _first_on_or_after(prices.index, end_target)
    if end_date is None:
        return empty
    empty["end_date"] = pd.Timestamp(end_date)
    start_price = _float_or_nan(prices.loc[as_of, ticker])
    end_price = _float_or_nan(prices.loc[end_date, ticker])
    benchmark_start = _float_or_nan(prices.loc[as_of, benchmark])
    benchmark_end = _float_or_nan(prices.loc[end_date, benchmark])
    if (
        not all(np.isfinite(value) for value in [start_price, end_price, benchmark_start, benchmark_end])
        or min(start_price, end_price, benchmark_start, benchmark_end) <= 0
    ):
        return empty
    window = prices.loc[(prices.index >= as_of) & (prices.index <= end_date), ticker].astype(float)
    if window.empty or window.isna().any():
        return empty
    forward_return = end_price / start_price - 1.0
    benchmark_return = benchmark_end / benchmark_start - 1.0
    drawdown = float(window.min() / start_price - 1.0)
    return {
        "available": True,
        "end_date": pd.Timestamp(end_date),
        "forward_return": float(forward_return),
        "benchmark_return": float(benchmark_return),
        "excess_return": float(forward_return - benchmark_return),
        "drawdown": drawdown,
    }


def build_calibration_feature_labels(
    targets: HistoricalSignalTargets,
    prices: pd.DataFrame,
    *,
    horizons_weeks: Sequence[int] = (4, 13, 26, 52),
    benchmark_by_class: dict[str, str] | None = None,
    drawdown_avoidance_threshold: float = -0.05,
) -> pd.DataFrame:
    """Build point-in-time feature rows plus forward labels for calibration research."""
    raw_prices = prices.copy()
    raw_prices.index = pd.to_datetime(raw_prices.index)
    if not raw_prices.index.is_unique:
        raise ValueError("prices index must be unique")
    if not raw_prices.columns.is_unique:
        raise ValueError("prices columns must be unique")
    raw_prices = raw_prices.sort_index().apply(pd.to_numeric, errors="coerce").dropna(how="all")
    available_values = raw_prices.to_numpy(dtype=float)
    available_values = available_values[~np.isnan(available_values)]
    if len(available_values) and ((~np.isfinite(available_values)).any() or (available_values <= 0).any()):
        raise ValueError("prices must be finite and strictly positive where available")
    horizons = sorted({_positive_int("horizons_weeks", value) for value in horizons_weeks})
    if not horizons:
        raise ValueError("horizons_weeks must contain at least one value")
    drawdown_threshold = _finite_scalar("drawdown_avoidance_threshold", drawdown_avoidance_threshold)
    target_weights = targets.target_weights.copy()
    target_weights.index = pd.to_datetime(target_weights.index)
    states = targets.states.copy()
    states.index = pd.to_datetime(states.index)
    negative_states = {"WARNING", "EXIT", "BEARISH_STAGE_4"}
    rows: list[dict] = []
    bool_columns = {"selected", "veto", "positive_signal", "negative_signal"}

    for raw_as_of in sorted(targets.snapshots):
        as_of = pd.Timestamp(raw_as_of)
        if as_of not in raw_prices.index:
            raise ValueError("rebalance dates must exist in prices index")
        snapshot = targets.snapshots[raw_as_of].copy()
        for ticker, snapshot_row in snapshot.iterrows():
            ticker = str(ticker).upper()
            ticker_class = str(snapshot_row.get("class", ""))
            state = _state_at(states, as_of, ticker, fallback=str(snapshot_row.get("state", "")))
            target_weight = _target_weight_at(target_weights, as_of, ticker)
            selected = _scalar_bool(snapshot_row.get("selected"), default=target_weight > 0.0)
            positive_signal = bool(selected or state == "STAGE_2_BULLISH")
            negative_signal = state in negative_states
            benchmark = _class_benchmark_for(ticker, ticker_class, raw_prices, benchmark_by_class)
            row = {
                "rebalance_date": as_of,
                "feature_asof_date": as_of,
                "ticker": ticker,
                "class": ticker_class,
                "benchmark_ticker": benchmark,
                "state": state,
                "target_weight": target_weight,
                "selected": selected,
                "positive_signal": positive_signal,
                "negative_signal": negative_signal,
                "S_score": _float_or_nan(snapshot_row.get("S_score")),
                "S_score_after_veto": _float_or_nan(snapshot_row.get("S_score_after_veto")),
                "rank_in_class": _float_or_nan(snapshot_row.get("rank_in_class")),
                "top_n_target": _float_or_nan(snapshot_row.get("top_n_target")),
                "veto": _scalar_bool(snapshot_row.get("veto"), default=False),
            }
            for horizon in horizons:
                suffix = f"{horizon}w"
                values = _forward_label_values(
                    raw_prices,
                    ticker=ticker,
                    benchmark=benchmark,
                    as_of=as_of,
                    horizon_weeks=horizon,
                )
                available = bool(values["available"])
                positive_success = bool(
                    positive_signal
                    and available
                    and values["forward_return"] > 0.0
                    and values["excess_return"] > 0.0
                )
                avoided_underperformance = bool(
                    negative_signal and available and values["excess_return"] < 0.0
                )
                failed_followthrough = bool(
                    negative_signal and available and values["forward_return"] <= 0.0
                )
                avoided_drawdown = bool(
                    negative_signal and available and values["drawdown"] <= drawdown_threshold
                )
                negative_success = bool(
                    negative_signal
                    and available
                    and (avoided_underperformance or failed_followthrough or avoided_drawdown)
                )
                row.update(
                    {
                        f"label_available_{suffix}": available,
                        f"label_end_date_{suffix}": values["end_date"],
                        f"forward_return_{suffix}": values["forward_return"],
                        f"forward_benchmark_return_{suffix}": values["benchmark_return"],
                        f"forward_excess_return_{suffix}": values["excess_return"],
                        f"post_entry_drawdown_{suffix}": values["drawdown"],
                        f"positive_success_{suffix}": positive_success,
                        f"negative_avoided_underperformance_{suffix}": avoided_underperformance,
                        f"negative_failed_followthrough_{suffix}": failed_followthrough,
                        f"negative_avoided_drawdown_{suffix}": avoided_drawdown,
                        f"negative_success_{suffix}": negative_success,
                    }
                )
                bool_columns.update(
                    {
                        f"label_available_{suffix}",
                        f"positive_success_{suffix}",
                        f"negative_avoided_underperformance_{suffix}",
                        f"negative_failed_followthrough_{suffix}",
                        f"negative_avoided_drawdown_{suffix}",
                        f"negative_success_{suffix}",
                    }
                )
            rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in sorted(bool_columns.intersection(frame.columns)):
        frame[column] = frame[column].map(bool).astype(object)
    return frame


def _bool_series(series: pd.Series) -> pd.Series:
    return series.map(lambda value: _scalar_bool(value, default=False)).astype(bool)


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _mean_or_zero(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if len(values) else 0.0


def _calibration_metric_columns(group_cols: Sequence[str] = ()) -> list[str]:
    return [
        *group_cols,
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


def _normalized_group_columns(group_by: str | Sequence[str] | None) -> list[str]:
    if group_by is None:
        return []
    if isinstance(group_by, str):
        group_cols = [group_by]
    else:
        group_cols = [str(column) for column in group_by]
    if not group_cols:
        raise ValueError("group_by must contain at least one column")
    return group_cols


def _required_calibration_columns(horizon: int) -> dict[str, str]:
    suffix = f"{horizon}w"
    return {
        "available": f"label_available_{suffix}",
        "positive_success": f"positive_success_{suffix}",
        "negative_success": f"negative_success_{suffix}",
        "forward_return": f"forward_return_{suffix}",
        "forward_excess_return": f"forward_excess_return_{suffix}",
        "post_entry_drawdown": f"post_entry_drawdown_{suffix}",
    }


def _calibration_actual_outcome(
    *,
    direction: str,
    available: pd.Series,
    forward_return: pd.Series,
    forward_excess_return: pd.Series,
    post_entry_drawdown: pd.Series,
    drawdown_avoidance_threshold: float,
) -> pd.Series:
    if direction == "positive":
        actual = (
            available
            & forward_return.notna()
            & forward_excess_return.notna()
            & (forward_return > 0.0)
            & (forward_excess_return > 0.0)
        )
    else:
        actual = (
            available
            & (
                (forward_return.notna() & (forward_return <= 0.0))
                | (forward_excess_return.notna() & (forward_excess_return < 0.0))
                | (
                    post_entry_drawdown.notna()
                    & (post_entry_drawdown <= drawdown_avoidance_threshold)
                )
            )
        )
    actual = actual.astype(bool)
    return actual.reindex(available.index, fill_value=False).astype(bool)


def calibration_label_metrics(
    labels: pd.DataFrame,
    *,
    horizons_weeks: Sequence[int] = (4, 13, 26, 52),
    group_by: str | Sequence[str] | None = None,
    drawdown_avoidance_threshold: float = -0.05,
) -> pd.DataFrame:
    """Aggregate calibration label hit rates and directional confusion metrics."""
    horizons = sorted({_positive_int("horizons_weeks", value) for value in horizons_weeks})
    if not horizons:
        raise ValueError("horizons_weeks must contain at least one value")
    threshold = _finite_scalar("drawdown_avoidance_threshold", drawdown_avoidance_threshold)
    group_cols = _normalized_group_columns(group_by)
    metric_columns = _calibration_metric_columns(group_cols)
    if labels.empty:
        return pd.DataFrame(columns=metric_columns)
    required_base = {"positive_signal", "negative_signal", *group_cols}
    missing_base = sorted(required_base.difference(labels.columns))
    if missing_base:
        raise ValueError(f"labels missing required columns: {', '.join(missing_base)}")

    rows: list[dict] = []
    frame = labels.copy()
    if group_cols:
        groups = frame.groupby(group_cols, dropna=False, sort=True)
    else:
        groups = [((), frame)]

    for horizon in horizons:
        horizon_columns = _required_calibration_columns(horizon)
        required = set(horizon_columns.values())
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(
                f"labels missing required columns for {horizon}w: {', '.join(missing)}"
            )

        for raw_group_key, group in groups:
            if group_cols:
                group_values = (
                    raw_group_key if isinstance(raw_group_key, tuple) else (raw_group_key,)
                )
                group_record = dict(zip(group_cols, group_values))
            else:
                group_record = {}

            available = _bool_series(group[horizon_columns["available"]])
            forward_return = pd.to_numeric(
                group[horizon_columns["forward_return"]], errors="coerce"
            )
            forward_excess_return = pd.to_numeric(
                group[horizon_columns["forward_excess_return"]], errors="coerce"
            )
            post_entry_drawdown = pd.to_numeric(
                group[horizon_columns["post_entry_drawdown"]], errors="coerce"
            )

            for direction, signal_col in (
                ("positive", "positive_signal"),
                ("negative", "negative_signal"),
            ):
                signal = _bool_series(group[signal_col])
                signal_available = signal & available
                signal_unavailable = signal & ~available
                actual = _calibration_actual_outcome(
                    direction=direction,
                    available=available,
                    forward_return=forward_return,
                    forward_excess_return=forward_excess_return,
                    post_entry_drawdown=post_entry_drawdown,
                    drawdown_avoidance_threshold=threshold,
                )
                success = signal_available & actual
                predicted = signal_available
                failure = signal_available & ~success
                true_positive = int((predicted & actual).sum())
                false_positive = int((predicted & ~actual).sum())
                false_negative = int((~predicted & available & actual).sum())
                true_negative = int((~predicted & available & ~actual).sum())
                precision = _rate(true_positive, true_positive + false_positive)
                recall = _rate(true_positive, true_positive + false_negative)
                f1 = _rate(
                    2 * true_positive,
                    2 * true_positive + false_positive + false_negative,
                )
                success_count = int(success.sum())
                failure_count = int(failure.sum())
                signal_count = int(signal.sum())
                total_count = int(len(group))
                available_count = int(available.sum())
                signal_available_count = int(signal_available.sum())
                drawdown_avoided = 0.0
                if direction == "negative":
                    drawdown_avoided = _mean_or_zero(
                        -post_entry_drawdown.loc[signal_available].clip(upper=0.0)
                    )

                rows.append(
                    {
                        **group_record,
                        "direction": direction,
                        "horizon_weeks": horizon,
                        "total_count": total_count,
                        "available_count": available_count,
                        "unavailable_count": total_count - available_count,
                        "missing_label_rate": _rate(
                            total_count - available_count, total_count
                        ),
                        "signal_count": signal_count,
                        "signal_available_count": signal_available_count,
                        "signal_unavailable_count": int(signal_unavailable.sum()),
                        "signal_missing_rate": _rate(
                            int(signal_unavailable.sum()), signal_count
                        ),
                        "success_count": success_count,
                        "failure_count": failure_count,
                        "hit_rate": _rate(success_count, signal_available_count),
                        "actual_outcome_count": int(actual.sum()),
                        "true_positive": true_positive,
                        "false_positive": false_positive,
                        "false_negative": false_negative,
                        "true_negative": true_negative,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                        "average_forward_return": _mean_or_zero(
                            forward_return.loc[signal_available]
                        ),
                        "average_forward_excess_return": _mean_or_zero(
                            forward_excess_return.loc[signal_available]
                        ),
                        "average_post_entry_drawdown": _mean_or_zero(
                            post_entry_drawdown.loc[signal_available]
                        ),
                        "average_drawdown_avoided": drawdown_avoided,
                    }
                )

    return pd.DataFrame(rows, columns=metric_columns)


def _windowed_labels_for_split(
    labels: pd.DataFrame,
    split: WalkForwardSplit,
    window: str,
    horizon_weeks: int | None = None,
) -> pd.DataFrame:
    if labels.empty:
        return labels.copy()
    if "rebalance_date" not in labels.columns:
        raise ValueError("labels missing required columns: rebalance_date")
    dates = pd.to_datetime(labels["rebalance_date"])
    if window == "calibration":
        mask = (dates >= split.calibration_start) & (dates <= split.calibration_end)
        if horizon_weeks is not None:
            maturity_dates = _label_maturity_dates(labels, horizon_weeks)
            mask &= maturity_dates.notna() & (maturity_dates <= split.calibration_end)
    elif window == "validation":
        mask = (dates >= split.validation_start) & (dates <= split.validation_end)
        if horizon_weeks is not None:
            maturity_dates = _label_maturity_dates(labels, horizon_weeks)
            mask &= maturity_dates.notna() & (maturity_dates < split.final_holdout_start)
    else:
        raise ValueError("window must be calibration or validation")
    return labels.loc[mask].copy()


def _label_maturity_dates(labels: pd.DataFrame, horizon_weeks: int) -> pd.Series:
    horizon = _positive_int("horizon_weeks", horizon_weeks)
    column = f"label_end_date_{horizon}w"
    if column in labels.columns:
        return pd.to_datetime(labels[column], errors="coerce")
    return pd.to_datetime(labels["rebalance_date"], errors="coerce") + pd.DateOffset(weeks=horizon)


def _candidate_signals(labels: pd.DataFrame, rule: CalibrationCandidateRule) -> pd.DataFrame:
    frame = labels.copy()
    if frame.empty:
        return frame
    required = {"positive_signal", "negative_signal"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"labels missing required columns: {', '.join(missing)}")
    score = pd.to_numeric(frame.get("S_score_after_veto"), errors="coerce")
    if rule.positive_min_s_score_after_veto is not None:
        threshold = _finite_scalar(
            "positive_min_s_score_after_veto",
            rule.positive_min_s_score_after_veto,
        )
        frame["positive_signal"] = _bool_series(frame["positive_signal"]) & score.ge(threshold)
    if rule.negative_max_s_score_after_veto is not None:
        threshold = _finite_scalar(
            "negative_max_s_score_after_veto",
            rule.negative_max_s_score_after_veto,
        )
        frame["negative_signal"] = _bool_series(frame["negative_signal"]) & score.le(threshold)
    return frame


def _direction_metric(metrics: pd.DataFrame, direction: str, horizon: int) -> dict[str, float]:
    if metrics.empty:
        return {}
    rows = metrics[
        (metrics["direction"].astype(str) == direction)
        & (pd.to_numeric(metrics["horizon_weeks"], errors="coerce") == horizon)
    ]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _calibration_metric_value(metrics: dict[str, float], column: str) -> float:
    value = metrics.get(column, 0.0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if np.isfinite(number) else 0.0


def _candidate_direction_scope(rule: CalibrationCandidateRule) -> tuple[str, ...]:
    directions: list[str] = []
    if rule.positive_min_s_score_after_veto is not None:
        directions.append("positive")
    if rule.negative_max_s_score_after_veto is not None:
        directions.append("negative")
    return tuple(directions or ["positive", "negative"])


def _candidate_gate_status(
    *,
    row: dict,
    directions: Sequence[str],
    min_direction_signal_count: int,
    max_negative_hit_rate_degradation: float,
    min_fold_validation_hit_rate_delta: float,
) -> tuple[str, str, str]:
    reasons = ["final_holdout_not_evaluated"]
    for direction in directions:
        calibration_count = int(row[f"calibration_{direction}_signal_available_count"])
        validation_count = int(row[f"validation_{direction}_signal_available_count"])
        if (
            calibration_count < min_direction_signal_count
            or validation_count < min_direction_signal_count
        ):
            reasons.insert(0, "thin_sample")
            return "rejected_thin_sample", "do not promote", ";".join(reasons)
    if row["validation_negative_hit_rate_delta_vs_baseline"] < -max_negative_hit_rate_degradation:
        reasons.insert(0, "negative_signal_degraded")
        return "rejected_negative_signal_degraded", "do not promote", ";".join(reasons)
    if row["validation_positive_hit_rate_delta_vs_baseline"] < 0:
        reasons.insert(0, "positive_signal_degraded")
        return "rejected_positive_signal_degraded", "do not promote", ";".join(reasons)
    if row["minimum_validation_fold_hit_rate_delta"] < min_fold_validation_hit_rate_delta:
        reasons.insert(0, "unstable_folds")
        return "rejected_unstable_folds", "do not promote", ";".join(reasons)
    return "blocked_final_holdout_not_evaluated", "needs more testing", ";".join(reasons)


def calibration_candidate_search(
    labels: pd.DataFrame,
    splits: Sequence[WalkForwardSplit],
    *,
    horizons_weeks: Sequence[int] = (4, 13, 26, 52),
    candidate_rules: Sequence[CalibrationCandidateRule] | None = None,
    min_direction_signal_count: int = 20,
    max_negative_hit_rate_degradation: float = 0.0,
    min_fold_validation_hit_rate_delta: float = 0.0,
    drawdown_avoidance_threshold: float = -0.05,
) -> pd.DataFrame:
    """Evaluate deterministic calibration candidates without final-holdout leakage."""
    horizons = sorted({_positive_int("horizons_weeks", value) for value in horizons_weeks})
    min_count = _positive_int("min_direction_signal_count", min_direction_signal_count)
    negative_tolerance = _finite_scalar(
        "max_negative_hit_rate_degradation",
        max_negative_hit_rate_degradation,
    )
    if negative_tolerance < 0:
        raise ValueError("max_negative_hit_rate_degradation must be non-negative")
    fold_floor = _finite_scalar(
        "min_fold_validation_hit_rate_delta",
        min_fold_validation_hit_rate_delta,
    )
    rules = tuple(candidate_rules or (CalibrationCandidateRule(candidate_id="baseline"),))
    if not rules:
        raise ValueError("candidate_rules must contain at least one rule")
    if not splits:
        return pd.DataFrame(
            [
                {
                    "candidate_id": "no_ready_walk_forward_splits",
                    "horizon_weeks": horizons[0],
                    "gate_status": "skipped_insufficient_history",
                    "promotion_label": "do not promote",
                    "rejection_reasons": "no_ready_walk_forward_splits",
                    "selected_by_calibration": False,
                    "selection_source": "calibration_window_only",
                    "final_holdout_evaluated": False,
                    "final_holdout_rows_used": 0,
                    "live_promotion_allowed": False,
                }
            ]
        )

    rows: list[dict] = []
    for horizon in horizons:
        baseline_calibration_frames = []
        baseline_validation_frames = []
        for split in splits:
            baseline_calibration_frames.append(
                _windowed_labels_for_split(labels, split, "calibration", horizon)
            )
            baseline_validation_frames.append(
                _windowed_labels_for_split(labels, split, "validation", horizon)
            )
        baseline_calibration = pd.concat(baseline_calibration_frames, ignore_index=True)
        baseline_validation = pd.concat(baseline_validation_frames, ignore_index=True)
        baseline_calibration_metrics = calibration_label_metrics(
            baseline_calibration,
            horizons_weeks=(horizon,),
            drawdown_avoidance_threshold=drawdown_avoidance_threshold,
        )
        baseline_validation_metrics = calibration_label_metrics(
            baseline_validation,
            horizons_weeks=(horizon,),
            drawdown_avoidance_threshold=drawdown_avoidance_threshold,
        )
        baseline_cal_pos = _direction_metric(baseline_calibration_metrics, "positive", horizon)
        baseline_cal_neg = _direction_metric(baseline_calibration_metrics, "negative", horizon)
        baseline_val_pos = _direction_metric(baseline_validation_metrics, "positive", horizon)
        baseline_val_neg = _direction_metric(baseline_validation_metrics, "negative", horizon)

        for index, rule in enumerate(rules):
            candidate_calibration_frames = []
            candidate_validation_frames = []
            fold_validation_deltas = []
            for split in splits:
                calibration_frame = _candidate_signals(
                    _windowed_labels_for_split(labels, split, "calibration", horizon),
                    rule,
                )
                validation_frame = _candidate_signals(
                    _windowed_labels_for_split(labels, split, "validation", horizon),
                    rule,
                )
                candidate_calibration_frames.append(calibration_frame)
                candidate_validation_frames.append(validation_frame)
                fold_baseline = calibration_label_metrics(
                    _windowed_labels_for_split(labels, split, "validation", horizon),
                    horizons_weeks=(horizon,),
                    drawdown_avoidance_threshold=drawdown_avoidance_threshold,
                )
                fold_candidate = calibration_label_metrics(
                    validation_frame,
                    horizons_weeks=(horizon,),
                    drawdown_avoidance_threshold=drawdown_avoidance_threshold,
                )
                fold_validation_deltas.append(
                    min(
                        _calibration_metric_value(
                            _direction_metric(fold_candidate, "positive", horizon),
                            "hit_rate",
                        )
                        - _calibration_metric_value(
                            _direction_metric(fold_baseline, "positive", horizon),
                            "hit_rate",
                        ),
                        _calibration_metric_value(
                            _direction_metric(fold_candidate, "negative", horizon),
                            "hit_rate",
                        )
                        - _calibration_metric_value(
                            _direction_metric(fold_baseline, "negative", horizon),
                            "hit_rate",
                        ),
                    )
                )
            candidate_calibration = pd.concat(candidate_calibration_frames, ignore_index=True)
            candidate_validation = pd.concat(candidate_validation_frames, ignore_index=True)
            candidate_calibration_metrics = calibration_label_metrics(
                candidate_calibration,
                horizons_weeks=(horizon,),
                drawdown_avoidance_threshold=drawdown_avoidance_threshold,
            )
            candidate_validation_metrics = calibration_label_metrics(
                candidate_validation,
                horizons_weeks=(horizon,),
                drawdown_avoidance_threshold=drawdown_avoidance_threshold,
            )
            cand_cal_pos = _direction_metric(candidate_calibration_metrics, "positive", horizon)
            cand_cal_neg = _direction_metric(candidate_calibration_metrics, "negative", horizon)
            cand_val_pos = _direction_metric(candidate_validation_metrics, "positive", horizon)
            cand_val_neg = _direction_metric(candidate_validation_metrics, "negative", horizon)
            row = {
                "candidate_id": str(rule.candidate_id),
                "horizon_weeks": horizon,
                "rule_order": index,
                "positive_min_s_score_after_veto": rule.positive_min_s_score_after_veto,
                "negative_max_s_score_after_veto": rule.negative_max_s_score_after_veto,
                "selection_source": "calibration_window_only",
                "selected_by_calibration": False,
                "final_holdout_evaluated": False,
                "final_holdout_rows_used": 0,
                "live_promotion_allowed": False,
                "calibration_positive_hit_rate": _calibration_metric_value(cand_cal_pos, "hit_rate"),
                "calibration_negative_hit_rate": _calibration_metric_value(cand_cal_neg, "hit_rate"),
                "validation_positive_hit_rate": _calibration_metric_value(cand_val_pos, "hit_rate"),
                "validation_negative_hit_rate": _calibration_metric_value(cand_val_neg, "hit_rate"),
                "baseline_calibration_positive_hit_rate": _calibration_metric_value(baseline_cal_pos, "hit_rate"),
                "baseline_calibration_negative_hit_rate": _calibration_metric_value(baseline_cal_neg, "hit_rate"),
                "baseline_validation_positive_hit_rate": _calibration_metric_value(baseline_val_pos, "hit_rate"),
                "baseline_validation_negative_hit_rate": _calibration_metric_value(baseline_val_neg, "hit_rate"),
                "calibration_positive_signal_available_count": int(
                    _calibration_metric_value(cand_cal_pos, "signal_available_count")
                ),
                "calibration_negative_signal_available_count": int(
                    _calibration_metric_value(cand_cal_neg, "signal_available_count")
                ),
                "validation_positive_signal_available_count": int(
                    _calibration_metric_value(cand_val_pos, "signal_available_count")
                ),
                "validation_negative_signal_available_count": int(
                    _calibration_metric_value(cand_val_neg, "signal_available_count")
                ),
                "fold_count": len(splits),
                "minimum_validation_fold_hit_rate_delta": (
                    min(fold_validation_deltas) if fold_validation_deltas else 0.0
                ),
            }
            row["calibration_positive_hit_rate_delta_vs_baseline"] = (
                row["calibration_positive_hit_rate"]
                - row["baseline_calibration_positive_hit_rate"]
            )
            row["calibration_negative_hit_rate_delta_vs_baseline"] = (
                row["calibration_negative_hit_rate"]
                - row["baseline_calibration_negative_hit_rate"]
            )
            row["validation_positive_hit_rate_delta_vs_baseline"] = (
                row["validation_positive_hit_rate"]
                - row["baseline_validation_positive_hit_rate"]
            )
            row["validation_negative_hit_rate_delta_vs_baseline"] = (
                row["validation_negative_hit_rate"]
                - row["baseline_validation_negative_hit_rate"]
            )
            row["calibration_objective_delta"] = (
                row["calibration_positive_hit_rate_delta_vs_baseline"]
                + row["calibration_negative_hit_rate_delta_vs_baseline"]
            )
            directions = _candidate_direction_scope(rule)
            row["directions_changed"] = ",".join(directions)
            gate_status, promotion_label, rejection_reasons = _candidate_gate_status(
                row=row,
                directions=directions,
                min_direction_signal_count=min_count,
                max_negative_hit_rate_degradation=negative_tolerance,
                min_fold_validation_hit_rate_delta=fold_floor,
            )
            if str(rule.candidate_id) == "baseline":
                gate_status = "baseline_reference"
                promotion_label = "do not promote"
                rejection_reasons = "baseline_reference;final_holdout_not_evaluated"
            row["gate_status"] = gate_status
            row["promotion_label"] = promotion_label
            row["rejection_reasons"] = rejection_reasons
            rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    selectable = frame[frame["candidate_id"] != "baseline"].copy()
    if not selectable.empty:
        selectable = selectable.sort_values(
            ["calibration_objective_delta", "horizon_weeks", "candidate_id"],
            ascending=[False, True, True],
            kind="mergesort",
        )
        selected_index = selectable.index[0]
        frame.loc[selected_index, "selected_by_calibration"] = True
    bool_columns = ["selected_by_calibration", "final_holdout_evaluated", "live_promotion_allowed"]
    for column in bool_columns:
        frame[column] = frame[column].map(bool).astype(object)
    preferred = [
        "candidate_id",
        "horizon_weeks",
        "gate_status",
        "promotion_label",
        "rejection_reasons",
        "selected_by_calibration",
        "selection_source",
        "final_holdout_evaluated",
        "final_holdout_rows_used",
        "live_promotion_allowed",
        "directions_changed",
        "positive_min_s_score_after_veto",
        "negative_max_s_score_after_veto",
        "calibration_objective_delta",
        "calibration_positive_hit_rate_delta_vs_baseline",
        "calibration_negative_hit_rate_delta_vs_baseline",
        "validation_positive_hit_rate_delta_vs_baseline",
        "validation_negative_hit_rate_delta_vs_baseline",
        "calibration_positive_signal_available_count",
        "calibration_negative_signal_available_count",
        "validation_positive_signal_available_count",
        "validation_negative_signal_available_count",
        "fold_count",
        "minimum_validation_fold_hit_rate_delta",
    ]
    columns = [column for column in preferred if column in frame.columns]
    columns.extend(column for column in frame.columns if column not in columns)
    return frame[columns].sort_values(
        ["horizon_weeks", "selected_by_calibration", "rule_order"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)


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
