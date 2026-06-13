from __future__ import annotations

import pytest

from src.api_refresh import (
    append_refresh_event,
    create_refresh_job,
    get_refresh_job,
    list_refresh_events,
    normalize_refresh_lane,
    queued_refresh_response,
)


def test_refresh_job_queue_persists_job_and_initial_event(tmp_path):
    db_path = tmp_path / "refresh_jobs.sqlite"

    job = create_refresh_job(lane_id="market_ohlcv", db_path=db_path, metadata={"requested_by": "test"})

    assert job["lane_id"] == "market_ohlcv"
    assert job["status"] == "queued"
    assert job["progress_pct"] == 0
    assert job["metadata"] == {"requested_by": "test"}
    assert get_refresh_job(job["job_id"], db_path=db_path) == job
    assert list_refresh_events(job["job_id"], db_path=db_path)[0]["phase"] == "queued"
    assert queued_refresh_response(job) == {
        "job_id": job["job_id"],
        "lane_id": "market_ohlcv",
        "status": "queued",
        "progress_pct": 0,
        "message": "Refresh queued for lane market_ohlcv",
        "status_url": f"/api/v1/refresh/{job['job_id']}",
        "events_url": f"/api/v1/refresh/{job['job_id']}/events",
    }


def test_refresh_job_events_update_status_progress_and_terminal_time(tmp_path):
    db_path = tmp_path / "refresh_jobs.sqlite"
    job = create_refresh_job(lane_id="all", db_path=db_path)

    running = append_refresh_event(
        job["job_id"],
        status="running",
        phase="download_market_ohlcv",
        progress_pct=35,
        message="Downloading market OHLCV",
        db_path=db_path,
    )
    assert running["status"] == "running"
    assert running["started_at_utc"]
    assert running["completed_at_utc"] is None
    assert running["progress_pct"] == 35

    complete = append_refresh_event(
        job["job_id"],
        status="succeeded",
        phase="complete",
        progress_pct=100,
        message="Refresh complete",
        metadata={"fetched": 89},
        db_path=db_path,
    )
    events = list_refresh_events(job["job_id"], db_path=db_path)

    assert complete["status"] == "succeeded"
    assert complete["completed_at_utc"]
    assert complete["message"] == "Refresh complete"
    assert [event["phase"] for event in events] == ["queued", "download_market_ohlcv", "complete"]
    assert events[-1]["metadata"] == {"fetched": 89}


def test_refresh_job_validates_lane_and_missing_job(tmp_path):
    db_path = tmp_path / "refresh_jobs.sqlite"

    assert normalize_refresh_lane("BAD") == "all"
    job = create_refresh_job(lane_id="BAD", db_path=db_path)
    assert job["lane_id"] == "all"
    assert get_refresh_job("missing", db_path=db_path) is None
    assert list_refresh_events("missing", db_path=db_path) == []
    with pytest.raises(KeyError):
        append_refresh_event("missing", db_path=db_path)
