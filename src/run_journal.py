"""Append-only run journal for methodology decisions and later debriefs."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
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
