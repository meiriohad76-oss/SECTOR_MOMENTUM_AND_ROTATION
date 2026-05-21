from __future__ import annotations

import json

import pandas as pd
import pytest

from src import scoring


def _row(**overrides) -> pd.Series:
    base = {
        "stage": 2,
        "above_30wma": True,
        "ma_slope_pos": True,
        "mansfield_rs": 5.0,
        "antonacci": 1,
        "rrg_quadrant": "Leading",
        "breadth_50d": 0.70,
        "cmf21": 0.08,
        "rvol": 1.0,
        "etf_flow_5d_pct": 0.0,
        "block_up_ratio": 1.0,
        "obv_divergence": False,
        "dist_days_25": 0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_decide_state_prioritizes_bearish_stage_four_before_exit():
    row = _row(
        above_30wma=False,
        ma_slope_pos=False,
        mansfield_rs=-2.0,
        cmf21=-0.20,
    )

    assert scoring.decide_state(row) == "BEARISH_STAGE_4"


def test_decide_state_returns_warning_for_weakening_quadrant():
    row = _row(rrg_quadrant="Weakening", cmf21=0.02)

    assert scoring.decide_state(row) == "WARNING"


def test_decide_state_returns_strict_stage_two_bullish():
    assert scoring.decide_state(_row()) == "STAGE_2_BULLISH"


def test_compute_composite_applies_flow_veto_and_ranks_within_class():
    indicators_df = pd.DataFrame(
        {
            "mom_12_1": [0.30, 0.05],
            "faber": [1, 1],
            "stage": [2, 2],
            "mansfield_rs": [12.0, -2.0],
            "antonacci": [1, 1],
            "rs_ratio": [110.0, 95.0],
            "rs_momentum": [108.0, 96.0],
        },
        index=["XLK", "XLF"],
    )
    flow_df = pd.DataFrame({"cmf21": [0.2, -0.2]}, index=["XLK", "XLF"])
    flow_z = pd.Series([2.0, -2.0], index=["XLK", "XLF"], name="F")

    out = scoring.compute_composite(indicators_df, flow_df, flow_z, phase="MID")

    assert out.loc["XLF", "veto"] == True
    assert out.loc["XLF", "S_score_after_veto"] == pytest.approx(-9.99)
    assert out.loc["XLK", "rank_in_class"] < out.loc["XLF", "rank_in_class"]


def test_apply_state_machine_persists_transitions_to_patched_state_file(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [],
            }
        )
    )
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)
    df = pd.DataFrame([_row(rrg_quadrant="Weakening", cmf21=0.02)], index=["XLK"])

    out = scoring.apply_state_machine(df)
    saved = json.loads(state_file.read_text())

    assert out.loc["XLK", "state"] == "WARNING"
    assert out.loc["XLK", "prior_state"] == "HOLD"
    assert saved["by_ticker"]["XLK"]["state"] == "WARNING"
    assert saved["transitions"][-1]["ticker"] == "XLK"
    assert saved["transitions"][-1]["from"] == "HOLD"
    assert saved["transitions"][-1]["to"] == "WARNING"


def test_apply_state_machine_dates_transitions_by_us_eastern_day(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-20T00:00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-20"}},
                "transitions": [],
            }
        )
    )
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)
    monkeypatch.setattr(scoring, "_now_utc", lambda: scoring.datetime(2026, 5, 21, 1, 0, tzinfo=scoring.timezone.utc))
    df = pd.DataFrame([_row(rrg_quadrant="Weakening", cmf21=0.02)], index=["XLK"])

    scoring.apply_state_machine(df)
    saved = json.loads(state_file.read_text())

    assert saved["transitions"][-1]["date"] == "2026-05-20"
    assert saved["by_ticker"]["XLK"]["date"] == "2026-05-20"


def test_apply_state_machine_notifies_after_persisting_transitions(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [],
            }
        )
    )
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    sent = []

    def fake_send_transition_alerts(transitions):
        saved = json.loads(state_file.read_text())
        assert saved["transitions"][-1]["ticker"] == "XLK"
        assert saved["transitions"][-1]["to"] == "WARNING"
        sent.extend(transitions)

    monkeypatch.setattr(scoring, "_send_transition_alerts", fake_send_transition_alerts)
    df = pd.DataFrame([_row(rrg_quadrant="Weakening", cmf21=0.02)], index=["XLK"])

    scoring.apply_state_machine(df)

    assert sent
    assert sent[-1]["ticker"] == "XLK"
    assert sent[-1]["from"] == "HOLD"
    assert sent[-1]["to"] == "WARNING"
