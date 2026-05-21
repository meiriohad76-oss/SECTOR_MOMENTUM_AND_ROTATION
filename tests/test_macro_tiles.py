from __future__ import annotations

import pandas as pd

from src.macro_tiles import MACRO_CONTEXT_SYMBOLS, macro_tile_rows, session_range_tile


def _frame(values):
    return pd.DataFrame(
        {"close": values, "adj_close": values},
        index=pd.date_range("2026-01-01", periods=len(values), freq="D"),
    )


def test_macro_context_symbols_are_display_only_market_proxies():
    assert tuple(MACRO_CONTEXT_SYMBOLS) == ("^VIX", "GLD", "USO", "UUP")


def test_macro_tile_rows_compute_last_value_and_percent_change():
    rows = macro_tile_rows(
        {
            "^VIX": _frame([15.0, 18.0]),
            "GLD": _frame([200.0, 202.0]),
            "USO": _frame([70.0, 68.6]),
            "UUP": _frame([28.0, 28.0]),
        }
    )

    assert [row["label"] for row in rows] == ["VIX", "Gold", "Oil", "USD"]
    assert rows[0]["value"] == "18.00"
    assert rows[0]["change"] == "+20.0%"
    assert rows[0]["tone"] == "warn"
    assert rows[2]["change"] == "-2.0%"
    assert rows[2]["tone"] == "down"
    assert rows[3]["tone"] == "flat"


def test_macro_tile_rows_use_data_pending_for_missing_symbol():
    rows = macro_tile_rows({})

    assert rows[0]["value"] == "DATA PENDING"
    assert rows[0]["change"] == "-"
    assert rows[0]["tone"] == "warn"


def test_session_range_tile_uses_latest_high_low_and_close():
    frame = pd.DataFrame(
        {"high": [450.0, 455.0], "low": [445.0, 449.0], "close": [448.0, 454.0]},
        index=pd.date_range("2026-01-01", periods=2, freq="D"),
    )

    row = session_range_tile(frame, symbol="SPY")

    assert row["label"] == "Session range"
    assert row["symbol"] == "SPY"
    assert row["value"] == "454.00"
    assert row["change"] == "H 455.00 / L 449.00"
    assert row["tone"] == "up"
    assert row["subtitle"] == "near high"


def test_session_range_tile_uses_data_pending_when_range_missing():
    row = session_range_tile(None, symbol="SPY")

    assert row["value"] == "DATA PENDING"
    assert row["change"] == "-"
    assert row["tone"] == "warn"


def test_session_range_tile_rejects_non_finite_latest_values():
    frame = pd.DataFrame(
        {"high": [455.0], "low": [449.0], "close": [float("nan")]},
        index=pd.date_range("2026-01-01", periods=1, freq="D"),
    )

    row = session_range_tile(frame, symbol="SPY")

    assert row["value"] == "DATA PENDING"
    assert row["change"] == "-"
    assert row["tone"] == "warn"
