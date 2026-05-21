"""Append-only run journal for methodology decisions and later debriefs."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOURNAL_PATH = ROOT / "data" / "run_journal" / "runs.sqlite"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    started_at_utc: str
    git_sha: str | None = None
    app_version: str | None = None
    provider: str | None = None
    universe_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredSnapshotRecord:
    ticker: str
    asset_class: str | None = None
    state: str | None = None
    s_score: float | None = None
    f_score: float | None = None
    pillar_scores: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionRecord:
    decision_type: str
    action: str
    ticker: str | None = None
    rationale: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JournalAppendResult:
    ok: bool
    run_id: str | None = None
    error: str | None = None


PILLAR_SCORE_COLUMNS = (
    "mom_12_1",
    "mansfield_rs",
    "rs_ratio",
    "rs_momentum",
    "cycle_tilt",
    "breadth_50d",
    "cmf21",
    "obv_slope",
    "mfi14",
    "rvol",
    "dist_days_25",
    "etf_primary_flow_5d_pct",
    "block_trade_upside_ratio",
    "dark_pool_pct",
    "short_interest_delta_15d",
    "thirteen_f_net_buys_q",
)
SCORED_PRIMARY_COLUMNS = {"class", "state", "S_score", "F_score"}
BLUF_ACTIONS = {"exit": "EXIT", "warn": "WATCH", "buy": "BUY"}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _to_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), default=_json_default, sort_keys=True, separators=(",", ":"))


def _from_json(payload: str) -> dict[str, Any]:
    if not payload:
        return {}
    return json.loads(payload)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if bool(value != value):
            return None
    except (TypeError, ValueError):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): cleaned
            for key, item in value.items()
            if (cleaned := _clean_json_value(item)) is not None
        }
    if isinstance(value, (list, tuple)):
        return [cleaned for item in value if (cleaned := _clean_json_value(item)) is not None]
    return _clean_scalar(value)


def _clean_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): cleaned
        for key, value in payload.items()
        if (cleaned := _clean_json_value(value)) is not None
    }


def _float_or_none(value: Any) -> float | None:
    cleaned = _clean_scalar(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _text_or_none(value: Any) -> str | None:
    cleaned = _clean_scalar(value)
    if cleaned is None:
        return None
    return str(cleaned)


def _compact_run_timestamp(started_at_utc: str) -> str:
    text = str(started_at_utc).replace("+00:00", "Z")
    return "".join(ch for ch in text if ch.isalnum())


def scored_snapshot_records_from_frame(scored_df: Any) -> list[ScoredSnapshotRecord]:
    columns = set(getattr(scored_df, "columns", []))
    payload_columns = [
        column
        for column in getattr(scored_df, "columns", [])
        if column not in SCORED_PRIMARY_COLUMNS and column not in PILLAR_SCORE_COLUMNS
    ]

    records: list[ScoredSnapshotRecord] = []
    for ticker, row in scored_df.iterrows():
        pillar_scores = {
            column: cleaned
            for column in PILLAR_SCORE_COLUMNS
            if column in columns and (cleaned := _clean_json_value(row.get(column))) is not None
        }
        payload = {
            str(column): cleaned
            for column in payload_columns
            if (cleaned := _clean_json_value(row.get(column))) is not None
        }
        records.append(
            ScoredSnapshotRecord(
                ticker=str(ticker).upper(),
                asset_class=_text_or_none(row.get("class")),
                state=_text_or_none(row.get("state")),
                s_score=_float_or_none(row.get("S_score")),
                f_score=_float_or_none(row.get("F_score")),
                pillar_scores=pillar_scores,
                payload=payload,
            )
        )
    return records


def decision_records_from_bluf(bluf: Mapping[str, Any]) -> list[DecisionRecord]:
    decisions: list[DecisionRecord] = []
    actions = bluf.get("actions", []) if isinstance(bluf, Mapping) else []
    for group in actions:
        if not isinstance(group, Mapping):
            continue
        kind = str(group.get("kind") or "").strip().lower()
        action = BLUF_ACTIONS.get(kind, kind.upper() or "REVIEW")
        label = _text_or_none(group.get("label"))
        eta = _text_or_none(group.get("eta"))
        state = _text_or_none(group.get("state"))
        payload = _clean_mapping({"kind": kind, "label": label, "eta": eta, "state": state})
        for item in group.get("tickers", []):
            if not isinstance(item, Mapping):
                continue
            ticker = _text_or_none(item.get("t") or item.get("ticker"))
            if not ticker:
                continue
            decisions.append(
                DecisionRecord(
                    decision_type="bluf",
                    ticker=ticker.upper(),
                    action=action,
                    rationale=_text_or_none(item.get("note")),
                    payload=payload,
                )
            )
    return decisions


def _dashboard_run_digest(
    scored_rows: Sequence[ScoredSnapshotRecord],
    decisions: Sequence[DecisionRecord],
    metadata: Mapping[str, Any],
) -> str:
    payload = {
        "scores": [
            {
                "ticker": row.ticker,
                "asset_class": row.asset_class,
                "state": row.state,
                "s_score": row.s_score,
                "f_score": row.f_score,
                "pillar_scores": row.pillar_scores,
                "payload": row.payload,
            }
            for row in scored_rows
        ],
        "decisions": [
            {
                "decision_type": decision.decision_type,
                "action": decision.action,
                "ticker": decision.ticker,
                "rationale": decision.rationale,
                "payload": decision.payload,
            }
            for decision in decisions
        ],
        "metadata": metadata,
    }
    encoded = json.dumps(payload, default=_json_default, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]


def build_dashboard_run_records(
    scored_df: Any,
    bluf: Mapping[str, Any],
    *,
    started_at_utc: str | None = None,
    git_sha: str | None = None,
    app_version: str | None = None,
    provider: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[RunRecord, list[ScoredSnapshotRecord], list[DecisionRecord]]:
    started = started_at_utc or _utc_now()
    scored_rows = scored_snapshot_records_from_frame(scored_df)
    decisions = decision_records_from_bluf(bluf)
    clean_metadata = _clean_mapping(metadata or {})
    digest = _dashboard_run_digest(scored_rows, decisions, clean_metadata)
    run = RunRecord(
        run_id=f"dashboard-{_compact_run_timestamp(started)}-{digest}",
        started_at_utc=started,
        git_sha=git_sha,
        app_version=app_version,
        provider=provider,
        universe_count=len(scored_rows),
        metadata=clean_metadata,
    )
    return run, scored_rows, decisions


def append_dashboard_run(
    db_path: str | Path,
    scored_df: Any,
    bluf: Mapping[str, Any],
    *,
    started_at_utc: str | None = None,
    git_sha: str | None = None,
    app_version: str | None = None,
    provider: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> JournalAppendResult:
    run: RunRecord | None = None
    try:
        run, scored_rows, decisions = build_dashboard_run_records(
            scored_df,
            bluf,
            started_at_utc=started_at_utc,
            git_sha=git_sha,
            app_version=app_version,
            provider=provider,
            metadata=metadata,
        )
        append_run(db_path, run, scored_rows=scored_rows, decisions=decisions)
    except Exception as exc:
        return JournalAppendResult(
            ok=False,
            run_id=run.run_id if run else None,
            error=f"{type(exc).__name__}: {exc}",
        )
    return JournalAppendResult(ok=True, run_id=run.run_id)


def initialize_journal(db_path: str | Path = DEFAULT_JOURNAL_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at_utc TEXT NOT NULL,
                git_sha TEXT,
                app_version TEXT,
                provider TEXT,
                universe_count INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scored_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                asset_class TEXT,
                state TEXT,
                s_score REAL,
                f_score REAL,
                pillar_scores_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                UNIQUE (run_id, ticker)
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                ticker TEXT,
                action TEXT NOT NULL,
                rationale TEXT,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_runs_started_at
                ON runs(started_at_utc DESC);
            CREATE INDEX IF NOT EXISTS idx_decisions_run_id
                ON decisions(run_id);
            """
        )


