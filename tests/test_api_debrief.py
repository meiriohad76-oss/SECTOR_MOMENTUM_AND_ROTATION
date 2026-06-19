from __future__ import annotations

import pytest

from src.api_debrief import build_debrief_payload
from src.run_journal import DecisionRecord, RunRecord, ScoredSnapshotRecord, append_run


def test_build_debrief_payload_returns_empty_when_journal_missing(tmp_path):
    payload = build_debrief_payload(
        journal_path=tmp_path / "missing.sqlite",
        limit=20,
    )
    assert payload["runs"] == []
    assert payload["decisions"] == []
    assert "api_version" in payload
    assert "generated_at" in payload


def test_build_debrief_payload_returns_runs_from_journal(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-debrief-1",
            started_at_utc="2026-06-01T10:00:00Z",
            provider="massive",
            universe_count=3,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.2,
                f_score=0.4,
                pillar_scores={"cmf21": 0.12},
            ),
        ],
        decisions=[
            DecisionRecord(
                decision_type="bluf",
                action="BUY",
                ticker="XLK",
                rationale="Leading RRG quadrant",
            ),
        ],
    )

    payload = build_debrief_payload(journal_path=journal_path, limit=20)

    assert len(payload["runs"]) == 1
    run = payload["runs"][0]
    assert run["run_id"] == "run-debrief-1"
    assert run["provider"] == "massive"
    assert run["universe_count"] == 3


def test_build_debrief_payload_returns_decisions_with_scores(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-debrief-2",
            started_at_utc="2026-06-02T10:00:00Z",
            provider="massive",
            universe_count=2,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLE",
                asset_class="US Sectors",
                state="WARNING",
                s_score=-0.5,
                f_score=-0.3,
                pillar_scores={},
            ),
        ],
        decisions=[
            DecisionRecord(
                decision_type="bluf",
                action="EXIT",
                ticker="XLE",
                rationale="Weakening RS",
            ),
        ],
    )

    payload = build_debrief_payload(journal_path=journal_path, limit=20)

    assert len(payload["decisions"]) >= 1
    decision = next(d for d in payload["decisions"] if d["ticker"] == "XLE")
    assert decision["action"] == "EXIT"
    assert decision["state"] == "WARNING"
    assert decision["s_score"] == pytest.approx(-0.5)


def test_build_debrief_payload_respects_limit(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    for i in range(5):
        append_run(
            journal_path,
            RunRecord(
                run_id=f"run-limit-{i}",
                started_at_utc=f"2026-06-{i+1:02d}T10:00:00Z",
                provider="massive",
                universe_count=1,
                metadata={},
            ),
            scored_rows=[],
            decisions=[],
        )

    payload = build_debrief_payload(journal_path=journal_path, limit=3)

    assert len(payload["runs"]) == 3
