# B-104 Session Range Tile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a session high/low context tile to the Market state row.

**Architecture:** Reuse the already-fetched SPY OHLCV frame. A pure helper in `src/macro_tiles.py` derives the latest close, high, low, and close-position tone from the latest bar; `app.py` renders it alongside the existing macro context tiles. Missing or malformed OHLCV returns `DATA PENDING` and does not affect scoring.

**Tech Stack:** Python, pandas, pytest, existing Streamlit HTML rendering.

---

### Task 1: Add Session Range Helper Tests

**Files:**
- Modify: `tests/test_macro_tiles.py`
- Test: `tests/test_macro_tiles.py`

- [ ] **Step 1: Write the failing test**

```python
from src.macro_tiles import session_range_tile


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_tiles.py -q`
Expected: FAIL because `session_range_tile` does not exist.

### Task 2: Implement Session Range Helper

**Files:**
- Modify: `src/macro_tiles.py`
- Test: `tests/test_macro_tiles.py`

- [ ] **Step 1: Write minimal implementation**

Add `session_range_tile(frame, symbol)` that reads latest `high`, `low`, and adjusted/regular close, formats close plus `H ... / L ...`, and sets tone to `up`, `down`, or `flat` based on where close sits in the high-low range.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_macro_tiles.py -q`
Expected: all tests pass.

### Task 3: Wire App Rendering and Backlog

**Files:**
- Modify: `app.py`
- Modify: `tests/test_macro_tiles_app_static.py`
- Modify: `docs/BACKLOG.md`
- Test: focused/static QA

- [ ] **Step 1: Add static wiring test**

Assert that `app.py` imports `session_range_tile`, renders `session_tile_html`, passes `ohlcv.get(BENCH["US"])`, and updates status count to `8 indicators`.

- [ ] **Step 2: Implement app wiring**

Render session range before the four macro context tiles.

- [ ] **Step 3: Move B-104 from Ideas to completed backlog**

Add a completed B-104 note with files and behavior, then remove the B-104 bullet from Ideas.

### Task 4: Verify, Commit, Push, and Deploy

Run:

```powershell
python -m pytest tests/test_macro_tiles.py tests/test_macro_tiles_app_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Then commit, push, deploy to Pi, run focused/full Pi tests, restart the service, and smoke test `http://127.0.0.1:8501/?ticker=XLK`.
