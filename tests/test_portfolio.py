from __future__ import annotations

import io
import zipfile

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


def test_parse_holdings_excel_ignores_unsupported_conditional_formatting_metadata():
    frame = pd.DataFrame({"Ticker": ["orcl", "xlf"], "Weight": ["60%", "40%"]})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
    workbook = _inject_invalid_conditional_formatting(buffer.getvalue())

    result = portfolio.parse_holdings_excel(workbook)

    assert result.errors == []
    assert [holding.ticker for holding in result.holdings] == ["ORCL", "XLF"]
    assert [holding.weight for holding in result.holdings] == pytest.approx([0.6, 0.4])


def test_parse_holdings_excel_reports_unreadable_workbook_bytes():
    result = portfolio.parse_holdings_excel(b"not an excel file")

    assert result.holdings == []
    assert len(result.errors) == 1
    assert "could not read Excel file" in result.errors[0].message


def _inject_invalid_conditional_formatting(payload: bytes) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zin:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "xl/worksheets/sheet1.xml":
                    xml = data.decode("utf-8")
                    unsupported_rule = (
                        '<conditionalFormatting sqref="A2:A3">'
                        '<cfRule type="cellIs" priority="1" operator="notContainsText">'
                        "<formula>XLK</formula>"
                        "</cfRule>"
                        "</conditionalFormatting>"
                    )
                    data = xml.replace("</worksheet>", unsupported_rule + "</worksheet>").encode("utf-8")
                zout.writestr(item, data)
    return out.getvalue()


def _scored_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "state": ["STAGE_2_BULLISH", "WARNING", "EXIT"],
            "class": ["US Sectors", "US Sectors", "US Industries"],
            "S_score": [1.25, -0.35, -2.0],
            "F_score": [0.80, -0.20, -1.10],
            "rank_in_class": [1, 5, 12],
            "selected": [True, False, False],
            "veto": [False, False, True],
        },
        index=["XLK", "XLF", "SOXX"],
    )


def test_analyze_holdings_joins_scored_rows_and_state_exposure():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", weight=0.60),
        portfolio.HoldingInput(ticker="XLF", weight=0.40),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert analysis.missing_tickers == []
    assert [row.ticker for row in analysis.rows] == ["XLK", "XLF"]
    assert analysis.rows[0].state == "STAGE_2_BULLISH"
    assert analysis.rows[0].asset_class == "US Sectors"
    assert analysis.rows[0].s_score == pytest.approx(1.25)
    assert analysis.rows[0].f_score == pytest.approx(0.80)
    assert analysis.rows[0].selected is True
    assert analysis.rows[0].veto is False
    assert analysis.state_exposure == pytest.approx(
        {"STAGE_2_BULLISH": 0.60, "WARNING": 0.40}
    )
    assert analysis.class_exposure == pytest.approx({"US Sectors": 1.0})
    assert analysis.action_tickers == {
        "exit": [],
        "warning": ["XLF"],
        "bullish": ["XLK"],
    }


def test_analyze_holdings_reports_unknown_tickers_and_keeps_missing_exposure():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", weight=0.25),
        portfolio.HoldingInput(ticker="ZZZZ", weight=0.75),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert analysis.missing_tickers == ["ZZZZ"]
    assert analysis.rows[1].missing is True
    assert analysis.rows[1].missing_reason == "ticker not found in scored universe"
    assert analysis.rows[1].state is None
    assert analysis.rows[1].analysis_weight == pytest.approx(0.75)
    assert analysis.state_exposure == pytest.approx(
        {"STAGE_2_BULLISH": 0.25, "MISSING": 0.75}
    )
    assert analysis.class_exposure == pytest.approx(
        {"US Sectors": 0.25, "MISSING": 0.75}
    )


def test_analyze_holdings_infers_weights_from_market_value_when_weights_missing():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", market_value=2500.0),
        portfolio.HoldingInput(ticker="XLF", market_value=7500.0),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert [row.analysis_weight for row in analysis.rows] == pytest.approx([0.25, 0.75])
    assert analysis.state_exposure == pytest.approx(
        {"STAGE_2_BULLISH": 0.25, "WARNING": 0.75}
    )


