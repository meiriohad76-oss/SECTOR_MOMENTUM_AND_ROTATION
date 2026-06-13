from __future__ import annotations

import pandas as pd
import pytest

from src import personal_trades


def test_parse_trade_history_csv_accepts_common_broker_aliases():
    csv_text = """Trade Date,Symbol,Side,Quantity,Price,Fees
2024-01-02,xlk,Buy,10,100,1.25
2024-02-05,XLF,SELL,5,40,0
"""

    result = personal_trades.parse_trade_history_csv(csv_text)

    assert result.errors == []
    assert [trade.ticker for trade in result.trades] == ["XLK", "XLF"]
    assert result.trades[0].side == "BUY"
    assert result.trades[0].shares == pytest.approx(10)
    assert result.trades[0].price == pytest.approx(100)
    assert result.trades[0].fees == pytest.approx(1.25)


def test_parse_trade_history_csv_reports_missing_columns_and_bad_rows():
    result = personal_trades.parse_trade_history_csv("Ticker,Side,Shares\nXLK,BUY,ten\n")

    assert result.trades == []
    messages = [error.message for error in result.errors]
    assert "trade file must include a date column" in messages
    assert "shares must be numeric" in messages


def test_evaluate_trade_history_aligns_user_actions_to_methodology_states():
    trades = [
        personal_trades.TradeInput(pd.Timestamp("2024-01-03"), "XLK", "BUY", 10, 100, 0),
        personal_trades.TradeInput(pd.Timestamp("2024-01-05"), "XLF", "SELL", 5, 40, 0),
        personal_trades.TradeInput(pd.Timestamp("2024-01-05"), "XLV", "BUY", 3, 80, 0),
    ]
    states = pd.DataFrame(
        {
            "XLK": ["STAGE_2_BULLISH", "WARNING"],
            "XLF": ["HOLD", "EXIT"],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-04"]),
    )

    result = personal_trades.evaluate_trade_history(trades, states)

    assert [row.alignment for row in result.rows] == ["ALIGNED", "ALIGNED", "NO_METHOD_STATE"]
    assert result.aligned_count == 2
    assert result.not_aligned_count == 0
    assert result.unavailable_count == 1
    assert result.rows[0].methodology_state == "STAGE_2_BULLISH"
    assert result.rows[1].methodology_state == "EXIT"


def test_evaluate_trade_history_flags_counter_methodology_actions():
    trades = [
        personal_trades.TradeInput(pd.Timestamp("2024-01-03"), "XLK", "BUY", 10, 100, 0),
        personal_trades.TradeInput(pd.Timestamp("2024-01-03"), "XLF", "SELL", 5, 40, 0),
    ]
    states = pd.DataFrame(
        {"XLK": ["EXIT"], "XLF": ["STAGE_2_BULLISH"]},
        index=pd.to_datetime(["2024-01-02"]),
    )

    result = personal_trades.evaluate_trade_history(trades, states)

    assert [row.alignment for row in result.rows] == ["AGAINST_METHOD", "AGAINST_METHOD"]
    assert result.not_aligned_count == 2


def test_trade_alignment_frame_formats_rows():
    result = personal_trades.evaluate_trade_history(
        [personal_trades.TradeInput(pd.Timestamp("2024-01-03"), "XLK", "BUY", 10, 100, 1.0)],
        pd.DataFrame({"XLK": ["HOLD"]}, index=pd.to_datetime(["2024-01-02"])),
    )

    frame = personal_trades.trade_alignment_frame(result)

    assert frame.to_dict("records") == [
        {
            "Date": "2024-01-03",
            "Ticker": "XLK",
            "Side": "BUY",
            "Shares": "10.00",
            "Price": "$100.00",
            "State Date": "2024-01-02",
            "Method State": "HOLD",
            "Alignment": "ALIGNED",
        }
    ]
