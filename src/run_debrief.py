"""Pure debrief engine for saved run-journal decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

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
    run_metadata: Mapping[str, Any] = field(default_factory=dict)
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


def _float_value(value: Any) -> float | None:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _macro_snapshot(record: DecisionDebrief) -> dict[str, Mapping[str, Any]]:
    snapshot = record.run_metadata.get("fred_macro_snapshot")
    if not isinstance(snapshot, Mapping):
        return {}
    return {
        str(series_id).upper(): entry
        for series_id, entry in snapshot.items()
        if isinstance(entry, Mapping)
    }


def _macro_condition(entry: Mapping[str, Any]) -> str:
    delta = _float_value(entry.get("delta"))
    if delta is not None:
        if math.isclose(delta, 0.0, abs_tol=0.0001):
            return "flat"
        return "rising" if delta > 0 else "falling"

    yoy = _float_value(entry.get("yoy_pct"))
    if yoy is not None:
        if math.isclose(yoy, 0.0, abs_tol=0.0001):
            return "yoy_flat"
        return "yoy_positive" if yoy > 0 else "yoy_negative"

    return "level_available"


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


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
                run_metadata=run.get("metadata", {}),
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


def summarize_debriefs_by_macro_condition(
    records: list[DecisionDebrief],
    horizon: str = "4w",
    series_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    selected_series = tuple(str(series_id).upper() for series_id in series_ids) if series_ids else None
    buckets: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for record in records:
        outcome = record.outcomes.get(horizon)
        if outcome is None:
            continue
        snapshot = _macro_snapshot(record)
        if not snapshot:
            continue

        series_to_scan = selected_series or tuple(sorted(snapshot))
        for series_id in series_to_scan:
            entry = snapshot.get(series_id)
            if entry is None:
                continue
            group = str(entry.get("group") or "Macro")
            label = str(entry.get("label") or series_id)
            condition = _macro_condition(entry)
            key = (series_id, group, label, condition, record.action, str(horizon))
            bucket = buckets.setdefault(
                key,
                {
                    "decision_count": 0,
                    "hits": 0,
                    "available_returns": [],
                    "available_drawdowns": [],
                },
            )
            bucket["decision_count"] += 1
            if outcome.forward_return is None or outcome.hit is None:
                continue
            bucket["available_returns"].append(float(outcome.forward_return))
            if outcome.max_drawdown is not None:
                bucket["available_drawdowns"].append(float(outcome.max_drawdown))
            if outcome.hit:
                bucket["hits"] += 1

    rows: list[dict[str, Any]] = []
    for (series_id, group, label, condition, action, horizon_name), bucket in sorted(buckets.items()):
        available_returns = bucket["available_returns"]
        available_count = len(available_returns)
        if available_count == 0:
            continue
        rows.append(
            {
                "macro_series": series_id,
                "macro_group": group,
                "macro_label": label,
                "macro_condition": condition,
                "action": action,
                "horizon": horizon_name,
                "decision_count": bucket["decision_count"],
                "available_count": available_count,
                "hit_rate": (bucket["hits"] / available_count) if available_count else None,
                "average_forward_return": _mean(available_returns),
                "average_max_drawdown": _mean(bucket["available_drawdowns"]),
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


def debrief_outcome_rows(records: Sequence[DecisionDebrief]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        for horizon, outcome in record.outcomes.items():
            rows.append(
                {
                    "run_id": record.run_id,
                    "started_at_utc": record.started_at_utc,
                    "ticker": record.ticker,
                    "action": record.action,
                    "decision_type": record.decision_type,
                    "state": record.state,
                    "s_score": _float_value(record.s_score),
                    "f_score": _float_value(record.f_score),
                    "rationale": record.rationale,
                    "horizon": horizon,
                    "days": outcome.days,
                    "status": outcome.status,
                    "start_date": outcome.start_date,
                    "end_date": outcome.end_date,
                    "start_price": outcome.start_price,
                    "end_price": outcome.end_price,
                    "forward_return": outcome.forward_return,
                    "max_drawdown": outcome.max_drawdown,
                    "hit": outcome.hit,
                }
            )
    return rows


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_percent(value: Any) -> str:
    number = _float_value(value)
    if number is None:
        return "-"
    return f"{number * 100:.1f}%"


def _format_table_cell(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return text.strip() or "-"


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    header_line = "| " + " | ".join(_format_table_cell(header) for header in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_format_table_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header_line, separator, *body])


def build_debrief_markdown_report(
    records: Sequence[DecisionDebrief],
    *,
    summary_rows: Sequence[Mapping[str, Any]] | None = None,
    macro_rows: Sequence[Mapping[str, Any]] | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    generated_at_utc: str | None = None,
) -> str:
    summaries = list(summary_rows) if summary_rows is not None else summarize_debriefs(list(records))
    macro_summaries = (
        list(macro_rows)
        if macro_rows is not None
        else summarize_debriefs_by_macro_condition(list(records), horizon="4w")
    )
    candidates = (
        list(candidate_rows)
        if candidate_rows is not None
        else threshold_review_candidates(list(records), horizon="4w", min_abs_return=0.02)
    )
    outcome_rows = debrief_outcome_rows(records)
    available_rows = [row for row in outcome_rows if row["forward_return"] is not None and row["hit"] is not None]

    lines = [
        "# Run Debrief Report",
        "",
        f"Generated: {generated_at_utc or _utc_timestamp()}",
        "",
        "Methodology debrief export is analysis-only; it does not change live scoring, alerts, provider behavior, or recommendations.",
        "",
        f"Decisions analyzed: {len(records)}",
        f"Outcome rows: {len(outcome_rows)}",
        f"Matured outcome rows: {len(available_rows)}",
        "",
        "## Outcome Summary",
        "",
    ]

    if summaries:
        lines.append(
            _markdown_table(
                ["Action", "Horizon", "Decisions", "Matured", "Hit Rate", "Avg Forward Return"],
                [
                    [
                        row.get("action"),
                        row.get("horizon"),
                        row.get("decision_count"),
                        row.get("available_count"),
                        _format_percent(row.get("hit_rate")),
                        _format_percent(row.get("average_forward_return")),
                    ]
                    for row in summaries
                ],
            )
        )
    else:
        lines.append("No matured outcome summary is available yet.")

    lines.extend(["", "## Macro-Conditioned Outcomes", ""])
    if macro_summaries:
        lines.append(
            _markdown_table(
                [
                    "Macro Group",
                    "Macro",
                    "Series",
                    "Condition",
                    "Action",
                    "Horizon",
                    "Decisions",
                    "Matured",
                    "Hit Rate",
                    "Avg Forward Return",
                    "Avg Max Drawdown",
                ],
                [
                    [
                        row.get("macro_group"),
                        row.get("macro_label"),
                        row.get("macro_series"),
                        row.get("macro_condition"),
                        row.get("action"),
                        row.get("horizon"),
                        row.get("decision_count"),
                        row.get("available_count"),
                        _format_percent(row.get("hit_rate")),
                        _format_percent(row.get("average_forward_return")),
                        _format_percent(row.get("average_max_drawdown")),
                    ]
                    for row in macro_summaries
                ],
            )
        )
    else:
        lines.append("No macro-conditioned matured outcomes are available yet.")

    lines.extend(["", "## Threshold Review Candidates", ""])
    if candidates:
        lines.append(
            _markdown_table(
                ["Ticker", "Action", "Horizon", "Forward Return", "State", "Rationale"],
                [
                    [
                        row.get("ticker"),
                        row.get("action"),
                        row.get("horizon"),
                        _format_percent(row.get("forward_return")),
                        row.get("state"),
                        row.get("rationale"),
                    ]
                    for row in candidates
                ],
            )
        )
    else:
        lines.append("No threshold review candidates met the export threshold.")

    return "\n".join(lines).rstrip() + "\n"
