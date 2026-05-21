from __future__ import annotations

import sqlite3

import pytest

from src.run_journal import (
    DEFAULT_JOURNAL_PATH,
    DecisionRecord,
    RunRecord,
    ScoredSnapshotRecord,
    append_run,
    list_runs,
    load_run_details,
)


def test_default_journal_path_is_local_data_file():
    assert DEFAULT_JOURNAL_PATH.as_posix().endswith("data/run_journal/runs.sqlite")


def test_append_run_persists_scores_and_decisions(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    run = RunRecord(
        run_id="run-20260521-001",
        started_at_utc="2026-05-21T05:00:00Z",
        git_sha="abc1234",
        app_version="v2.4.2",
        provider="massive",
        universe_count=2,
        metadata={"phase": "MID", "missing_tickers": []},
    )
    scored_rows = [
        ScoredSnapshotRecord(
            ticker="XLK",
            asset_class="US Sectors",
            state="STAGE_2_BULLISH",
            s_score=0.91,
            f_score=0.33,
            pillar_scores={"momentum": 0.95, "flow": 0.15},
            payload={"rank": 1},
        ),
        ScoredSnapshotRecord(
            ticker="XLE",
            asset_class="US Sectors",
            state="WARNING",
            s_score=-0.15,
            f_score=-0.21,
            pillar_scores={"momentum": -0.40},
        ),
    ]
    decisions = [
        DecisionRecord(
            decision_type="recommendation",
            ticker="XLK",
            action="BUY",
            rationale="Top methodology score and bullish state.",
            payload={"bucket": "buy"},
        ),
        DecisionRecord(
            decision_type="risk",
            ticker="XLE",
            action="WATCH",
            rationale="Warning state requires tighter stop.",
        ),
    ]

    append_run(db_path, run, scored_rows=scored_rows, decisions=decisions)

    details = load_run_details(db_path, "run-20260521-001")
    assert details["run"]["run_id"] == "run-20260521-001"
    assert details["run"]["metadata"] == {"phase": "MID", "missing_tickers": []}
    assert details["scores"][0]["ticker"] == "XLK"
    assert details["scores"][0]["pillar_scores"]["momentum"] == pytest.approx(0.95)
    assert details["scores"][0]["payload"] == {"rank": 1}
    assert details["scores"][1]["state"] == "WARNING"
    assert details["decisions"][0]["action"] == "BUY"
    assert details["decisions"][0]["payload"] == {"bucket": "buy"}
    assert details["decisions"][1]["rationale"] == "Warning state requires tighter stop."


def test_list_runs_returns_newest_first(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    append_run(
        db_path,
        RunRecord(run_id="older", started_at_utc="2026-05-20T05:00:00Z"),
    )
    append_run(
        db_path,
        RunRecord(run_id="newer", started_at_utc="2026-05-21T05:00:00Z"),
    )

    runs = list_runs(db_path)

    assert [row["run_id"] for row in runs] == ["newer", "older"]


def test_append_run_rejects_duplicate_run_id(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    run = RunRecord(run_id="duplicate", started_at_utc="2026-05-21T05:00:00Z")

    append_run(db_path, run)

    with pytest.raises(sqlite3.IntegrityError):
        append_run(db_path, run)
