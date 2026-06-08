from __future__ import annotations

import pytest

from src.api_refresh import create_refresh_job, list_refresh_events
from src.api_refresh_runner import run_refresh_job


def test_refresh_runner_executes_headless_refresh_and_persists_progress(tmp_path, monkeypatch):
    db_path = tmp_path / "refresh_jobs.sqlite"
    journal_path = tmp_path / "dashboard_runs.jsonl"
    job = create_refresh_job(lane_id="all", db_path=db_path)
    calls = {}

    from scripts import refresh_dashboard_state as dashboard_refresh

    def fake_refresh_dashboard_state(**kwargs):
        calls.update(kwargs)
        kwargs["progress_callback"]("market_ohlcv", 25, "Market data", {"period": kwargs["period"]})
        kwargs["progress_callback"]("fred_macro", 70, "FRED data", {"fred_configured": True})
        return {
            "ok": True,
            "provider": "massive",
            "period": kwargs["period"],
            "ticker_count": 83,
            "state_counts": {"STAGE_2_BULLISH": 5},
            "bluf_counts": {"buys": 5, "warnings": 2, "exits": 1},
            "regime": {"phase": "expansion", "fred_used": True},
            "journal": {"ok": True, "run_id": "run-1"},
        }

    monkeypatch.setattr(dashboard_refresh, "refresh_dashboard_state", fake_refresh_dashboard_state)

    result = run_refresh_job(
        job["job_id"],
        db_path=db_path,
        period="5y",
        force_refresh=True,
        provider_flow_mode="cache-only",
        allow_stale_provider_cache=True,
        journal_path=journal_path,
    )

    assert result["status"] == "succeeded"
    assert result["progress_pct"] == 100
    assert result["metadata"]["provider"] == "massive"
    assert result["metadata"]["ticker_count"] == 83
    assert calls["period"] == "5y"
    assert calls["force_refresh"] is True
    assert calls["provider_flow_mode"] == "cache-only"
    assert calls["journal_path"] == journal_path
    assert callable(calls["progress_callback"])
    assert [event["phase"] for event in list_refresh_events(job["job_id"], db_path=db_path)] == [
        "queued",
        "starting",
        "market_ohlcv",
        "fred_macro",
        "complete",
    ]


def test_refresh_runner_marks_non_ok_payload_as_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "refresh_jobs.sqlite"
    job = create_refresh_job(lane_id="fred_macro", db_path=db_path)

    from scripts import refresh_dashboard_state as dashboard_refresh

    monkeypatch.setattr(
        dashboard_refresh,
        "refresh_dashboard_state",
        lambda **kwargs: {"ok": False, "error": "missing_required_market_data", "ticker_count": 0},
    )

    result = run_refresh_job(job["job_id"], db_path=db_path, journal_path=tmp_path / "runs.jsonl")

    assert result["status"] == "failed"
    assert result["error"] == "missing_required_market_data"
    assert result["progress_pct"] == 100
    assert list_refresh_events(job["job_id"], db_path=db_path)[-1]["phase"] == "failed"


def test_refresh_runner_marks_exception_as_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "refresh_jobs.sqlite"
    job = create_refresh_job(lane_id="all", db_path=db_path)

    from scripts import refresh_dashboard_state as dashboard_refresh

    def explode(**kwargs):
        raise RuntimeError("Bearer SECRET MASSIVE_API_KEY")

    monkeypatch.setattr(dashboard_refresh, "refresh_dashboard_state", explode)

    result = run_refresh_job(job["job_id"], db_path=db_path, journal_path=tmp_path / "runs.jsonl")

    assert result["status"] == "failed"
    assert result["error"] == "RuntimeError"
    assert result["progress_pct"] == 100
    assert "SECRET" not in str(result)
    assert "MASSIVE_API_KEY" not in str(result)


def test_refresh_runner_rejects_missing_job(tmp_path):
    with pytest.raises(KeyError):
        run_refresh_job("missing", db_path=tmp_path / "refresh_jobs.sqlite", journal_path=tmp_path / "runs.jsonl")
