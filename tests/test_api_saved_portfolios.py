from __future__ import annotations

from src.api_saved_portfolios import (
    build_saved_portfolios_payload,
    delete_saved_portfolio_payload,
    save_saved_portfolio_payload,
)


def test_saved_portfolio_api_saves_lists_and_deletes_portfolio(tmp_path):
    store_path = tmp_path / "saved_inputs.json"

    save_payload = save_saved_portfolio_payload(
        {
            "name": "Core Sleeve",
            "holdings": [
                {"ticker": "xlk", "weight": 0.6, "account": "taxable"},
                {"ticker": "xle", "market_value": 4000},
            ],
        },
        path=store_path,
    )

    assert save_payload["status"] == "ready"
    assert save_payload["portfolio"]["name"] == "Core Sleeve"
    assert save_payload["portfolio"]["holding_count"] == 2
    assert save_payload["portfolio"]["holdings"][0]["ticker"] == "XLK"

    list_payload = build_saved_portfolios_payload(store_path)

    assert list_payload["status"] == "ready"
    assert list_payload["portfolio_count"] == 1
    assert list_payload["portfolios"][0]["holdings"][1]["ticker"] == "XLE"

    delete_payload = delete_saved_portfolio_payload("core sleeve", path=store_path)

    assert delete_payload["status"] == "deleted"
    assert build_saved_portfolios_payload(store_path)["portfolio_count"] == 0


def test_saved_portfolio_api_validates_name_and_parse_errors(tmp_path):
    store_path = tmp_path / "saved_inputs.json"

    no_name = save_saved_portfolio_payload({"ticker": "XLK"}, path=store_path)
    no_input = save_saved_portfolio_payload({"name": "Empty"}, path=store_path)

    assert no_name["status"] == "invalid"
    assert "name is required" in no_name["message"]
    assert no_input["status"] == "invalid"
    assert no_input["errors"][0]["message"] == "ticker, holdings, csv, or content_base64 is required"
    assert build_saved_portfolios_payload(store_path)["portfolios"] == []
