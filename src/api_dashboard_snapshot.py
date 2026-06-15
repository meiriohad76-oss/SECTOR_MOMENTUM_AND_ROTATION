"""Read-only dashboard snapshot payloads for the React migration shell."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .run_journal import DEFAULT_JOURNAL_PATH, list_runs, load_run_details
from .saved_inputs import DEFAULT_SAVED_INPUTS_PATH, load_saved_inputs
from .ticker_identity import ticker_display_name

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRANSITION_JOURNAL_PATH = Path(
    os.environ.get("STATE_TRANSITION_JOURNAL", ROOT / "data" / "state_transitions.jsonl")
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _score_value(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = _float_or_none(row.get(key))
    return default if value is None else value


def _payload_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    payload = row.get("payload", {})
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return default


def _pillar_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    pillars = row.get("pillar_scores", {})
    if isinstance(pillars, Mapping):
        return pillars.get(key, default)
    return default


def _quadrant(row: Mapping[str, Any]) -> str:
    value = _clean_text(_payload_value(row, "rrg_quadrant"))
    if value:
        return value
    rs_ratio = _float_or_none(_pillar_value(row, "rs_ratio"))
    rs_momentum = _float_or_none(_pillar_value(row, "rs_momentum"))
    if rs_ratio is None or rs_momentum is None:
        return "Unknown"
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "Leading"
    if rs_ratio >= 100 and rs_momentum < 100:
        return "Weakening"
    if rs_ratio < 100 and rs_momentum >= 100:
        return "Improving"
    return "Lagging"


def _row_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    ticker = _clean_text(row.get("ticker")).upper()
    state = _clean_text(row.get("state"), "UNKNOWN")
    identity = ticker_display_name(ticker)
    return {
        "ticker": ticker,
        "identity": identity,
        "display_label": f"{ticker} | {identity}" if identity != ticker else ticker,
        "asset_class": _clean_text(row.get("asset_class"), "Other"),
        "state": state,
        "s_score": _score_value(row, "s_score"),
        "f_score": _score_value(row, "f_score"),
        "quadrant": _quadrant(row),
        "momentum_pct": _float_or_none(_pillar_value(row, "mom_12_1")),
        "rs_ratio": _float_or_none(_pillar_value(row, "rs_ratio")),
        "rs_momentum": _float_or_none(_pillar_value(row, "rs_momentum")),
        "cmf21": _float_or_none(_pillar_value(row, "cmf21")),
        "adv_20d": _float_or_none(_payload_value(row, "adv_20d")),
        "pillar_scores": dict(row.get("pillar_scores", {}) or {}),
        "payload": dict(row.get("payload", {}) or {}),
    }


def _decision_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    ticker = _clean_text(row.get("ticker")).upper()
    return {
        "decision_type": _clean_text(row.get("decision_type"), "decision"),
        "ticker": ticker,
        "identity": ticker_display_name(ticker) if ticker else "",
        "action": _clean_text(row.get("action"), "REVIEW"),
        "rationale": _clean_text(row.get("rationale")),
        "payload": dict(row.get("payload", {}) or {}),
    }


def _transition_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    ticker = _clean_text(row.get("ticker")).upper()
    return {
        "ticker": ticker,
        "identity": ticker_display_name(ticker) if ticker else "",
        "from": _clean_text(row.get("from"), "UNKNOWN"),
        "to": _clean_text(row.get("to"), "UNKNOWN"),
        "date": _clean_text(row.get("date")),
    }


def _transition_sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_clean_text(row.get("date")), _clean_text(row.get("ticker")).upper())


def _transition_payloads(path: str | Path | None = DEFAULT_TRANSITION_JOURNAL_PATH, limit: int = 25) -> list[dict[str, Any]]:
    if path is None:
        return []
    journal_path = Path(path)
    if not journal_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            transition = _transition_payload(parsed)
            if transition["ticker"]:
                rows.append(transition)
    rows.sort(key=_transition_sort_key, reverse=True)
    return rows[:limit]


def _top_rows(rows: list[dict[str, Any]], reverse: bool = True, limit: int = 8) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: float(row.get("s_score", 0.0)), reverse=reverse)[:limit]


def _position_payloads(path: str | Path | None = DEFAULT_SAVED_INPUTS_PATH, limit: int = 8) -> list[dict[str, Any]]:
    portfolios = [item for item in load_saved_inputs(path) if item.kind == "portfolio" and item.holdings]
    if not portfolios:
        return []
    latest = max(portfolios, key=lambda item: item.updated_at or "")
    rows: list[dict[str, Any]] = []
    for holding in latest.holdings[:limit]:
        shares = _float_or_none(holding.shares)
        cost_basis = _float_or_none(holding.cost_basis)
        market_value = _float_or_none(holding.market_value)
        cost = shares * cost_basis if shares is not None and cost_basis is not None else None
        pnl_pct = None
        if cost is not None and cost > 0 and market_value is not None:
            pnl_pct = (market_value - cost) / cost
        rows.append(
            {
                "ticker": holding.ticker.upper(),
                "identity": ticker_display_name(holding.ticker.upper()),
                "shares": shares,
                "cost_basis": cost_basis,
                "market_value": market_value,
                "cost": cost,
                "unrealized_pct": pnl_pct,
                "account": holding.account or "",
                "notes": holding.notes or "",
                "source_name": latest.name,
                "updated_at": latest.updated_at,
            }
        )
    return rows


def build_latest_dashboard_snapshot_payload(
    *,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    saved_inputs_path: str | Path | None = DEFAULT_SAVED_INPUTS_PATH,
    transition_journal_path: str | Path | None = DEFAULT_TRANSITION_JOURNAL_PATH,
    focus_ticker: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    runs = list_runs(journal_path, limit=1)
    if not runs:
        return {
            "api_version": "v1",
            "generated_at": generated_at or _utc_iso(),
            "status": "empty",
            "message": "No dashboard run journal entries are available yet.",
            "run": None,
            "summary": {
                "universe_count": 0,
                "state_counts": {},
                "quadrant_counts": {},
                "decision_counts": {},
            },
            "rows": [],
            "decisions": [],
            "focus": None,
            "screens": {"overview": {"positions": [], "transitions": []}, "deepdive": {}, "rotation": {}},
        }

    details = load_run_details(journal_path, str(runs[0]["run_id"]))
    run = dict(details["run"])
    rows = [_row_payload(row) for row in details.get("scores", [])]
    decisions = [_decision_payload(row) for row in details.get("decisions", [])]
    focus = None
    requested = _clean_text(focus_ticker).upper()
    if requested:
        focus = next((row for row in rows if row["ticker"] == requested), None)
    if focus is None:
        focus = max(rows, key=lambda row: float(row.get("s_score", 0.0)), default=None)

    state_counts = Counter(str(row.get("state", "UNKNOWN")) for row in rows)
    quadrant_counts = Counter(str(row.get("quadrant", "Unknown")) for row in rows)
    decision_counts = Counter(str(row.get("action", "REVIEW")) for row in decisions)
    leaders = _top_rows(rows, reverse=True, limit=8)
    risks = _top_rows(rows, reverse=False, limit=8)
    sectors = [row for row in rows if row.get("asset_class") == "US Sectors"] or rows

    positions = _position_payloads(saved_inputs_path)
    transitions = _transition_payloads(transition_journal_path)

    return {
        "api_version": "v1",
        "generated_at": generated_at or _utc_iso(),
        "status": "ready",
        "message": "Latest run-journal snapshot loaded.",
        "run": run,
        "summary": {
            "universe_count": len(rows),
            "state_counts": dict(state_counts),
            "quadrant_counts": dict(quadrant_counts),
            "decision_counts": dict(decision_counts),
        },
        "rows": rows,
        "decisions": decisions,
        "focus": focus,
        "screens": {
            "overview": {
                "leaders": leaders,
                "risks": risks,
                "actions": decisions[:12],
                "transitions": transitions,
                "positions": positions,
            },
            "deepdive": {"focus": focus, "peer_rows": rows[:12]},
            "rotation": {
                "sectors": sectors,
                "leaders": sorted(sectors, key=lambda row: float(row.get("s_score", 0.0)), reverse=True)[:8],
                "laggards": sorted(sectors, key=lambda row: float(row.get("s_score", 0.0)))[:8],
            },
        },
    }
