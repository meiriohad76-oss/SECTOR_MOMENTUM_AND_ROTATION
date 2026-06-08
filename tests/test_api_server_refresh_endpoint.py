from __future__ import annotations

import pytest


def test_refresh_endpoint_queues_by_default_without_running_worker():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    calls = []

    from src.api_server import create_app

    app = create_app(status_provider=lambda: {"ok": True}, refresh_runner=lambda *args, **kwargs: calls.append(args))
    client = TestClient(app)

    response = client.post("/api/v1/refresh", json={"lane_id": "market_ohlcv", "requested_by": "test"})

    assert response.status_code == 202
    body = response.json()
    assert body["lane_id"] == "market_ohlcv"
    assert body["status"] == "queued"
    assert body["progress_pct"] == 0
    assert calls == []


def test_refresh_endpoint_can_run_worker_synchronously_when_explicitly_requested():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    calls = []

    from src.api_server import create_app

    def fake_runner(job_id, **kwargs):
        calls.append((job_id, kwargs))
        return {
            "job_id": job_id,
            "lane_id": kwargs["lane_id"],
            "status": "succeeded",
            "progress_pct": 100,
            "message": "Refresh complete",
        }

    app = create_app(status_provider=lambda: {"ok": True}, refresh_runner=fake_runner)
    client = TestClient(app)

    response = client.post(
        "/api/v1/refresh",
        json={
            "lane_id": "fred_macro",
            "run_now": True,
            "background": False,
            "period": "5y",
            "provider_flow_mode": "cache-only",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["progress_pct"] == 100
    assert len(calls) == 1
    assert calls[0][1] == {
        "lane_id": "fred_macro",
        "period": "5y",
        "force_refresh": True,
        "provider_flow_mode": "cache-only",
        "allow_stale_provider_cache": True,
    }
