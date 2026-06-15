from __future__ import annotations

import pytest

from src.api_dashboard_snapshot import build_latest_dashboard_snapshot_payload
from src.portfolio import HoldingInput
from src.run_journal import DecisionRecord, RunRecord, ScoredSnapshotRecord, append_run
from src.saved_inputs import save_portfolio


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
        saved_inputs_path=tmp_path / "missing-saved-inputs.json",
        transition_journal_path=tmp_path / "state_transitions.jsonl",
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
    assert payload["screens"]["overview"]["positions"] == []
    assert payload["screens"]["overview"]["transitions"] == []


def test_latest_dashboard_snapshot_reads_transition_journal_for_overview(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    transition_journal = tmp_path / "state_transitions.jsonl"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-1",
            started_at_utc="2026-06-09T10:00:00Z",
            provider="massive",
            universe_count=1,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.2,
                f_score=0.4,
                pillar_scores={"mom_12_1": 0.22},
                payload={},
            )
        ],
        decisions=[],
    )
    transition_journal.write_text(
        "\n".join(
            [
                '{"ticker":"XLK","from":"WARNING","to":"STAGE_2_BULLISH","date":"2026-06-08"}',
                '{"ticker":"XLE","from":"HOLD","to":"WARNING","date":"2026-06-09"}',
                "not-json",
            ]
        ),
        encoding="utf-8",
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        saved_inputs_path=tmp_path / "missing-saved-inputs.json",
        transition_journal_path=transition_journal,
        generated_at="2026-06-09T12:00:00+00:00",
    )

    transitions = payload["screens"]["overview"]["transitions"]
    assert [row["ticker"] for row in transitions] == ["XLE", "XLK"]
    assert transitions[0] == {
        "ticker": "XLE",
        "identity": "Energy sector",
        "from": "HOLD",
        "to": "WARNING",
        "date": "2026-06-09",
    }


def test_latest_dashboard_snapshot_reads_saved_portfolio_positions(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    saved_inputs_path = tmp_path / "saved_inputs.json"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-1",
            started_at_utc="2026-06-09T10:00:00Z",
            provider="massive",
            universe_count=1,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.2,
                f_score=0.4,
                pillar_scores={"mom_12_1": 0.22},
                payload={},
            )
        ],
        decisions=[],
    )
    save_portfolio(
        "core",
        [
            HoldingInput(ticker="XLK", shares=10, cost_basis=100, market_value=1200),
            HoldingInput(ticker="XLE", shares=5, cost_basis=80),
        ],
        path=saved_inputs_path,
        now="2026-06-09T11:00:00Z",
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        saved_inputs_path=saved_inputs_path,
        generated_at="2026-06-09T12:00:00+00:00",
    )
    positions = payload["screens"]["overview"]["positions"]

    assert [row["ticker"] for row in positions] == ["XLK", "XLE"]
    assert positions[0]["source_name"] == "core"
    assert positions[0]["identity"] == "Technology sector"
    assert positions[0]["cost"] == 1000.0
    assert positions[0]["unrealized_pct"] == 0.2
    assert positions[1]["unrealized_pct"] is None


def test_row_payload_includes_adv_20d_from_payload_dict(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-adv",
            started_at_utc="2026-06-15T10:00:00Z",
            provider="massive",
            universe_count=1,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.0,
                f_score=0.3,
                pillar_scores={"cmf21": 0.12},
                payload={"adv_20d": 1_200_000_000.0},
            ),
        ],
        decisions=[],
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        saved_inputs_path=tmp_path / "missing.json",
        transition_journal_path=tmp_path / "missing.jsonl",
        generated_at="2026-06-15T12:00:00+00:00",
    )

    row = next(r for r in payload["rows"] if r["ticker"] == "XLK")
    assert row["adv_20d"] == pytest.approx(1_200_000_000.0)


def test_row_payload_adv_20d_is_none_when_absent_from_payload(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-noadv",
            started_at_utc="2026-06-15T10:00:00Z",
            provider="massive",
            universe_count=1,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLE",
                asset_class="US Sectors",
                state="WARNING",
                s_score=-0.5,
                f_score=-0.2,
                pillar_scores={"cmf21": -0.08},
                payload={},   # no adv_20d
            ),
        ],
        decisions=[],
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        saved_inputs_path=tmp_path / "missing.json",
        transition_journal_path=tmp_path / "missing.jsonl",
        generated_at="2026-06-15T12:00:00+00:00",
    )

    row = next(r for r in payload["rows"] if r["ticker"] == "XLE")
    assert row["adv_20d"] is None
