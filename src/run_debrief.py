"""Pure debrief engine for saved run-journal decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .data import close_price
from .run_journal import list_runs, load_run_details


FORWARD_WINDOWS = {"1w": 5, "4w": 20, "13w": 65, "26w": 130}
POSITIVE_ACTIONS = {"BUY", "ADD", "HOLD"}
DEFENSIVE_ACTIONS = {"EXIT", "WATCH", "SELL", "TRIM"}


@dataclass(frozen=True)
class ForwardOutcome:
    horizon: str
    days: int
    start_date: str | None
    end_date: str | None
    start_price: float | None
    end_price: float | None
    forward_return: float | None
    max_drawdown: float | None
    hit: bool | None
    status: str


@dataclass(frozen=True)
class DecisionDebrief:
    run_id: str
    started_at_utc: str
    ticker: str
    action: str
    decision_type: str
    rationale: str | None
    state: str | None
    s_score: float | None
    f_score: float | None
    outcomes: dict[str, ForwardOutcome]
    payload: Mapping[str, Any] = field(default_factory=dict)


def _na_outcome(
    horizon: str,
    days: int,
    status: str,
    start_date: str | None = None,
    start_price: float | None = None,
) -> ForwardOutcome:
    return ForwardOutcome(
        horizon=horizon,
        days=days,
        start_date=start_date,
        end_date=None,
        start_price=start_price,
        end_price=None,
        forward_return=None,
        max_drawdown=None,
        hit=None,
        status=status,
    )


def _run_start_date(started_at_utc: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(started_at_utc)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp.normalize()


def _price_series(frame: pd.DataFrame) -> pd.Series:
    series = close_price(frame)
    series = pd.to_numeric(series, errors="coerce").dropna()
    series.index = pd.to_datetime(series.index)
    if series.index.tz is not None:
        series.index = series.index.tz_convert(None)
    return series.sort_index()


def _hit_for_action(action: str, forward_return: float) -> tuple[bool | None, str]:
    normalized = str(action).upper()
    if normalized in POSITIVE_ACTIONS:
        return forward_return > 0.0, "available"
    if normalized in DEFENSIVE_ACTIONS:
        return forward_return <= 0.0, "available"
    return None, "unsupported_action"


def compute_forward_outcomes(
    started_at_utc: str,
    ticker: str,
    action: str,
    ohlcv: Mapping[str, pd.DataFrame],
    windows: Mapping[str, int] = FORWARD_WINDOWS,
) -> dict[str, ForwardOutcome]:
    symbol = str(ticker).upper()
    if symbol not in ohlcv:
        return {horizon: _na_outcome(horizon, int(days), "missing_ticker") for horizon, days in windows.items()}

    try:
        prices = _price_series(ohlcv[symbol])
    except (AttributeError, KeyError, TypeError, ValueError):
        return {horizon: _na_outcome(horizon, int(days), "missing_prices") for horizon, days in windows.items()}
    if prices.empty:
        return {horizon: _na_outcome(horizon, int(days), "missing_prices") for horizon, days in windows.items()}

    start = _run_start_date(started_at_utc)
    future = prices.loc[prices.index >= start]
    if future.empty:
        return {horizon: _na_outcome(horizon, int(days), "no_baseline") for horizon, days in windows.items()}

    start_date = pd.Timestamp(future.index[0])
    start_price = float(future.iloc[0])
    if start_price <= 0:
        return {
            horizon: _na_outcome(
                horizon,
                int(days),
                "invalid_baseline",
                start_date=start_date.date().isoformat(),
                start_price=start_price,
            )
            for horizon, days in windows.items()
        }
    outcomes: dict[str, ForwardOutcome] = {}
    for horizon, raw_days in windows.items():
        days = int(raw_days)
        if len(future) <= days:
            outcomes[str(horizon)] = _na_outcome(
                str(horizon),
                days,
                "insufficient_history",
                start_date=start_date.date().isoformat(),
                start_price=start_price,
            )
            continue

        end_date = pd.Timestamp(future.index[days])
        end_price = float(future.iloc[days])
        path = future.iloc[: days + 1].astype(float)
        forward_return = end_price / start_price - 1.0
        drawdown = path / path.cummax() - 1.0
        hit, status = _hit_for_action(action, forward_return)
        outcomes[str(horizon)] = ForwardOutcome(
            horizon=str(horizon),
            days=days,
            start_date=start_date.date().isoformat(),
            end_date=end_date.date().isoformat(),
            start_price=start_price,
            end_price=end_price,
            forward_return=float(forward_return),
            max_drawdown=float(drawdown.min()),
            hit=hit,
            status=status,
        )
    return outcomes


def _score_by_ticker(details: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["ticker"]).upper(): row for row in details.get("scores", []) if row.get("ticker")}


def debrief_run_details(
    details: Mapping[str, Any],
    ohlcv: Mapping[str, pd.DataFrame],
    windows: Mapping[str, int] = FORWARD_WINDOWS,
) -> list[DecisionDebrief]:
    run = details["run"]
    scores = _score_by_ticker(details)
    out: list[DecisionDebrief] = []
    for decision in details.get("decisions", []):
        ticker = decision.get("ticker")
        if not ticker:
            continue
        symbol = str(ticker).upper()
        score = scores.get(symbol, {})
        action = str(decision.get("action") or "").upper()
        out.append(
            DecisionDebrief(
                run_id=str(run["run_id"]),
                started_at_utc=str(run["started_at_utc"]),
                ticker=symbol,
                action=action,
                decision_type=str(decision.get("decision_type") or ""),
                rationale=decision.get("rationale"),
                state=score.get("state"),
                s_score=score.get("s_score"),
                f_score=score.get("f_score"),
                outcomes=compute_forward_outcomes(
                    str(run["started_at_utc"]),
                    symbol,
                    action,
                    ohlcv,
                    windows=windows,
                ),
                payload=decision.get("payload", {}),
            )
        )
    return out


def debrief_journal(
    db_path: str | Path,
    ohlcv: Mapping[str, pd.DataFrame],
    windows: Mapping[str, int] = FORWARD_WINDOWS,
    limit: int = 50,
) -> list[DecisionDebrief]:
    out: list[DecisionDebrief] = []
    for run in reversed(list_runs(db_path, limit=limit)):
        details = load_run_details(db_path, run["run_id"])
        out.extend(debrief_run_details(details, ohlcv, windows=windows))
    return out


def summarize_debriefs(records: list[DecisionDebrief]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[ForwardOutcome]] = {}
    for record in records:
        for horizon, outcome in record.outcomes.items():
            buckets.setdefault((record.action, horizon), []).append(outcome)

    rows: list[dict[str, Any]] = []
    for (action, horizon), outcomes in sorted(buckets.items()):
        available = [outcome for outcome in outcomes if outcome.forward_return is not None and outcome.hit is not None]
        hits = [outcome for outcome in available if outcome.hit]
        rows.append(
            {
                "action": action,
                "horizon": horizon,
                "decision_count": len(outcomes),
                "available_count": len(available),
                "hit_rate": (len(hits) / len(available)) if available else None,
                "average_forward_return": (
                    sum(float(outcome.forward_return) for outcome in available) / len(available)
                    if available
                    else None
                ),
            }
        )
    return rows


def threshold_review_candidates(
    records: list[DecisionDebrief],
    horizon: str = "4w",
    min_abs_return: float = 0.02,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        outcome = record.outcomes.get(horizon)
        if outcome is None or outcome.hit is not False or outcome.forward_return is None:
            continue
        if abs(outcome.forward_return) < float(min_abs_return):
            continue
        candidates.append(
            {
                "run_id": record.run_id,
                "ticker": record.ticker,
                "action": record.action,
                "horizon": horizon,
                "forward_return": outcome.forward_return,
                "state": record.state,
                "s_score": record.s_score,
                "f_score": record.f_score,
                "rationale": record.rationale,
            }
        )
    return sorted(candidates, key=lambda row: abs(float(row["forward_return"])), reverse=True)