def append_run(
    db_path: str | Path,
    run: RunRecord,
    scored_rows: Sequence[ScoredSnapshotRecord] = (),
    decisions: Sequence[DecisionRecord] = (),
) -> None:
    initialize_journal(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id,
                    started_at_utc,
                    git_sha,
                    app_version,
                    provider,
                    universe_count,
                    metadata_json,
                    created_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.started_at_utc,
                    run.git_sha,
                    run.app_version,
                    run.provider,
                    int(run.universe_count),
                    _to_json(run.metadata),
                    _utc_now(),
                ),
            )
            conn.executemany(
                """
                INSERT INTO scored_snapshots (
                    run_id,
                    ticker,
                    asset_class,
                    state,
                    s_score,
                    f_score,
                    pillar_scores_json,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run.run_id,
                        row.ticker.upper(),
                        row.asset_class,
                        row.state,
                        row.s_score,
                        row.f_score,
                        _to_json(row.pillar_scores),
                        _to_json(row.payload),
                    )
                    for row in scored_rows
                ],
            )
            conn.executemany(
                """
                INSERT INTO decisions (
                    run_id,
                    decision_type,
                    ticker,
                    action,
                    rationale,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run.run_id,
                        decision.decision_type,
                        decision.ticker.upper() if decision.ticker else None,
                        decision.action,
                        decision.rationale,
                        _to_json(decision.payload),
                    )
                    for decision in decisions
                ],
            )


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), row))


def list_runs(db_path: str | Path = DEFAULT_JOURNAL_PATH, limit: int = 50) -> list[dict[str, Any]]:
    initialize_journal(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                run_id,
                started_at_utc,
                git_sha,
                app_version,
                provider,
                universe_count,
                metadata_json,
                created_at_utc
            FROM runs
            ORDER BY started_at_utc DESC, created_at_utc DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    out = []
    for row in rows:
        data = _row_dict(row)
        data["metadata"] = _from_json(data.pop("metadata_json"))
        out.append(data)
    return out


def load_run_details(db_path: str | Path, run_id: str) -> dict[str, Any]:
    initialize_journal(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute(
            """
            SELECT
                run_id,
                started_at_utc,
                git_sha,
                app_version,
                provider,
                universe_count,
                metadata_json,
                created_at_utc
            FROM runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        scores = conn.execute(
            """
            SELECT
                ticker,
                asset_class,
                state,
                s_score,
                f_score,
                pillar_scores_json,
                payload_json
            FROM scored_snapshots
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        decisions = conn.execute(
            """
            SELECT
                decision_type,
                ticker,
                action,
                rationale,
                payload_json
            FROM decisions
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()

    run_data = _row_dict(run)
    run_data["metadata"] = _from_json(run_data.pop("metadata_json"))

    score_rows = []
    for row in scores:
        data = _row_dict(row)
        data["pillar_scores"] = _from_json(data.pop("pillar_scores_json"))
        data["payload"] = _from_json(data.pop("payload_json"))
        score_rows.append(data)

    decision_rows = []
    for row in decisions:
        data = _row_dict(row)
        data["payload"] = _from_json(data.pop("payload_json"))
        decision_rows.append(data)

    return {"run": run_data, "scores": score_rows, "decisions": decision_rows}
