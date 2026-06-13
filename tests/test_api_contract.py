from __future__ import annotations

from datetime import datetime, timezone

from src.api_contract import API_VERSION, build_dashboard_status_payload, normalize_health_lane


def test_normalize_health_lane_returns_json_safe_contract():
    lane = normalize_health_lane(
        {
            "lane_id": "market_ohlcv",
            "source": "Market OHLCV",
            "role": "Critical: price data",
            "status": "warning",
            "severity_symbol": "WARN",
            "latest": "2026-06-08",
            "freshness": "latest today; oldest 4d old",
            "coverage": "oldest 2026-06-04 (4d old)",
            "detail": "89/89 symbols loaded",
            "sla": "fresh <=5d; stale >10d",
            "refresh_label": "Refresh market OHLCV",
            "refresh_key": "data_health_refresh_market_ohlcv",
            "providers": [
                {
                    "id": "massive_block_trades",
                    "label": "Massive block trades",
                    "provider": "Massive",
                    "status": "warning",
                    "mode": "partial",
                    "signal": "block_up_ratio",
                    "detail": "78 live ok / 8 warning",
                }
            ],
        }
    )

    assert lane == {
        "lane_id": "market_ohlcv",
        "source": "Market OHLCV",
        "role": "Critical: price data",
        "status": "warning",
        "severity_symbol": "WARN",
        "latest": "2026-06-08",
        "freshness": "latest today; oldest 4d old",
        "coverage": "oldest 2026-06-04 (4d old)",
        "detail": "89/89 symbols loaded",
        "sla": "fresh <=5d; stale >10d",
        "refresh_label": "Refresh market OHLCV",
        "refresh_key": "data_health_refresh_market_ohlcv",
        "providers": [
            {
                "id": "massive_block_trades",
                "label": "Massive block trades",
                "provider": "Massive",
                "status": "warning",
                "mode": "partial",
                "signal": "block_up_ratio",
                "detail": "78 live ok / 8 warning",
            }
        ],
    }


def test_build_dashboard_status_payload_summarizes_lanes_for_future_clients():
    payload = build_dashboard_status_payload(
        [
            {"lane_id": "market_ohlcv", "source": "Market OHLCV", "status": "healthy"},
            {"lane_id": "provider_flow", "source": "Provider-flow feeds", "status": "warning"},
        ],
        app_version="v2.4.11",
        git_sha="abc123",
        generated_at=datetime(2026, 6, 8, 15, 30, tzinfo=timezone.utc),
    )

    assert payload["api_version"] == API_VERSION
    assert payload["generated_at"] == "2026-06-08T15:30:00+00:00"
    assert payload["app"] == {
        "name": "sector-momentum-dashboard",
        "version": "v2.4.11",
        "git_sha": "abc123",
        "active_frontend": "streamlit",
        "migration_stage": "streamlit_compat_api_foundation",
    }
    assert payload["health"]["status"] == "warning"
    assert payload["health"]["label"] == "Data warning"
    assert payload["health"]["lane_count"] == 2
    assert payload["health"]["critical_statuses"] == ["healthy", "warning"]
    assert [lane["lane_id"] for lane in payload["lanes"]] == ["market_ohlcv", "provider_flow"]
