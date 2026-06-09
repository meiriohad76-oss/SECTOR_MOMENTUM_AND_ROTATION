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


def test_data_health_and_provider_health_endpoints_use_injected_provider():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api_server import create_app

    payload = {
        "api_version": "v1",
        "generated_at": "2026-06-09T10:00:00+00:00",
        "app": {"name": "sector-momentum-dashboard"},
        "health": {"status": "warning"},
        "provider_flow": {"provider_count": 2},
        "lanes": [
            {"lane_id": "state_persistence", "status": "healthy"},
            {"lane_id": "provider_flow_readiness", "status": "warning"},
            {"lane_id": "provider_flow_cache", "status": "warning"},
        ],
    }
    app = create_app(
        status_provider=lambda: {"ok": True},
        data_health_provider=lambda: payload,
    )
    client = TestClient(app)

    data_health = client.get("/api/v1/data-health")
    provider_health = client.get("/api/v1/provider-health")

    assert data_health.status_code == 200
    assert data_health.json() == payload
    assert provider_health.status_code == 200
    assert [lane["lane_id"] for lane in provider_health.json()["lanes"]] == [
        "provider_flow_readiness",
        "provider_flow_cache",
    ]
    assert provider_health.json()["provider_flow"] == {"provider_count": 2}


def test_dashboard_snapshot_endpoint_uses_injected_provider_and_ticker_query():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api_server import create_app

    calls = []

    def snapshot_provider(**kwargs):
        calls.append(kwargs)
        return {"api_version": "v1", "status": "ready", "focus": {"ticker": kwargs.get("focus_ticker")}}

    app = create_app(
        status_provider=lambda: {"ok": True},
        snapshot_provider=snapshot_provider,
    )
    client = TestClient(app)

    response = client.get("/api/v1/dashboard-snapshot?ticker=XLK")

    assert response.status_code == 200
    assert response.json()["focus"] == {"ticker": "XLK"}
    assert calls == [{"focus_ticker": "XLK"}]


def test_portfolio_analyze_endpoint_uses_injected_snapshot_provider():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api_server import create_app

    calls = []

    def snapshot_provider(**kwargs):
        calls.append(kwargs)
        return {
            "api_version": "v1",
            "status": "ready",
            "rows": [
                {
                    "ticker": "XLK",
                    "asset_class": "US Sectors",
                    "state": "STAGE_2_BULLISH",
                    "s_score": 1.2,
                    "f_score": 0.4,
                    "payload": {"rank_in_class": 1, "selected": True, "veto": False},
                }
            ],
        }

    app = create_app(
        status_provider=lambda: {"ok": True},
        snapshot_provider=snapshot_provider,
    )
    client = TestClient(app)

    response = client.post("/api/v1/portfolio/analyze", json={"ticker": "XLK"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["rows"][0]["ticker"] == "XLK"
    assert payload["rows"][0]["state"] == "STAGE_2_BULLISH"
    assert calls == [{}]


def test_backtest_artifacts_endpoint_uses_injected_provider():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api_server import create_app

    payload = {
        "api_version": "v1",
        "status": "ready",
        "artifacts": [{"id": "report", "status": "verified"}],
        "equity": {"row_count": 1, "rows": [{"date": "2026-01-01", "methodology": 1.0}]},
    }
    app = create_app(
        status_provider=lambda: {"ok": True},
        backtest_artifacts_provider=lambda: payload,
    )
    client = TestClient(app)

    response = client.get("/api/v1/backtest-artifacts")

    assert response.status_code == 200
    assert response.json() == payload


def test_ticker_chart_endpoint_uses_injected_provider():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api_server import create_app

    calls = []

    def chart_provider(**kwargs):
        calls.append(kwargs)
        return {
            "api_version": "v1",
            "status": "ready",
            "ticker": kwargs["ticker"],
            "period": kwargs["period"],
            "series": [{"date": "2026-01-02", "close": 100.0, "ma30w": 98.0}],
        }

    app = create_app(
        status_provider=lambda: {"ok": True},
        ticker_chart_provider=chart_provider,
    )
    client = TestClient(app)

    response = client.get("/api/v1/ticker-chart?ticker=XLK&period=1y")

    assert response.status_code == 200
    assert response.json()["ticker"] == "XLK"
    assert response.json()["period"] == "1y"
    assert calls == [{"ticker": "XLK", "period": "1y"}]