def test_analyze_holdings_preserves_zero_explicit_weights():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", weight=0.0),
        portfolio.HoldingInput(ticker="XLF", weight=0.5),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert [row.analysis_weight for row in analysis.rows] == pytest.approx([0.0, 1.0])
    assert analysis.state_exposure == pytest.approx({"STAGE_2_BULLISH": 0.0, "WARNING": 1.0})


def test_analyze_holdings_equal_weights_when_no_weight_or_market_value_exists():
    holdings = [
        portfolio.HoldingInput(ticker="XLK"),
        portfolio.HoldingInput(ticker="XLF"),
        portfolio.HoldingInput(ticker="SOXX"),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert [row.analysis_weight for row in analysis.rows] == pytest.approx(
        [1 / 3, 1 / 3, 1 / 3]
    )
    assert analysis.action_tickers["exit"] == ["SOXX"]
    assert analysis.action_tickers["warning"] == ["XLF"]
    assert analysis.action_tickers["bullish"] == ["XLK"]


def test_analyze_holdings_does_not_mutate_scored_dataframe():
    scored = _scored_fixture()
    original = scored.copy(deep=True)

    portfolio.analyze_holdings([portfolio.HoldingInput(ticker="XLK")], scored)

    pd.testing.assert_frame_equal(scored, original)


def test_analyze_holdings_parses_string_booleans_from_scored_dataframe():
    scored = _scored_fixture()
    scored["selected"] = pd.Series(["False", "true", "0"], index=scored.index, dtype=object)
    scored["veto"] = pd.Series(["0", "1", "no"], index=scored.index, dtype=object)

    analysis = portfolio.analyze_holdings(
        [
            portfolio.HoldingInput(ticker="XLK"),
            portfolio.HoldingInput(ticker="XLF"),
            portfolio.HoldingInput(ticker="SOXX"),
        ],
        scored,
    )

    assert [row.selected for row in analysis.rows] == [False, True, False]
    assert [row.veto for row in analysis.rows] == [False, True, False]


def test_analyze_holdings_rejects_duplicate_scored_ticker_index():
    scored = pd.concat([_scored_fixture(), _scored_fixture().loc[["XLK"]]])

    with pytest.raises(ValueError, match="scored_df index must contain unique tickers"):
        portfolio.analyze_holdings([portfolio.HoldingInput(ticker="XLK")], scored)


def test_analysis_rows_frame_formats_display_columns_and_missing_rows():
    analysis = portfolio.analyze_holdings(
        [
            portfolio.HoldingInput(ticker="XLK", weight=0.25),
            portfolio.HoldingInput(ticker="ZZZZ", weight=0.75),
        ],
        _scored_fixture(),
    )

    frame = portfolio.analysis_rows_frame(analysis)

    assert frame.to_dict("records") == [
        {
            "Ticker": "XLK",
            "Weight": "25.0%",
            "State": "STAGE 2 BULLISH",
            "Class": "US Sectors",
            "S": "1.25",
            "F": "0.80",
            "Rank": "1",
            "Selected": "YES",
            "Veto": "NO",
        },
        {
            "Ticker": "ZZZZ",
            "Weight": "75.0%",
            "State": "MISSING",
            "Class": "MISSING",
            "S": "-",
            "F": "-",
            "Rank": "-",
            "Selected": "-",
            "Veto": "-",
        },
    ]


def test_analysis_rows_frame_formats_nan_rank_as_blank():
    scored = _scored_fixture()
    scored["rank_in_class"] = scored["rank_in_class"].astype(object)
    scored.loc["XLK", "rank_in_class"] = "nan"
    analysis = portfolio.analyze_holdings([portfolio.HoldingInput(ticker="XLK")], scored)

    frame = portfolio.analysis_rows_frame(analysis)

    assert frame.loc[0, "Rank"] == "-"


def test_exposure_frame_sorts_by_weight_descending():
    frame = portfolio.exposure_frame(
        {"WARNING": 0.15, "STAGE_2_BULLISH": 0.80, "MISSING": 0.05},
        label="State",
    )

    assert frame.to_dict("records") == [
        {"State": "STAGE 2 BULLISH", "Weight": "80.0%"},
        {"State": "WARNING", "Weight": "15.0%"},
        {"State": "MISSING", "Weight": "5.0%"},
    ]
