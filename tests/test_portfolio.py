from __future__ import annotations

import io

import pandas as pd
import pytest

from src import portfolio


def test_parse_single_ticker_normalizes_symbol_to_one_full_weight_holding():
    result = portfolio.parse_single_ticker(" xlk ")

    assert result.errors == []
    assert len(result.holdings) == 1
    assert result.holdings[0].ticker == "XLK"
    assert result.holdings[0].weight == pytest.approx(1.0)


def test_parse_single_ticker_reports_invalid_characters():
    result = portfolio.parse_single_ticker("not a ticker")

    assert result.holdings == []
    assert len(result.errors) == 1
    assert result.errors[0].message == "ticker has invalid characters"


def test_parse_holdings_csv_accepts_aliases_and_normalizes_weights():
    csv_text = """Symbol,Quantity,Market Value,Weight,Account,Notes
xlk,10,"2,500",25%,IRA,core technology
xlf,5,1250,25,Taxable,financial sleeve
"""

    result = portfolio.parse_holdings_csv(csv_text)

    assert result.errors == []
    assert [holding.ticker for holding in result.holdings] == ["XLK", "XLF"]
    assert result.holdings[0].shares == pytest.approx(10.0)
    assert result.holdings[0].market_value == pytest.approx(2500.0)
    assert result.holdings[0].weight == pytest.approx(0.25)
    assert result.holdings[0].account == "IRA"
    assert result.holdings[1].weight == pytest.approx(0.25)


def test_parse_holdings_csv_reports_blank_ticker_rows_without_dropping_valid_rows():
    csv_text = """ticker,shares,weight
XLK,10,0.5
,4,0.5
XLF,5,50%
"""

    result = portfolio.parse_holdings_csv(csv_text)

    assert [holding.ticker for holding in result.holdings] == ["XLK", "XLF"]
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 3
    assert "ticker is required" in result.errors[0].message


def test_parse_holdings_csv_reports_missing_ticker_column():
    result = portfolio.parse_holdings_csv("name,shares\nTechnology,10\n")

    assert result.holdings == []
    assert len(result.errors) == 1
    assert result.errors[0].row_number is None
    assert "ticker column" in result.errors[0].message


def test_parse_holdings_csv_reports_unreadable_bytes():
    result = portfolio.parse_holdings_csv(b"\xff\xfe\xfa")

    assert result.holdings == []
    assert len(result.errors) == 1
    assert "could not read CSV file" in result.errors[0].message


def test_parse_holdings_csv_reports_parser_errors():
    result = portfolio.parse_holdings_csv('Ticker,Weight\n"XLK,100%\n')

    assert result.holdings == []
    assert len(result.errors) == 1
    assert "could not read CSV file" in result.errors[0].message


def test_parse_holdings_csv_reports_invalid_ticker_text():
    result = portfolio.parse_holdings_csv("Ticker,Weight\nnot a ticker,100%\n")

    assert result.holdings == []
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 2
    assert "ticker has invalid characters" in result.errors[0].message


def test_parse_holdings_csv_reports_bad_numeric_cells_without_rejecting_row():
    result = portfolio.parse_holdings_csv("Ticker,Shares,Weight\nXLK,ten,nope\n")

    assert [holding.ticker for holding in result.holdings] == ["XLK"]
    assert result.holdings[0].shares is None
    assert result.holdings[0].weight is None
    assert [(error.column, error.message) for error in result.errors] == [
        ("Shares", "shares must be numeric"),
        ("Weight", "weight must be numeric"),
    ]
    assert all(error.row_number == 2 for error in result.errors)


def test_parse_holdings_excel_accepts_xlsx_bytes():
    frame = pd.DataFrame({"Ticker": ["xlk", "xlf"], "Weight": ["60%", "40%"]})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)

    result = portfolio.parse_holdings_excel(buffer.getvalue())

    assert result.errors == []
    assert [holding.ticker for holding in result.holdings] == ["XLK", "XLF"]
    assert [holding.weight for holding in result.holdings] == pytest.approx([0.6, 0.4])
