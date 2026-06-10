from __future__ import annotations

import importlib
import json

import numpy as np
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
        "return_5d": 0.01,
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


def test_decide_state_handles_numpy_boolean_gate_values_without_truthy_leakage():
    row = _row(
        stage=np.int64(4),
        above_30wma=np.bool_(False),
        ma_slope_pos=np.bool_(False),
        mansfield_rs=np.float64(-7.0),
        cmf21=np.float64(-0.12),
    )

    assert scoring.decide_state(row) == "BEARISH_STAGE_4"


def test_decide_state_matches_boolean_like_obv_warning_without_identity_checks():
    row = _row(obv_divergence=np.bool_(True))

    assert scoring.decide_state(row) == "WARNING"


def test_decide_state_treats_nullable_gate_values_as_unknown_not_true():
    row = _row(
        above_30wma=pd.NA,
        ma_slope_pos=pd.NA,
        mansfield_rs=pd.NA,
        cmf21=pd.NA,
        obv_divergence=pd.NA,
    )

    assert scoring.decide_state(row) == "HOLD"


def test_decide_state_returns_warning_for_weakening_quadrant():
    row = _row(rrg_quadrant="Weakening", cmf21=0.02)

    assert scoring.decide_state(row) == "WARNING"


def test_decide_state_returns_strict_stage_two_bullish():
    assert scoring.decide_state(_row()) == "STAGE_2_BULLISH"


def test_decide_state_blocks_clean_bullish_after_short_term_selloff():
    row = _row(return_5d=-0.0467)

    assert scoring.decide_state(row) == "WARNING"


def test_decide_state_ignores_stubbed_provider_flow_for_exit_gates():
    row = _row(
        etf_flow_5d_pct=-5.0,
        etf_flow_5d_pct_live=False,
        block_up_ratio=0.1,
        block_up_ratio_live=False,
    )

    assert scoring.decide_state(row) == "STAGE_2_BULLISH"


def test_decide_state_uses_live_provider_flow_when_available():
    row = _row(
        etf_flow_5d_pct=-5.0,
        etf_flow_5d_pct_live=True,
        block_up_ratio=0.1,
        block_up_ratio_live=True,
    )

    assert scoring.decide_state(row) == "EXIT"


def test_decide_state_does_not_require_missing_provider_flow_for_stage_two():
    row = _row(etf_flow_5d_pct=0.0, etf_flow_5d_pct_live=False)

    assert scoring.decide_state(row) == "STAGE_2_BULLISH"


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
    journal_rows = [
        json.loads(line)
        for line in (tmp_path / "state_transitions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert journal_rows[-1]["ticker"] == "XLK"
    assert journal_rows[-1]["to"] == "WARNING"


def test_state_file_can_be_configured_from_environment(tmp_path, monkeypatch):
    state_file = tmp_path / "container-state.json"

    monkeypatch.setenv("STATE_FILE", str(state_file))
    reloaded = importlib.reload(scoring)
    try:
        assert reloaded.STATE_FILE == state_file
    finally:
        monkeypatch.delenv("STATE_FILE", raising=False)
        importlib.reload(scoring)


def test_transition_journal_can_be_configured_from_environment(tmp_path, monkeypatch):
    state_file = tmp_path / "container-state.json"
    journal_file = tmp_path / "journal" / "transitions.jsonl"

    monkeypatch.setenv("STATE_FILE", str(state_file))
    monkeypatch.setenv("STATE_TRANSITION_JOURNAL", str(journal_file))
    reloaded = importlib.reload(scoring)
    try:
        assert reloaded.STATE_FILE == state_file
        assert reloaded.STATE_TRANSITION_JOURNAL == journal_file
        assert reloaded._transition_journal_path() == journal_file
    finally:
        monkeypatch.delenv("STATE_FILE", raising=False)
        monkeypatch.delenv("STATE_TRANSITION_JOURNAL", raising=False)
        importlib.reload(scoring)


def test_default_state_file_migrates_legacy_root_state(tmp_path, monkeypatch):
    legacy_file = tmp_path / "state.json"
    state_file = tmp_path / "data" / "state.json"
    legacy_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00+00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [
                    {"ticker": "XLK", "from": "EXIT", "to": "HOLD", "date": "2026-05-18"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "LEGACY_STATE_FILE", legacy_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    monkeypatch.setattr(scoring, "_STATE_FILE_EXPLICIT", False)

    prior = scoring._load_state()

    assert prior["XLK"]["state"] == "HOLD"
    assert state_file.exists()
    assert scoring.recent_transitions(n=1)[0]["ticker"] == "XLK"


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


def test_recent_transitions_survives_snapshot_transition_loss(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    monkeypatch.setattr(scoring, "_STATE_FILE_EXPLICIT", True)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [],
            }
        ),
        encoding="utf-8",
    )

    scoring.apply_state_machine(pd.DataFrame([_row(rrg_quadrant="Weakening", cmf21=0.02)], index=["XLK"]))
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    payload["transitions"] = []
    state_file.write_text(json.dumps(payload), encoding="utf-8")

    rows = scoring.recent_transitions(n=5)

    assert rows[0]["ticker"] == "XLK"
    assert rows[0]["from"] == "HOLD"
    assert rows[0]["to"] == "WARNING"


def test_save_state_creates_empty_transition_journal_on_baseline_run(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    monkeypatch.setattr(scoring, "_STATE_FILE_EXPLICIT", True)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)

    scoring.apply_state_machine(pd.DataFrame([_row()], index=["XLK"]))

    journal_file = tmp_path / "state_transitions.jsonl"
    assert journal_file.exists()
    assert journal_file.read_text(encoding="utf-8") == ""


def test_save_state_creates_latest_and_daily_backups(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00+00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [],
            }
        ),
        encoding="utf-8",
    )

    scoring.apply_state_machine(pd.DataFrame([_row(rrg_quadrant="Weakening", cmf21=0.02)], index=["XLK"]))

    backup_dir = tmp_path / "state_backups"
    assert (backup_dir / "state-latest.json").exists()
    assert list(backup_dir.glob("state-*.json"))


