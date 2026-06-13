from __future__ import annotations

from datetime import datetime, timezone

from src import api_status
from src.provider_snapshots import upsert_provider_snapshot
from src.run_journal import RunRecord, append_run


def test_persisted_status_payload_reads_state_journal_and_provider_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        api_status,
        "state_storage_health",
        lambda: {
            "state_file": str(tmp_path / "state.json"),
            "state_file_exists": True,
            "state_updated": "2026-06-08T18:24:09Z",
            "state_updated_age_seconds": 120,
            "freshness_state": "fresh",
            "by_ticker_count": 83,
            "transition_journal": str(tmp_path / "state_transitions.jsonl"),
            "transition_journal_exists": True,
            "journal_transition_count": 62,
            "latest_transition_date": "2026-06-08",
            "backup_dir": str(tmp_path / "state_backups"),
        },
    )
    journal_path = tmp_path / "runs.sqlite"
    snapshot_path = tmp_path / "provider_snapshots.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-1",
            started_at_utc="2026-06-08T18:25:00Z",
            git_sha="abc123",
            app_version="v-test",
            provider="massive",
            universe_count=83,
        ),
    )
    upsert_provider_snapshot(
        snapshot_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-06-08",
        captured_at_utc="2026-06-08T22:00:00Z",
        payload={"trades": [{"price": 1.0}]},
    )
    payload = api_status.build_persisted_status_payload(
        app_version="v2.4.11",
        git_sha="abc123",
        journal_path=journal_path,
        snapshot_db_path=snapshot_path,
        expected_tickers=("XLK",),
        generated_at=datetime(2026, 6, 8, 18, 30, tzinfo=timezone.utc),
    )

    assert payload["api_version"] == "v1"
    assert payload["generated_at"] == "2026-06-08T18:30:00+00:00"
    assert payload["app"]["active_frontend"] == "api"
    assert payload["health"]["status"] == "healthy"
    lanes = {lane["lane_id"]: lane for lane in payload["lanes"]}
    assert lanes["state_persistence"]["freshness"] == "83 states; 62 journaled transitions; fresh (0h old)"
    assert lanes["run_journal"]["freshness"] == "latest run 2026-06-08T18:25:00Z"
    assert lanes["run_journal"]["coverage"] == "universe 83"
    assert lanes["provider_snapshots"]["freshness"] == "ready; 1/1 tickers covered"
    assert lanes["provider_snapshots"]["latest"] == "2026-06-08"


def test_persisted_status_payload_warns_for_missing_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        api_status,
        "state_storage_health",
        lambda: {
            "state_file": str(tmp_path / "state.json"),
            "state_file_exists": False,
            "freshness_state": "missing",
            "by_ticker_count": 0,
            "transition_journal_exists": False,
            "journal_transition_count": 0,
            "backup_dir": str(tmp_path / "state_backups"),
        },
    )
    payload = api_status.build_persisted_status_payload(
        journal_path=tmp_path / "missing_runs.sqlite",
        snapshot_db_path=tmp_path / "missing_provider_snapshots.sqlite",
        expected_tickers=("XLK", "XLF"),
        generated_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert payload["health"]["status"] == "warning"
    lanes = {lane["lane_id"]: lane for lane in payload["lanes"]}
    assert lanes["state_persistence"]["status"] == "warning"
    assert lanes["run_journal"]["freshness"] == "missing"
    assert lanes["provider_snapshots"]["freshness"] == "missing; 0/2 tickers covered"
