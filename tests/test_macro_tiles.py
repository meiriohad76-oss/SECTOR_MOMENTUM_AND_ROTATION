from __future__ import annotations

import pandas as pd

from src.macro_tiles import MACRO_CONTEXT_SYMBOLS, macro_tile_rows


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