def test_state_storage_health_reports_paths_and_counts(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)
    now = scoring.datetime.fromisoformat("2026-05-18T02:00:00+00:00")
    monkeypatch.setattr(scoring, "_now_utc", lambda: now)
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00+00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [
                    {"ticker": "XLK", "from": "EXIT", "to": "HOLD", "date": "2026-05-18"}
                ],
            }
        ),
        encoding="utf-8",
    )

    health = scoring.state_storage_health()

    assert health["state_file"] == str(state_file)
    assert health["state_file_exists"] is True
    assert health["by_ticker_count"] == 1
    assert health["journal_transition_count"] == 1
    assert health["latest_transition_date"] == "2026-05-18"
    assert health["state_updated_age_seconds"] == 7200
    assert health["freshness_state"] == "fresh"


def test_state_storage_health_initializes_empty_journal_for_existing_snapshot(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00+00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [],
            }
        ),
        encoding="utf-8",
    )

    health = scoring.state_storage_health()

    assert health["transition_journal_exists"] is True
    assert (tmp_path / "state_transitions.jsonl").exists()
    assert health["journal_transition_count"] == 0


def test_reconcile_states_from_storage_overrides_stale_rendered_state(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    now = scoring.datetime.fromisoformat("2026-06-10T18:00:00+00:00")
    monkeypatch.setattr(scoring, "_now_utc", lambda: now)
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-06-10T17:51:04+00:00",
                "by_ticker": {"EWJ": {"state": "EXIT", "date": "2026-06-10"}},
                "transitions": [],
            }
        ),
        encoding="utf-8",
    )
    scored = pd.DataFrame(
        {
            "state": ["STAGE_2_BULLISH"],
            "return_5d": [-0.0469],
            "S_score": [0.8],
        },
        index=["EWJ"],
    )

    reconciled = scoring.reconcile_states_from_storage(scored)

    assert reconciled.loc["EWJ", "state"] == "EXIT"
    assert reconciled.loc["EWJ", "rendered_state_before_storage_reconcile"] == "STAGE_2_BULLISH"
    assert bool(reconciled.loc["EWJ", "state_storage_reconciled"]) is True
    assert reconciled.loc["EWJ", "state_storage_date"] == "2026-06-10"


def test_reconcile_states_from_storage_ignores_stale_state_file(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    now = scoring.datetime.fromisoformat("2026-06-10T18:00:00+00:00")
    monkeypatch.setattr(scoring, "_now_utc", lambda: now)
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-06-01T17:51:04+00:00",
                "by_ticker": {"EWJ": {"state": "EXIT", "date": "2026-06-01"}},
            }
        ),
        encoding="utf-8",
    )
    scored = pd.DataFrame({"state": ["STAGE_2_BULLISH"]}, index=["EWJ"])

    reconciled = scoring.reconcile_states_from_storage(scored)

    assert reconciled.loc["EWJ", "state"] == "STAGE_2_BULLISH"
    assert "state_storage_reconciled" not in reconciled.columns
