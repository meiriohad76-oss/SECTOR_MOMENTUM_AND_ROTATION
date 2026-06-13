from __future__ import annotations

import pandas as pd
import pytest

from src import pl_tracker
from src.portfolio import HoldingInput


def test_latest_prices_from_ohlcv_uses_last_valid_close(market_ohlcv):
    prices = pl_tracker.latest_prices_from_ohlcv(market_ohlcv)

    assert prices["XLK"] == pytest.approx(market_ohlcv["XLK"]["close"].dropna().iloc[-1])
    assert prices["SPY"] == pytest.approx(market_ohlcv["SPY"]["close"].dropna().iloc[-1])


def test_analyze_position_pnl_computes_unrealized_totals_from_holdings():
    holdings = [
        HoldingInput(ticker="XLK", shares=10, cost_basis=90),
        HoldingInput(ticker="XLF", shares=5, cost_basis=120),
    ]

    result = pl_tracker.analyze_position_pnl(holdings, {"XLK": 100, "XLF": 100})

    assert [row.ticker for row in result.rows] == ["XLK", "XLF"]
    assert result.rows[0].unrealized_pnl == pytest.approx(100)
    assert result.rows[1].unrealized_pnl == pytest.approx(-100)
    assert result.total_cost == pytest.approx(1500)
    assert result.total_value == pytest.approx(1500)
    assert result.unrealized_pnl == pytest.approx(0)
    assert result.missing_tickers == []


def test_analyze_position_pnl_falls_back_to_market_value_when_price_missing():
    holdings = [HoldingInput(ticker="XLK", shares=10, cost_basis=90, market_value=1100)]

    result = pl_tracker.analyze_position_pnl(holdings, {})

    assert result.rows[0].current_price == pytest.approx(110)
    assert result.rows[0].current_value == pytest.approx(1100)
    assert result.rows[0].unrealized_pnl == pytest.approx(200)


def test_analyze_position_pnl_reports_missing_inputs_without_crashing():
    holdings = [
        HoldingInput(ticker="XLK", shares=10),
        HoldingInput(ticker="XLF", shares=0, cost_basis=20),
    ]

    result = pl_tracker.analyze_position_pnl(holdings, {"XLK": 100, "XLF": 100})

    assert result.rows[0].missing_reason == "cost basis missing"
    assert result.rows[1].missing_reason == "shares missing"
    assert result.missing_tickers == ["XLK", "XLF"]
    assert result.total_cost == pytest.approx(0)


def test_pnl_rows_frame_formats_operator_columns():
    result = pl_tracker.analyze_position_pnl(
        [HoldingInput(ticker="XLK", shares=10, cost_basis=90)],
        {"XLK": 100},
    )

    frame = pl_tracker.pnl_rows_frame(result)

    assert frame.to_dict("records") == [
        {
            "Ticker": "XLK",
            "Shares": "10.00",
            "Cost": "$900.00",
            "Value": "$1,000.00",
            "P&L": "$100.00",
            "P&L %": "11.1%",
            "Status": "OK",
        }
    ]
