from __future__ import annotations

import base64

from src.api_portfolio import build_portfolio_analysis_payload


def _snapshot_payload():
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
            },
            {
                "ticker": "XLE",
                "asset_class": "US Sectors",
                "state": "WARNING",
                "s_score": -0.5,
                "f_score": -0.8,
                "payload": {"rank_in_class": 8, "selected": False, "veto": True},
            },
        ],
    }


def test_portfolio_analysis_payload_maps_json_holdings_to_snapshot_rows():
    payload = build_portfolio_analysis_payload(
        {
            "holdings": [
                {"ticker": "XLK", "weight": 0.6, "market_value": 6000},
                {"ticker": "MISSING", "weight": 0.4},
            ]
        },
        snapshot_payload=_snapshot_payload(),
    )

    assert payload["status"] == "ready"
    assert payload["input"]["holding_count"] == 2
    assert [row["ticker"] for row in payload["rows"]] == ["XLK", "MISSING"]
    assert payload["rows"][0]["state"] == "STAGE_2_BULLISH"
    assert payload["rows"][0]["selected"] is True
    assert payload["rows"][1]["missing"] is True
    assert payload["summary"]["missing_tickers"] == ["MISSING"]
    assert payload["summary"]["state_exposure"]["STAGE_2_BULLISH"] == 0.6
    assert payload["summary"]["state_exposure"]["MISSING"] == 0.4


def test_portfolio_analysis_payload_accepts_single_ticker_and_base64_csv():
    single = build_portfolio_analysis_payload({"ticker": "xlk"}, snapshot_payload=_snapshot_payload())
    assert single["status"] == "ready"
    assert single["rows"][0]["ticker"] == "XLK"
    assert single["rows"][0]["analysis_weight"] == 1.0

    csv_payload = "Ticker,Weight\nXLK,75%\nXLE,25%\n"
    encoded = base64.b64encode(csv_payload.encode("utf-8")).decode("ascii")
    uploaded = build_portfolio_analysis_payload(
        {"file_name": "portfolio.csv", "content_base64": encoded},
        snapshot_payload=_snapshot_payload(),
    )
    assert uploaded["status"] == "ready"
    assert [row["ticker"] for row in uploaded["rows"]] == ["XLK", "XLE"]
    assert uploaded["summary"]["action_tickers"]["warning"] == ["XLE"]


def test_portfolio_analysis_payload_reports_invalid_input_without_snapshot_mutation():
    payload = build_portfolio_analysis_payload(
        {"content_base64": "not valid base64"},
        snapshot_payload=_snapshot_payload(),
    )

    assert payload["status"] == "invalid"
    assert payload["rows"] == []
    assert "not valid base64" in payload["input"]["errors"][0]["message"]
