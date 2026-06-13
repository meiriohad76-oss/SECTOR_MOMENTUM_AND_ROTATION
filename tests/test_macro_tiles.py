from __future__ import annotations

import pandas as pd

from src.macro_tiles import (
    FRED_HEADER_CONTEXT_IDS,
    MACRO_CONTEXT_SYMBOLS,
    fred_macro_snapshot,
    fred_macro_tile_groups,
    macro_tile_rows,
    session_range_tile,
)


def _frame(values):
    return pd.DataFrame(
        {"close": values, "adj_close": values},
        index=pd.date_range("2026-01-01", periods=len(values), freq="D"),
    )


def test_macro_context_symbols_avoid_oil_and_dollar_etf_proxies():
    assert tuple(MACRO_CONTEXT_SYMBOLS) == ("^VIX", "GLD")
    assert tuple(FRED_HEADER_CONTEXT_IDS) == ("DCOILWTICO", "DTWEXBGS")


def test_macro_tile_rows_use_fred_for_wti_and_usd_when_available():
    rows = macro_tile_rows(
        {
            "^VIX": _frame([15.0, 18.0]),
            "GLD": _frame([200.0, 202.0]),
        },
        fred_data={
            "DCOILWTICO": pd.Series([100.0, 112.2], index=pd.date_range("2026-05-01", periods=2)),
            "DTWEXBGS": pd.Series([120.0, 121.5], index=pd.date_range("2026-05-01", periods=2)),
        },
    )

    assert [row["label"] for row in rows] == ["VIX", "Gold ETF proxy", "WTI spot", "USD broad"]
    assert rows[0]["value"] == "18.00"
    assert rows[0]["change"] == "+20.0%"
    assert rows[0]["tone"] == "warn"
    assert rows[0]["sentiment_label"] == "negative"
    assert rows[0]["trend_label"] == "worsening"
    assert rows[0]["gauge_pct"] > 50
    assert rows[1]["subtitle"] == "GLD ETF, tradable gold exposure"
    assert rows[2]["series_id"] == "DCOILWTICO"
    assert rows[2]["value"] == "112.20"
    assert rows[2]["subtitle"] == "2026-05-02"
    assert "spot price from FRED" in rows[2]["tooltip"]
    assert "USO" not in rows[2]["tooltip"]
    assert rows[3]["series_id"] == "DTWEXBGS"
    assert rows[3]["value"] == "121.50"
    assert rows[3]["sentiment_label"] == "negative"
    assert "Broad U.S. Dollar Index" in rows[3]["tooltip"]


def test_macro_tile_rows_show_pending_for_fred_macro_when_fred_missing():
    rows = macro_tile_rows({"^VIX": _frame([15.0]), "GLD": _frame([200.0])}, fred_data={})

    assert [row["label"] for row in rows] == ["VIX", "Gold ETF proxy", "WTI spot", "USD broad"]
    assert rows[2]["value"] == "DATA PENDING"
    assert rows[2]["series_id"] == "DCOILWTICO"
    assert rows[2]["subtitle"] == "DCOILWTICO"
    assert "WTI crude oil spot price" in rows[2]["tooltip"]
    assert rows[3]["value"] == "DATA PENDING"
    assert rows[3]["series_id"] == "DTWEXBGS"


def test_macro_tile_rows_use_data_pending_for_missing_symbol():
    rows = macro_tile_rows({})

    assert rows[0]["value"] == "DATA PENDING"
    assert rows[0]["change"] == "-"
    assert rows[0]["tone"] == "warn"
    assert rows[0]["trend_label"] == "data pending"
    assert rows[0]["sentiment_label"] == "unavailable"
    assert "Volatility" in rows[0]["tooltip"]


def test_session_range_tile_uses_latest_high_low_and_close():
    frame = pd.DataFrame(
        {"high": [450.0, 455.0], "low": [445.0, 449.0], "close": [448.0, 454.0]},
        index=pd.date_range("2026-01-01", periods=2, freq="D"),
    )

    row = session_range_tile(frame, symbol="SPY")

    assert row["label"] == "SPY range"
    assert row["symbol"] == "SPY"
    assert row["value"] == "454.00"
    assert row["change"] == "H 455.00 / L 449.00"
    assert row["tone"] == "up"
    assert row["subtitle"] == "close near high"
    assert row["sentiment_label"] == "positive"
    assert row["trend_label"] == "buying pressure"
    assert row["gauge_pct"] == 83
    assert "latest high-low range" in row["tooltip"]


