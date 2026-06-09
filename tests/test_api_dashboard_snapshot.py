from __future__ import annotations

from src.api_dashboard_snapshot import build_latest_dashboard_snapshot_payload
from src.run_journal import DecisionRecord, RunRecord, ScoredSnapshotRecord, append_run


def test_latest_dashboard_snapshot_returns_empty_payload_without_runs(tmp_path):
    payload = build_latest_dashboard_snapshot_payload(
        journal_path=tmp_path / "missing.sqlite",
        generated_at="2026-06-09T12:00:00+00:00",
    )

    assert payload["status"] == "empty"
    assert payload["rows"] == []
    assert payload["focus"] is None
    assert payload["summary"]["universe_count"] == 0


def test_latest_dashboard_snapshot_reads_scores_decisions_and_focus(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-1",
            started_at_utc="2026-06-09T10:00:00Z",
            provider="massive",
            universe_count=3,
            metadata={"phase": "MID"},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.2,
                f_score=0.4,
                pillar_scores={"mom_12_1": 0.22, "rs_ratio": 110, "rs_momentum": 105, "cmf21": 0.12},
                payload={"rrg_quadrant": "Leading"},
            ),
            ScoredSnapshotRecord(
                ticker="XLE",
                asset_class="US Sectors",
                state="WARNING",
                s_score=-0.5,
                f_score=-0.8,
                pillar_scores={"mom_12_1": -0.04, "rs_ratio": 92, "rs_momentum": 88, "cmf21": -0.2},
            ),
            ScoredSnapshotRecord(
                ticker="NVDA",
                asset_class="Mega-Cap Stocks",
                state="HOLD",
                s_score=0.7,
                f_score=0.1,
                pillar_scores={"mom_12_1": 0.18},
            ),
        ],
        decisions=[
            DecisionRecord(decision_type="bluf", ticker="XLK", action="BUY", rationale="top score"),
            DecisionRecord(decision_type="bluf", ticker="XLE", action="WATCH", rationale="flow veto"),
        ],
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        focus_ticker="XLE",
        generated_at="2026-06-09T12:00:00+00:00",
    )
    by_ticker = {row["ticker"]: row for row in payload["rows"]}

    assert payload["status"] == "ready"
    assert payload["run"]["run_id"] == "run-1"
    assert payload["summary"]["state_counts"] == {"HOLD": 1, "STAGE_2_BULLISH": 1, "WARNING": 1}
    assert payload["summary"]["decision_counts"] == {"BUY": 1, "WATCH": 1}
    assert by_ticker["XLK"]["identity"] == "Technology sector"
    assert by_ticker["XLK"]["quadrant"] == "Leading"
    assert by_ticker["XLE"]["quadrant"] == "Lagging"
    assert payload["focus"]["ticker"] == "XLE"
    assert [row["ticker"] for row in payload["screens"]["overview"]["leaders"][:2]] == ["XLK", "NVDA"]
    assert [row["ticker"] for row in payload["screens"]["rotation"]["sectors"]] == ["XLK", "XLE"]
