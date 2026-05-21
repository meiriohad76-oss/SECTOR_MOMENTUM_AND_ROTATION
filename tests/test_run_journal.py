from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

import src.run_journal as run_journal
from src.run_journal import (
    DEFAULT_JOURNAL_PATH,
    DecisionRecord,
    append_dashboard_run,
    RunRecord,
    ScoredSnapshotRecord,
    append_run,
    build_dashboard_run_records,
    decision_records_from_bluf,
    list_runs,
    load_run_details,
    scored_snapshot_records_from_frame,
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


def test_scored_snapshot_records_from_frame_extracts_scores_and_payload():
    scored = pd.DataFrame(
        {
            "class": ["US Sectors", "US Sectors"],
            "state": ["STAGE_2_BULLISH", "WARNING"],
            "S_score": [0.91, float("nan")],
            "F_score": [0.33, -0.21],
            "mom_12_1": [0.12, None],
            "cmf21": [0.08, -0.11],
            "rank_in_class": [1, 2],
            "selected": [True, False],
            "veto": [False, True],
            "rrg_quadrant": ["Leading", "Weakening"],
        },
        index=["xlk", "xle"],
    )

    records = scored_snapshot_records_from_frame(scored)

    assert [record.ticker for record in records] == ["XLK", "XLE"]
    assert records[0].asset_class == "US Sectors"
    assert records[0].state == "STAGE_2_BULLISH"
    assert records[0].s_score == pytest.approx(0.91)
    assert records[0].f_score == pytest.approx(0.33)
    assert records[0].pillar_scores["mom_12_1"] == pytest.approx(0.12)
    assert records[0].pillar_scores["cmf21"] == pytest.approx(0.08)
    assert records[0].payload["rank_in_class"] == 1
    assert records[0].payload["selected"] is True
    assert records[0].payload["rrg_quadrant"] == "Leading"
    assert records[1].s_score is None
    assert records[1].payload["veto"] is True


def test_decision_records_from_bluf_expands_action_tickers():
    bluf = {
        "actions": [
            {
                "kind": "exit",
                "label": "EXIT NOW",
                "eta": "ON MONDAY OPEN",
                "state": "EXIT",
                "tickers": [{"t": "xle", "note": "below 30wMA"}],
            },
            {
                "kind": "warn",
                "label": "WATCH CLOSELY",
                "eta": "TIGHTEN STOPS",
                "state": "WARNING",
                "tickers": [{"t": "xlf", "note": "RRG Weakening"}],
            },
            {
                "kind": "buy",
                "label": "BUY CANDIDATES",
                "eta": "ENTER ON DIP",
                "state": "STAGE_2_BULLISH",
                "tickers": [{"t": "xlk", "note": "S +1.40"}],
            },
        ]
    }

    decisions = decision_records_from_bluf(bluf)

    assert [decision.action for decision in decisions] == ["EXIT", "WATCH", "BUY"]
    assert [decision.ticker for decision in decisions] == ["XLE", "XLF", "XLK"]
    assert all(decision.decision_type == "bluf" for decision in decisions)
    assert decisions[0].rationale == "below 30wMA"
    assert decisions[0].payload == {
        "eta": "ON MONDAY OPEN",
        "kind": "exit",
        "label": "EXIT NOW",
        "state": "EXIT",
    }


def test_build_dashboard_run_records_adds_metadata_and_stable_run_id():
    scored = pd.DataFrame(
        {
            "class": ["US Sectors"],
            "state": ["STAGE_2_BULLISH"],
            "S_score": [0.91],
            "F_score": [0.33],
            "selected": [True],
        },
        index=["XLK"],
    )
    bluf = {
        "actions": [
            {
                "kind": "buy",
                "label": "BUY CANDIDATES",
                "eta": "ENTER ON DIP",
                "state": "STAGE_2_BULLISH",
                "tickers": [{"t": "XLK", "note": "S +0.91"}],
            }
        ]
    }

    run, scored_rows, decisions = build_dashboard_run_records(
        scored,
        bluf,
        started_at_utc="2026-05-21T05:00:00Z",
        git_sha="abc1234",
        app_version="v2.4.2",
        provider="massive",
        metadata={"phase": "MID", "risk_on": True},
    )
    run_again, _, _ = build_dashboard_run_records(
        scored,
        bluf,
        started_at_utc="2026-05-21T05:00:00Z",
        git_sha="abc1234",
        app_version="v2.4.2",
        provider="massive",
        metadata={"phase": "MID", "risk_on": True},
    )

    assert run.run_id == run_again.run_id
    assert run.run_id.startswith("dashboard-20260521T050000Z-")
    assert run.git_sha == "abc1234"
    assert run.app_version == "v2.4.2"
    assert run.provider == "massive"
    assert run.universe_count == 1
    assert run.metadata == {"phase": "MID", "risk_on": True}
    assert scored_rows[0].ticker == "XLK"
    assert decisions[0].action == "BUY"


def test_dashboard_run_fingerprint_is_stable_and_input_sensitive():
    scored = pd.DataFrame(
        {
            "class": ["US Sectors"],
            "state": ["STAGE_2_BULLISH"],
            "S_score": [0.91],
            "F_score": [0.33],
            "selected": [True],
        },
        index=["XLK"],
    )
    bluf = {
        "actions": [
            {
                "kind": "buy",
                "label": "BUY CANDIDATES",
                "eta": "ENTER ON DIP",
                "state": "STAGE_2_BULLISH",
                "tickers": [{"t": "XLK", "note": "S +0.91"}],
            }
        ]
    }

    fingerprint = run_journal.dashboard_run_fingerprint(
        scored,
        bluf,
        git_sha="abc1234",
        app_version="v2.4.9",
        provider="massive",
        metadata={"phase": "MID", "risk_on": True},
    )
    same_fingerprint = run_journal.dashboard_run_fingerprint(
        scored,
        bluf,
        git_sha="abc1234",
        app_version="v2.4.9",
        provider="massive",
        metadata={"phase": "MID", "risk_on": True},
    )
    changed_fingerprint = run_journal.dashboard_run_fingerprint(
        scored,
        bluf,
        git_sha="abc1234",
        app_version="v2.4.9",
        provider="massive",
        metadata={"phase": "LATE", "risk_on": False},
    )

    assert fingerprint == same_fingerprint
    assert fingerprint != changed_fingerprint


def test_append_dashboard_run_is_non_blocking_when_journal_write_fails(monkeypatch, tmp_path):
    scored = pd.DataFrame(
        {"class": ["US Sectors"], "state": ["WARNING"], "S_score": [-0.1], "F_score": [-0.2]},
        index=["XLE"],
    )
    bluf = {"actions": []}

    def fail_append(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(run_journal, "append_run", fail_append)

    result = append_dashboard_run(
        tmp_path / "runs.sqlite",
        scored,
        bluf,
        started_at_utc="2026-05-21T05:00:00Z",
    )

    assert result.ok is False
    assert result.run_id.startswith("dashboard-20260521T050000Z-")
    assert result.error == "OperationalError: database is locked"


def test_append_dashboard_run_persists_built_snapshot_and_decisions(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    scored = pd.DataFrame(
        {
            "class": ["US Sectors"],
            "state": ["STAGE_2_BULLISH"],
            "S_score": [0.91],
            "F_score": [0.33],
            "selected": [True],
            "mom_12_1": [0.12],
        },
        index=["XLK"],
    )
    bluf = {
        "actions": [
            {
                "kind": "buy",
                "label": "BUY CANDIDATES",
                "eta": "ENTER ON DIP",
                "state": "STAGE_2_BULLISH",
                "tickers": [{"t": "XLK", "note": "S +0.91"}],
            }
        ]
    }

    result = append_dashboard_run(
        db_path,
        scored,
        bluf,
        started_at_utc="2026-05-21T05:00:00Z",
        git_sha="abc1234",
        app_version="v2.4.2",
        provider="massive",
        metadata={"phase": "MID"},
    )

    assert result.ok is True
    assert result.run_id is not None
    details = load_run_details(db_path, result.run_id)
    assert details["run"]["provider"] == "massive"
    assert details["run"]["metadata"] == {"phase": "MID"}
    assert details["scores"][0]["ticker"] == "XLK"
    assert details["scores"][0]["pillar_scores"]["mom_12_1"] == pytest.approx(0.12)
    assert details["decisions"][0]["action"] == "BUY"
