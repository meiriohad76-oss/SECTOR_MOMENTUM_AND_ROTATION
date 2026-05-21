from __future__ import annotations

import pandas as pd
import pytest

from src.run_debrief import (
    compute_forward_outcomes,
    debrief_journal,
    summarize_debriefs,
    threshold_review_candidates,
)
from src.run_journal import DecisionRecord, RunRecord, ScoredSnapshotRecord, append_run


def _ohlcv_from_closes(start: str, closes: list[float]) -> pd.DataFrame:
    index = pd.bdate_range(start=start, periods=len(closes))
    values = pd.Series(closes, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": values.shift(1).fillna(values.iloc[0]),
            "high": values * 1.01,
            "low": values * 0.99,
            "close": values,
            "adj_close": values,
            "volume": 1_000_000,
        },
        index=index,
    )


def test_compute_forward_outcomes_marks_buy_and_exit_hits():
    windows = {"1w": 5}
    buy_frame = _ohlcv_from_closes("2026-01-02", [100, 101, 102, 103, 104, 110])
    exit_frame = _ohlcv_from_closes("2026-01-02", [100, 99, 98, 97, 96, 92])

    buy = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLK",
        "BUY",
        {"XLK": buy_frame},
        windows=windows,
    )["1w"]
    exit_ = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLE",
        "EXIT",
        {"XLE": exit_frame},
        windows=windows,
    )["1w"]

    assert buy.status == "available"
    assert buy.start_date == "2026-01-02"
    assert buy.end_date == "2026-01-09"
    assert buy.forward_return == pytest.approx(0.10)
    assert buy.max_drawdown == pytest.approx(0.0)
    assert buy.hit is True
    assert exit_.forward_return == pytest.approx(-0.08)
    assert exit_.max_drawdown == pytest.approx(-0.08)
    assert exit_.hit is True


def test_compute_forward_outcomes_returns_unavailable_for_missing_future_data():
    outcomes = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLK",
        "BUY",
        {"XLK": _ohlcv_from_closes("2026-01-02", [100, 101, 102])},
        windows={"1w": 5},
    )

    outcome = outcomes["1w"]
    assert outcome.status == "insufficient_history"
    assert outcome.start_date == "2026-01-02"
    assert outcome.end_date is None
    assert outcome.forward_return is None
    assert outcome.hit is None


def test_compute_forward_outcomes_returns_unavailable_for_missing_or_bad_prices():
    missing = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLK",
        "BUY",
        {},
        windows={"1w": 5},
    )["1w"]
    malformed = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLK",
        "BUY",
        {"XLK": None},
        windows={"1w": 5},
    )["1w"]
    zero_baseline = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLK",
        "BUY",
        {"XLK": _ohlcv_from_closes("2026-01-02", [0, 1, 2, 3, 4, 5])},
        windows={"1w": 5},
    )["1w"]

    assert missing.status == "missing_ticker"
    assert malformed.status == "missing_prices"
    assert zero_baseline.status == "invalid_baseline"
    assert zero_baseline.forward_return is None
    assert zero_baseline.hit is None


def test_compute_forward_outcomes_marks_unsupported_action_without_hit():
    outcome = compute_forward_outcomes(
        "2026-01-02T12:00:00Z",
        "XLK",
        "REVIEW",
        {"XLK": _ohlcv_from_closes("2026-01-02", [100, 101, 102, 103, 104, 110])},
        windows={"1w": 5},
    )["1w"]

    assert outcome.status == "unsupported_action"
    assert outcome.forward_return == pytest.approx(0.10)
    assert outcome.hit is None


