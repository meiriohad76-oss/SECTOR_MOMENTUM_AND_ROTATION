from __future__ import annotations

from src.api_universe import build_universe_analysis_payload


SNAPSHOT_ROWS = [
    {
        "ticker": "XLK",
        "s_score": 1.2,
        "f_score": 0.4,
        "state": "STAGE_2_BULLISH",
        "asset_class": "US Sectors",
        "quadrant": "Leading",
        "momentum_pct": 0.22,
        "cmf21": 0.12,
    },
    {
        "ticker": "XLE",
        "s_score": -0.5,
        "f_score": -0.3,
        "state": "WARNING",
        "asset_class": "US Sectors",
        "quadrant": "Weakening",
        "momentum_pct": -0.04,
        "cmf21": -0.10,
    },
]


def test_build_universe_analysis_returns_ranked_rows_for_known_tickers():
    result = build_universe_analysis_payload(["XLK", "XLE"], SNAPSHOT_ROWS)

    assert result["available_count"] == 2
    assert result["missing_count"] == 0
    rows = result["rows"]
    assert len(rows) == 2
    # XLK has higher s_score, should rank first (descending by default)
    assert rows[0]["ticker"] == "XLK"
    assert rows[0]["missing"] is False
    assert rows[0]["state"] == "STAGE_2_BULLISH"


def test_build_universe_analysis_flags_missing_tickers():
    result = build_universe_analysis_payload(["XLK", "FAKE"], SNAPSHOT_ROWS)

    assert result["available_count"] == 1
    assert result["missing_count"] == 1
    missing_row = next(r for r in result["rows"] if r["ticker"] == "FAKE")
    assert missing_row["missing"] is True


def test_build_universe_analysis_empty_tickers_returns_empty_rows():
    result = build_universe_analysis_payload([], SNAPSHOT_ROWS)

    assert result["available_count"] == 0
    assert result["missing_count"] == 0
    assert result["rows"] == []


def test_build_universe_analysis_empty_snapshot_marks_all_missing():
    result = build_universe_analysis_payload(["XLK", "XLE"], [])

    assert result["available_count"] == 0
    assert result["missing_count"] == 2
    for row in result["rows"]:
        assert row["missing"] is True


def test_build_universe_analysis_returns_class_and_state_counts():
    result = build_universe_analysis_payload(["XLK", "XLE"], SNAPSHOT_ROWS)

    assert "US Sectors" in result["class_counts"]
    assert result["class_counts"]["US Sectors"] == 2
    assert "STAGE_2_BULLISH" in result["state_counts"]
    assert "WARNING" in result["state_counts"]


def test_build_universe_analysis_returns_action_buckets():
    result = build_universe_analysis_payload(["XLK", "XLE"], SNAPSHOT_ROWS)

    assert "bullish" in result["action_tickers"]
    assert "warning" in result["action_tickers"]
    assert "exit" in result["action_tickers"]
    assert "XLK" in result["action_tickers"]["bullish"]
    assert "XLE" in result["action_tickers"]["warning"]
