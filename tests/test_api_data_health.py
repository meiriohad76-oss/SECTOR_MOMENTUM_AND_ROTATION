from __future__ import annotations

from datetime import datetime, timezone
import json

from src import api_data_health, api_status
from src.provider_flow_cache import write_provider_flow_cache
from src.provider_snapshots import upsert_provider_snapshot
from src.run_journal import RunRecord, append_run


def test_provider_data_health_payload_combines_persisted_and_provider_lanes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        api_status,
        "state_storage_health",
        lambda: {
            "state_file": str(tmp_path / "state.json"),
            "state_file_exists": True,
            "state_updated": "2026-06-09T10:00:00Z",
            "state_updated_age_seconds": 600,
            "freshness_state": "fresh",
            "by_ticker_count": 2,
            "transition_journal": str(tmp_path / "state_transitions.jsonl"),
            "transition_journal_exists": True,
            "journal_transition_count": 3,
            "latest_transition_date": "2026-06-09",
            "backup_dir": str(tmp_path / "state_backups"),
        },
    )
    monkeypatch.setattr(api_data_health, "_provider_flow_feeds_stubbed", lambda rows: False)
    journal_path = tmp_path / "runs.sqlite"
    snapshot_path = tmp_path / "provider_snapshots.sqlite"
    cache_path = tmp_path / "provider_flow_cache.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-1",
            started_at_utc="2026-06-09T10:05:00Z",
            git_sha="abc123",
            app_version="v-test",
            provider="massive",
            universe_count=2,
        ),
    )
    upsert_provider_snapshot(
        snapshot_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-06-09",
        captured_at_utc="2026-06-09T21:00:00Z",
        payload={"trades": [{"price": 1.0}]},
    )
    write_provider_flow_cache(
        provider="massive",
        lane="massive_block_trades",
        ticker="XLK",
        params={"limit": 25, "api_key": "secret-value"},
        payload=[{"p": 1.0}],
        path=cache_path,
        created_at_utc="2026-06-09T21:05:00Z",
    )

    payload = api_data_health.build_provider_data_health_payload(
        app_version="v2.5",
        git_sha="abc123",
        journal_path=journal_path,
        snapshot_db_path=snapshot_path,
        cache_path=cache_path,
        expected_tickers=("XLK", "XLF"),
        provider_flow_statuses=[
            {
                "id": "ohlcv_derived",
                "label": "OHLCV-derived flow",
                "provider": "Market OHLCV",
                "status": "healthy",
                "mode": "live from market lane",
                "signal": "CMF",
                "detail": "live",
            },
            {
                "id": "massive_block_trades",
                "label": "Massive block trades",
                "provider": "Massive",
                "status": "healthy",
                "mode": "enabled",
                "signal": "block_up_ratio",
                "detail": "configured",
            },
        ],
        generated_at=datetime(2026, 6, 9, 10, 10, tzinfo=timezone.utc),
    )
    lanes = {lane["lane_id"]: lane for lane in payload["lanes"]}
    serialized = json.dumps(payload)

    assert payload["api_version"] == "v1"
    assert payload["app"]["active_frontend"] == "api"
    assert payload["provider_flow"] == {
        "provider_count": 2,
        "enabled_provider_count": 1,
        "stubbed": False,
    }
    assert lanes["state_persistence"]["status"] == "healthy"
    assert lanes["run_journal"]["coverage"] == "universe 2"
    assert lanes["provider_snapshots"]["freshness"] == "incomplete; 1/2 tickers covered"
    assert lanes["provider_flow_readiness"]["providers"][1]["provider"] == "Massive"
    assert lanes["provider_flow_cache"]["freshness"] == "incomplete; 1/6 lane-ticker pairs covered"
    assert "secret-value" not in serialized


def test_provider_data_health_payload_warns_for_missing_cache_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        api_status,
        "state_storage_health",
        lambda: {
            "state_file_exists": False,
            "freshness_state": "missing",
            "by_ticker_count": 0,
            "transition_journal_exists": False,
            "journal_transition_count": 0,
        },
    )
    monkeypatch.setattr(api_data_health, "_provider_flow_feeds_stubbed", lambda rows: True)

    payload = api_data_health.build_provider_data_health_payload(
        journal_path=tmp_path / "missing_runs.sqlite",
        snapshot_db_path=tmp_path / "missing_snapshots.sqlite",
        cache_path=tmp_path / "missing_cache.sqlite",
        expected_tickers=("XLK",),
        provider_flow_statuses=[
            {
                "id": "massive_block_trades",
                "label": "Massive block trades",
                "provider": "Massive",
                "status": "info",
                "mode": "stubbed neutral",
                "signal": "block_up_ratio",
                "detail": "neutral",
            }
        ],
        generated_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )
    lanes = {lane["lane_id"]: lane for lane in payload["lanes"]}

    assert payload["health"]["status"] == "warning"
    assert payload["provider_flow"]["stubbed"] is True
    assert lanes["provider_flow_cache"]["freshness"] == "missing; 0/3 lane-ticker pairs covered"
    assert lanes["provider_snapshots"]["freshness"] == "missing; 0/1 tickers covered"