def test_session_range_tile_uses_data_pending_when_range_missing():
    row = session_range_tile(None, symbol="SPY")

    assert row["value"] == "DATA PENDING"
    assert row["change"] == "-"
    assert row["tone"] == "warn"
    assert row["sentiment_label"] == "unavailable"


def test_session_range_tile_rejects_non_finite_latest_values():
    frame = pd.DataFrame(
        {"high": [455.0], "low": [449.0], "close": [float("nan")]},
        index=pd.date_range("2026-01-01", periods=1, freq="D"),
    )

    row = session_range_tile(frame, symbol="SPY")

    assert row["value"] == "DATA PENDING"
    assert row["change"] == "-"
    assert row["tone"] == "warn"


def test_fred_macro_tile_groups_format_read_only_context():
    fred = {
        "DGS10": pd.Series([4.4, 4.6], index=pd.date_range("2026-05-01", periods=2)),
        "T10Y2Y": pd.Series([0.2, 0.5], index=pd.date_range("2026-05-01", periods=2)),
        "CPIAUCSL": pd.Series(
            [320.0, *([324.0] * 11), 330.0],
            index=pd.date_range("2025-04-01", periods=13, freq="MS"),
        ),
        "WALCL": pd.Series([6700000.0], index=pd.date_range("2026-05-01", periods=1)),
        "CFNAI": pd.Series([-0.1, 0.2], index=pd.date_range("2026-05-01", periods=2)),
        "ICSA": pd.Series([230000.0, 210000.0], index=pd.date_range("2026-05-01", periods=2)),
        "BAMLH0A0HYM2": pd.Series([3.1, 2.8], index=pd.date_range("2026-05-01", periods=2)),
        "DCOILWTICO": pd.Series([100.0, 112.2], index=pd.date_range("2026-05-01", periods=2)),
    }

    groups = fred_macro_tile_groups(fred)

    assert [group["group"] for group in groups] == [
        "Rates",
        "Inflation",
        "Liquidity",
        "Growth",
        "Credit",
        "Commodities",
        "FX",
    ]
    rates = groups[0]["rows"]
    assert rates[0]["label"] == "10Y yield"
    assert rates[0]["value"] == "4.60%"
    assert rates[0]["change"] == "+0.20 pp"
    assert rates[0]["sentiment_label"] == "negative"
    assert rates[0]["trend_label"] == "worsening"
    assert rates[0]["gauge_pct"] > 50
    assert "discount rate" in rates[0]["tooltip"]
    assert rates[1]["label"] == "2s10s"
    assert rates[1]["value"] == "0.50%"
    assert groups[1]["rows"][0]["label"] == "CPI"
    assert groups[1]["rows"][0]["change"] == "+3.1% YoY"
    assert groups[2]["rows"][1]["label"] == "M2"
    assert "broad money supply" in groups[2]["rows"][1]["tooltip"]
    assert groups[2]["rows"][0]["value"] == "6.70T"
    assert groups[3]["rows"][0]["tone"] == "up"
    assert groups[4]["rows"][0]["tone"] == "up"
    assert groups[5]["rows"][0]["value"] == "112.20"
    assert groups[6]["rows"][0]["label"] == "USD broad"
    assert groups[6]["rows"][0]["value"] == "DATA PENDING"


def test_fred_macro_tile_groups_use_data_pending_for_missing_series():
    groups = fred_macro_tile_groups({})

    assert groups[0]["rows"][0]["value"] == "DATA PENDING"
    assert groups[0]["rows"][0]["change"] == "-"
    assert groups[0]["rows"][0]["tone"] == "warn"
    assert groups[0]["rows"][0]["sentiment_label"] == "unavailable"


def test_fred_macro_snapshot_is_clean_journal_metadata():
    fred = {
        "DGS10": pd.Series([4.6], index=pd.to_datetime(["2026-05-21"])),
        "CPIAUCSL": pd.Series([330.0], index=pd.to_datetime(["2026-04-01"])),
    }

    snapshot = fred_macro_snapshot(fred)

    assert snapshot["DGS10"] == {
        "label": "10Y yield",
        "group": "Rates",
        "latest_date": "2026-05-21",
        "latest_value": 4.6,
    }
    assert snapshot["CPIAUCSL"]["group"] == "Inflation"
    assert "T10Y2Y" not in snapshot
