"""Read-only dashboard snapshot payloads for the React migration shell."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

import math
import statistics

from .bluf import build_bluf, load_sector_map
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
        "net_flow_21d": _float_or_none(_payload_value(row, "net_flow_21d")),
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
    # Journal is append-only (chronological). We deduplicate by (ticker, date) so that
    # same-day oscillations (e.g. SOXX EXIT→WARN then WARN→EXIT in two separate runs)
    # show only the final recorded state change for each ticker per day. Later lines
    # in the file overwrite earlier ones for the same key.
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
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
                deduped[(transition["ticker"], transition["date"])] = transition
    rows = list(deduped.values())
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


def _watchlist_tickers(path: str | Path | None = DEFAULT_SAVED_INPUTS_PATH) -> list[str]:
    tickers: list[str] = []
    for item in load_saved_inputs(path):
        if item.kind == 'watchlist':
            tickers.extend(t.upper() for t in item.tickers)
    return list(dict.fromkeys(tickers))


def _safe_median(values: list[float]) -> float | None:
    finite = [v for v in values if v is not None and not math.isnan(v)]
    if not finite:
        return None
    return statistics.median(finite)


def _class_rotation_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build cross-class rotation ranking from already-computed row payloads.

    Groups rows by asset_class and computes aggregate metrics on a common
    (non-z-scored within-class) basis, then ranks classes by a simple
    equal-weight composite of z-scored aggregates.
    """
    from collections import defaultdict

    buckets: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {
            "momentum": [],
            "breadth": [],
            "cmf": [],
            "mansfield_rs": [],
            "net_flow_21d": [],
        }
    )

    for row in rows:
        cls = str(row.get("asset_class") or "Other")
        if cls in ("Benchmark", ""):
            continue
        pillar = row.get("pillar_scores", {}) or {}
        payload = row.get("payload", {}) or {}

        for dest, src in [
            ("momentum", row.get("momentum_pct")),
            ("cmf", row.get("cmf21")),
            ("mansfield_rs", pillar.get("mansfield_rs")),
            ("breadth", pillar.get("breadth_50d")),
            ("net_flow_21d", payload.get("net_flow_21d")),
        ]:
            v = _float_or_none(src)
            if v is not None:
                buckets[cls][dest].append(v)

    if not buckets:
        return []

    # Aggregate per class
    class_aggs: list[dict[str, Any]] = []
    for cls, series in buckets.items():
        class_aggs.append({
            "asset_class": cls,
            "agg_momentum": _safe_median(series["momentum"]),
            "agg_breadth": _safe_median(series["breadth"]),
            "agg_cmf": _safe_median(series["cmf"]),
            "agg_mansfield_rs": _safe_median(series["mansfield_rs"]),
            "agg_net_flow_21d": sum(
                v for v in series["net_flow_21d"] if v is not None and not math.isnan(v)
            ) or None,
        })

    # Z-score each aggregate across the cross-class distribution
    agg_keys = ["agg_momentum", "agg_breadth", "agg_cmf", "agg_mansfield_rs", "agg_net_flow_21d"]

    def _z_list(key: str) -> dict[str, float]:
        vals = {d["asset_class"]: d[key] for d in class_aggs if d[key] is not None}
        if len(vals) < 2:
            return {cls: 0.0 for cls in vals}
        mean = sum(vals.values()) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals.values()) / len(vals)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return {cls: 0.0 for cls in vals}
        return {cls: (v - mean) / std for cls, v in vals.items()}

    z_maps = {key: _z_list(key) for key in agg_keys}

    for d in class_aggs:
        cls = d["asset_class"]
        d["class_score"] = sum(
            z_maps[key].get(cls, 0.0) for key in agg_keys
        )

    # Rank by class_score (1 = best)
    sorted_aggs = sorted(class_aggs, key=lambda d: d["class_score"], reverse=True)
    for rank, d in enumerate(sorted_aggs, start=1):
        d["rank"] = rank

    return sorted_aggs


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

    # Task 2: surface degraded_run in the snapshot so the UI can label runs
    # that were computed with fewer than the full 7 pillars.
    run_meta = dict(run)
    run_degraded = bool(run_meta.get("metadata", {}).get("degraded_run", False))

    # Task 7: cross-class rotation — which bucket is capital rotating into?
    class_rotation = _class_rotation_from_rows(rows)

    # Bottom-line-up-front summary: leading sectors, top stocks in them, and
    # the user's holdings and watchlist mapped to sectors.
    run_metadata = dict(run.get('metadata', {}) or {})
    bluf = build_bluf(
        rows=rows,
        sector_map=load_sector_map(),
        holdings=[item['ticker'] for item in positions],
        watchlist=_watchlist_tickers(saved_inputs_path),
        risk_on=run_metadata.get('risk_on'),
        degraded=run_degraded,
        flow_coverage=_float_or_none(run_metadata.get('flow_coverage')),
    )

    return {
        "api_version": "v1",
        "generated_at": generated_at or _utc_iso(),
        "status": "ready",
        "message": "Latest run-journal snapshot loaded.",
        "run": run,
        "degraded_run": run_degraded,
        "summary": {
            "universe_count": len(rows),
            "state_counts": dict(state_counts),
            "quadrant_counts": dict(quadrant_counts),
            "decision_counts": dict(decision_counts),
        },
        "rows": rows,
        "decisions": decisions,
        "focus": focus,
        "class_rotation": class_rotation,
        "bluf": bluf,
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
                "class_rotation": class_rotation,
            },
        },
    }