def test_debrief_journal_joins_decisions_scores_and_forward_returns(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    append_run(
        db_path,
        RunRecord(
            run_id="run-001",
            started_at_utc="2026-01-02T12:00:00Z",
            app_version="v2.4.2",
            provider="massive",
            universe_count=2,
            metadata={"phase": "MID"},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=0.91,
                f_score=0.33,
            ),
            ScoredSnapshotRecord(
                ticker="XLE",
                asset_class="US Sectors",
                state="EXIT",
                s_score=-0.40,
                f_score=-0.50,
            ),
        ],
        decisions=[
            DecisionRecord(
                decision_type="bluf",
                ticker="XLK",
                action="BUY",
                rationale="S +0.91",
                payload={"label": "BUY CANDIDATES"},
            ),
            DecisionRecord(
                decision_type="bluf",
                ticker="XLE",
                action="EXIT",
                rationale="below 30wMA",
                payload={"label": "EXIT NOW"},
            ),
        ],
    )

    records = debrief_journal(
        db_path,
        {
            "XLK": _ohlcv_from_closes("2026-01-02", [100, 101, 102, 103, 104, 110]),
            "XLE": _ohlcv_from_closes("2026-01-02", [100, 99, 98, 97, 96, 92]),
        },
        windows={"1w": 5},
    )

    assert [record.ticker for record in records] == ["XLK", "XLE"]
    assert records[0].run_id == "run-001"
    assert records[0].action == "BUY"
    assert records[0].state == "STAGE_2_BULLISH"
    assert records[0].s_score == pytest.approx(0.91)
    assert records[0].f_score == pytest.approx(0.33)
    assert records[0].outcomes["1w"].forward_return == pytest.approx(0.10)
    assert records[0].outcomes["1w"].hit is True
    assert records[1].action == "EXIT"
    assert records[1].outcomes["1w"].forward_return == pytest.approx(-0.08)
    assert records[1].outcomes["1w"].hit is True


def test_summarize_debriefs_and_threshold_review_candidates(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    append_run(
        db_path,
        RunRecord(run_id="run-001", started_at_utc="2026-01-02T12:00:00Z", universe_count=3),
        scored_rows=[
            ScoredSnapshotRecord(ticker="XLK", state="STAGE_2_BULLISH", s_score=0.9, f_score=0.4),
            ScoredSnapshotRecord(ticker="XLY", state="STAGE_2_BULLISH", s_score=0.8, f_score=0.2),
            ScoredSnapshotRecord(ticker="XLE", state="EXIT", s_score=-0.4, f_score=-0.5),
        ],
        decisions=[
            DecisionRecord(decision_type="bluf", ticker="XLK", action="BUY", rationale="winner"),
            DecisionRecord(decision_type="bluf", ticker="XLY", action="BUY", rationale="failed buy"),
            DecisionRecord(decision_type="bluf", ticker="XLE", action="EXIT", rationale="risk off"),
        ],
    )
    records = debrief_journal(
        db_path,
        {
            "XLK": _ohlcv_from_closes("2026-01-02", [100, 101, 102, 103, 104, 110]),
            "XLY": _ohlcv_from_closes("2026-01-02", [100, 99, 98, 97, 96, 94]),
            "XLE": _ohlcv_from_closes("2026-01-02", [100, 99, 98, 97, 96, 92]),
        },
        windows={"1w": 5},
    )

    summary = summarize_debriefs(records)
    candidates = threshold_review_candidates(records, horizon="1w", min_abs_return=0.02)

    buy_summary = [row for row in summary if row["action"] == "BUY" and row["horizon"] == "1w"][0]
    exit_summary = [row for row in summary if row["action"] == "EXIT" and row["horizon"] == "1w"][0]
    assert buy_summary["decision_count"] == 2
    assert buy_summary["available_count"] == 2
    assert buy_summary["hit_rate"] == pytest.approx(0.5)
    assert buy_summary["average_forward_return"] == pytest.approx(0.02)
    assert exit_summary["hit_rate"] == pytest.approx(1.0)
    assert candidates == [
        {
            "run_id": "run-001",
            "ticker": "XLY",
            "action": "BUY",
            "horizon": "1w",
            "forward_return": pytest.approx(-0.06),
            "state": "STAGE_2_BULLISH",
            "s_score": pytest.approx(0.8),
            "f_score": pytest.approx(0.2),
            "rationale": "failed buy",
        }
    ]
