from __future__ import annotations

import io

import pandas as pd
import pytest

from src import custom_universe


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


def test_parse_custom_universe_text_normalizes_deduplicates_and_reports_invalid_tokens():
    result = custom_universe.parse_custom_universe_text("xlk, xlf\nXLK;BRK/B")

    assert result.tickers == ["XLK", "XLF"]
    assert result.duplicate_tickers == ["XLK"]
    assert len(result.errors) == 1
    assert result.errors[0].message == "ticker has invalid characters"
    assert result.errors[0].token == "BRK/B"


def test_parse_custom_universe_text_allows_empty_input_without_warning():
    result = custom_universe.parse_custom_universe_text("")

    assert result.tickers == []
    assert result.errors == []
    assert result.duplicate_tickers == []


def test_parse_custom_universe_file_accepts_ticker_alias_columns():
    result = custom_universe.parse_custom_universe_file("Symbol\nxlk\nxlf\nXLK\n", "watchlist.csv")

    assert result.tickers == ["XLK", "XLF"]
    assert result.duplicate_tickers == ["XLK"]
    assert result.errors == []


def test_parse_custom_universe_file_ignores_non_ticker_watchlist_columns():
    csv_text = """Ticker,Weight,Shares,Notes
XLK,overweight,core,technology sleeve
XLF,underweight,avoid,rate sensitivity
"""

    result = custom_universe.parse_custom_universe_file(csv_text, "watchlist.csv")

    assert result.tickers == ["XLK", "XLF"]
    assert result.errors == []


def test_parse_custom_universe_file_accepts_xlsx_uploads():
    buffer = io.BytesIO()
    frame = pd.DataFrame({"Asset": ["xlk", "xlf"]})
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)

    result = custom_universe.parse_custom_universe_file(buffer.getvalue(), "watchlist.xlsx")

    assert result.tickers == ["XLK", "XLF"]
    assert result.errors == []


def test_parse_custom_universe_file_converts_parser_errors():
    result = custom_universe.parse_custom_universe_file("Name\nTechnology\n", "watchlist.csv")

    assert result.tickers == []
    assert len(result.errors) == 1
    assert "ticker column" in result.errors[0].message


def test_analyze_custom_universe_ranks_available_tickers_and_keeps_missing_rows():
    analysis = custom_universe.analyze_custom_universe(["XLF", "ZZZZ", "XLK"], _scored_fixture())

    assert analysis.available_tickers == ["XLK", "XLF"]
    assert analysis.missing_tickers == ["ZZZZ"]
    assert [row.ticker for row in analysis.rows] == ["XLK", "XLF", "ZZZZ"]
    assert [row.custom_rank for row in analysis.rows] == [1, 2, None]
    assert analysis.class_counts == {"US Sectors": 2, "MISSING": 1}
    assert analysis.state_counts == {"STAGE_2_BULLISH": 1, "WARNING": 1, "MISSING": 1}
    assert analysis.action_tickers == {
        "exit": [],
        "warning": ["XLF"],
        "bullish": ["XLK"],
    }


def test_analyze_custom_universe_does_not_mutate_scored_dataframe():
    scored = _scored_fixture()
    original = scored.copy(deep=True)

    custom_universe.analyze_custom_universe(["XLK", "XLF"], scored)

    pd.testing.assert_frame_equal(scored, original)


def test_analyze_custom_universe_rejects_duplicate_scored_ticker_index():
    scored = pd.concat([_scored_fixture(), _scored_fixture().loc[["XLK"]]])

    with pytest.raises(ValueError, match="scored_df index must contain unique tickers"):
        custom_universe.analyze_custom_universe(["XLK"], scored)


def test_custom_universe_rows_frame_formats_rank_scores_and_missing_values():
    analysis = custom_universe.analyze_custom_universe(["XLF", "ZZZZ", "XLK"], _scored_fixture())

    frame = custom_universe.custom_universe_rows_frame(analysis)

    assert frame.to_dict("records") == [
        {
            "Custom Rank": "1",
            "Ticker": "XLK",
            "Class": "US Sectors",
            "State": "STAGE 2 BULLISH",
            "S": "1.25",
            "F": "0.80",
            "Class Rank": "1",
            "Selected": "YES",
            "Veto": "NO",
        },
        {
            "Custom Rank": "2",
            "Ticker": "XLF",
            "Class": "US Sectors",
            "State": "WARNING",
            "S": "-0.35",
            "F": "-0.20",
            "Class Rank": "5",
            "Selected": "NO",
            "Veto": "NO",
        },
        {
            "Custom Rank": "-",
            "Ticker": "ZZZZ",
            "Class": "MISSING",
            "State": "MISSING",
            "S": "-",
            "F": "-",
            "Class Rank": "-",
            "Selected": "-",
            "Veto": "-",
        },
    ]


def test_summary_counts_frame_sorts_counts_descending():
    frame = custom_universe.summary_counts_frame({"WARNING": 1, "STAGE_2_BULLISH": 2}, "State")

    assert frame.to_dict("records") == [
        {"State": "STAGE 2 BULLISH", "Count": 2},
        {"State": "WARNING", "Count": 1},
    ]
