# B-103 Macro Context Tiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VIX, gold, oil, and USD context tiles to the market-state header.

**Architecture:** Macro context symbols are fetched for display only and are not added to the ranked universe. A new pure helper in `src/macro_tiles.py` converts OHLCV frames into compact tile rows; `app.py` fetches the context symbols, renders the rows inside the existing status section, and keeps missing data as `DATA PENDING` instead of failing the dashboard.

**Tech Stack:** Python, pandas, pytest, existing Streamlit HTML rendering.

---

### Task 1: Add Macro Tile Helper Tests

**Files:**
- Create: `src/macro_tiles.py`
- Create: `tests/test_macro_tiles.py`
- Test: `tests/test_macro_tiles.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_tiles.py -q`
Expected: FAIL because `src.macro_tiles` does not exist.

### Task 2: Implement Pure Macro Tile Rows

**Files:**
- Create: `src/macro_tiles.py`
- Test: `tests/test_macro_tiles.py`

- [ ] **Step 1: Write minimal implementation**

Define `MACRO_CONTEXT_SYMBOLS = ("^VIX", "GLD", "USO", "UUP")` and `macro_tile_rows(ohlcv)` that returns four dictionaries with labels, symbols, values, percent changes, tones, and subtitles.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_macro_tiles.py -q`
Expected: all tests pass.

### Task 3: Wire App Fetch and Status Rendering

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Test: `tests/test_macro_tiles_app_static.py`

- [ ] **Step 1: Add static wiring test**

Assert that `app.py` imports `MACRO_CONTEXT_SYMBOLS` and `macro_tile_rows`, fetches `list(MACRO_CONTEXT_SYMBOLS)`, renders `macro_tiles_html`, updates the status count to `7 indicators`, and that CSS supports a four-column status row.

- [ ] **Step 2: Implement app wiring**

Append context symbols to `_load_data()` fetches, filter the scoring payload back to `ALL_TICKERS` before `compute_all_indicators()` and `compute_flow_signals()`, render the four macro tiles in `render_status()`, and change the status-row grid to four columns.

### Task 4: Update Backlog and Verify

**Files:**
- Modify: `docs/BACKLOG.md`
- Test: local QA suite

- [ ] **Step 1: Move B-103 from Ideas to completed backlog**

Add a completed B-103 note with files and behavior, then remove the B-103 bullet from Ideas.

- [ ] **Step 2: Run local QA**

Run:

```powershell
python -m pytest tests/test_macro_tiles.py tests/test_macro_tiles_app_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: tests pass, compileall exits 0, whitespace check exits 0.

- [ ] **Step 3: Commit, push, deploy, and smoke test**

Use the standard branch commit, `git push`, Pi pull, focused/full Pi tests, service restart, and local HTTP smoke.
