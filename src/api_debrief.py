"""Read-only debrief payload for the B-170 React migration."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .run_journal import DEFAULT_JOURNAL_PATH, list_runs, load_run_details


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
        return result if result == result else None  # NaN guard
    except (TypeError, ValueError):
        return None


def build_debrief_payload(
    journal_path: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return run journal history and decisions without OHLCV or forward outcomes."""
    path = Path(journal_path) if journal_path is not None else DEFAULT_JOURNAL_PATH

    if not path.exists():
        return {
            "api_version": "v1",
            "generated_at": _utc_now(),
            "runs": [],
            "decisions": [],
        }

    runs = list_runs(path, limit=int(limit))

    result_runs: list[dict[str, Any]] = []
    result_decisions: list[dict[str, Any]] = []

    for run in runs:
        result_runs.append({
            "run_id": run["run_id"],
            "started_at_utc": run["started_at_utc"],
            "provider": run.get("provider"),
            "universe_count": run.get("universe_count", 0),
        })

        try:
            details = load_run_details(path, run["run_id"])
        except (KeyError, Exception):
            continue

        scores_by_ticker: dict[str, dict[str, Any]] = {
            str(row.get("ticker", "")).upper(): row
            for row in details.get("scores", [])
            if row.get("ticker")
        }

        for decision in details.get("decisions", []):
            ticker = decision.get("ticker")
            if not ticker:
                continue
            symbol = str(ticker).upper()
            score = scores_by_ticker.get(symbol, {})
            result_decisions.append({
                "run_id": run["run_id"],
                "started_at_utc": run["started_at_utc"],
                "ticker": symbol,
                "action": decision.get("action"),
                "decision_type": decision.get("decision_type"),
                "rationale": decision.get("rationale"),
                "state": score.get("state"),
                "s_score": _float_or_none(score.get("s_score")),
                "f_score": _float_or_none(score.get("f_score")),
            })

    return {
        "api_version": "v1",
        "generated_at": _utc_now(),
        "runs": result_runs,
        "decisions": result_decisions,
    }
