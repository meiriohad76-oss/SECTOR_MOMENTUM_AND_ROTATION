# B-026 Empty And Loading States Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dashboard-native no-picks and loading states.

**Architecture:** Add pure UI-state helpers in `src/ui_states.py`, render the empty and loading states from `app.py`, and style both in `static/style.css`. Keep the data pipeline unchanged.

**Tech Stack:** Python, Streamlit, pandas, CSS, pytest.

---

## File Structure

- Create `src/ui_states.py`: defensive basket constants, row builder, and skeleton slot helper.
- Create `tests/test_ui_states.py`: deterministic helper tests.
- Create `tests/test_empty_loading_states_static.py`: static app/CSS wiring tests.
- Modify `app.py`: replace spinner wrappers with a skeleton placeholder and replace empty picks row with the defensive basket panel.
- Modify `static/style.css`: add empty-state, defensive-card, and skeleton styles.
- Modify `docs/BACKLOG.md`: mark B-026 implemented and document deferred polish.

---

### Task 1: Pure UI State Helpers

**Files:**
- Create: `tests/test_ui_states.py`
- Create: `src/ui_states.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import pandas as pd

from src.ui_states import DEFENSIVE_BASKET, defensive_basket_rows, loading_skeleton_slots


def test_defensive_basket_order_is_tlt_gld_bil():
    assert DEFENSIVE_BASKET == ("TLT", "GLD", "BIL")


def test_defensive_basket_rows_use_scored_snapshot_when_available():
    scored = pd.DataFrame(
        {
            "state": ["HOLD", "STAGE_2_BULLISH", "STAGE_1_BASING"],
            "S_score": [0.25, 0.72, -0.05],
            "F_score": [0.10, 0.40, 0.00],
        },
        index=["BIL", "TLT", "GLD"],
    )

    rows = defensive_basket_rows(scored)

    assert [row["ticker"] for row in rows] == ["TLT", "GLD", "BIL"]
    assert rows[0]["state"] == "STAGE_2_BULLISH"
    assert rows[0]["s_score"] == 0.72
    assert rows[0]["available"] is True
    assert rows[1]["role"] == "Gold hedge"
    assert rows[2]["role"] == "Cash / T-bill proxy"


def test_defensive_basket_rows_mark_missing_ticker_as_pending():
    scored = pd.DataFrame(
        {"state": ["HOLD"], "S_score": [0.25], "F_score": [0.10]},
        index=["TLT"],
    )

    rows = defensive_basket_rows(scored)
    missing = [row for row in rows if row["ticker"] == "GLD"][0]

    assert missing["available"] is False
    assert missing["state"] == "DATA_PENDING"
    assert missing["s_score"] is None
    assert missing["f_score"] is None


def test_loading_skeleton_slots_clamps_to_non_negative_count():
    assert loading_skeleton_slots(3) == (0, 1, 2)
    assert loading_skeleton_slots(0) == ()
    assert loading_skeleton_slots(-2) == ()
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_ui_states.py -q`

Expected: import failure because `src/ui_states.py` does not exist.

- [ ] **Step 3: Implement helpers**

```python
from __future__ import annotations

from typing import Any

import pandas as pd


DEFENSIVE_BASKET = ("TLT", "GLD", "BIL")

DEFENSIVE_ROLES = {
    "TLT": "Long Treasury hedge",
    "GLD": "Gold hedge",
    "BIL": "Cash / T-bill proxy",
}

DEFENSIVE_NOTES = {
    "TLT": "Duration hedge for equity drawdown regimes.",
    "GLD": "Real-asset hedge when risk appetite fades.",
    "BIL": "T-bill proxy for capital preservation.",
}


def _first_row(scored_df: pd.DataFrame, ticker: str) -> pd.Series | None:
    if ticker not in scored_df.index:
        return None
    row = scored_df.loc[ticker]
    if isinstance(row, pd.DataFrame):
        return row.iloc[0]
    return row


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def defensive_basket_rows(scored_df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ticker in DEFENSIVE_BASKET:
        row = _first_row(scored_df, ticker)
        available = row is not None
        rows.append(
            {
                "ticker": ticker,
                "role": DEFENSIVE_ROLES[ticker],
                "note": DEFENSIVE_NOTES[ticker],
                "available": available,
                "state": str(row.get("state")) if available else "DATA_PENDING",
                "s_score": _optional_float(row.get("S_score")) if available else None,
                "f_score": _optional_float(row.get("F_score")) if available else None,
            }
        )
    return rows


def loading_skeleton_slots(count: int = 4) -> tuple[int, ...]:
    return tuple(range(max(0, int(count))))
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_ui_states.py -q`

Expected: tests pass.

- [ ] **Step 5: Commit helper**

```bash
git add src/ui_states.py tests/test_ui_states.py
git commit -m "feat: add empty state helpers"
```

---

### Task 2: App Wiring And CSS

**Files:**
- Create: `tests/test_empty_loading_states_static.py`
- Modify: `app.py`
- Modify: `static/style.css`

- [ ] **Step 1: Write failing static tests**

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_loading_state_replaces_streamlit_spinners():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_loading_state(" in app_source
    assert "loading_placeholder = st.empty()" in app_source
    assert "loading_placeholder.empty()" in app_source
    assert "st.spinner(" not in app_source


def test_empty_picks_render_defensive_basket():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "defensive_basket_rows(scored)" in app_source
    assert "No picks meet the gates" in app_source
    assert "TLT / GLD / BIL" in app_source
    assert '_render_drill_buttons("defensive_drill"' in app_source


def test_empty_and_loading_css_exists():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".empty-state" in css
    assert ".defensive-card" in css
    assert ".loading-state" in css
    assert ".skeleton-card" in css
    assert ".skeleton-line" in css
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_empty_loading_states_static.py -q`

Expected: fails because the app still uses `st.spinner()` and has no new state CSS.

- [ ] **Step 3: Wire loading placeholder**

Add `loading_skeleton_slots` import. Define `render_loading_state(placeholder, label, card_count=4)` near `_md()`. Replace the two `with st.spinner(...)` blocks with:

```python
loading_placeholder = st.empty()
render_loading_state(loading_placeholder, "Loading market data", card_count=4)
try:
    ohlcv = _load_data("3y")
    render_loading_state(loading_placeholder, "Computing indicators", card_count=4)
    indicators_df = compute_all_indicators(ohlcv, bench_ticker, bil_ticker)
    flow_df = compute_flow_signals(ohlcv)
    flow_z = flow_composite_z(flow_df)
    _fred_data = _load_fred()
    regime = assess_regime(ohlcv[bench_ticker], ohlcv.get("^TNX"), ohlcv.get("^IRX"), fred_cache=_fred_data)
    scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
    scored = apply_state_machine(scored)
finally:
    loading_placeholder.empty()
```

- [ ] **Step 4: Wire empty state**

Import `defensive_basket_rows`. In `render_picks()`, replace the existing empty branch with defensive basket cards built from `defensive_basket_rows(scored)`, then render drill buttons for available defensive tickers.

- [ ] **Step 5: Add CSS**

Add rules for:

```css
.empty-state
.empty-state-copy
.defensive-card
.defensive-card.unavailable
.loading-state
.loading-copy
.skeleton-grid
.skeleton-card
.skeleton-line
```

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_ui_states.py tests/test_empty_loading_states_static.py -q`

Expected: tests pass.

- [ ] **Step 7: Commit app wiring**

```bash
git add app.py static/style.css tests/test_empty_loading_states_static.py
git commit -m "feat: add empty and loading states"
```

---

### Task 3: Docs, QA, Review, Commit

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update backlog**

Replace B-026 with an implemented status, list files, behavior, and deferred future polish.

- [ ] **Step 2: Run verification**

Run:

```bash
python -m pytest tests/test_ui_states.py tests/test_empty_loading_states_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected:

- focused tests pass
- full suite passes
- compileall exits 0
- diff check exits 0, allowing existing CRLF warnings

- [ ] **Step 3: Request review**

Ask a reviewer to inspect no-picks behavior, loading placeholder lifecycle, CSS blast radius, and tests.

- [ ] **Step 4: Smoke local app**

Verify local Streamlit returns HTTP 200 on `http://127.0.0.1:8501/?ticker=XLK`, or start a server if needed.

- [ ] **Step 5: Commit docs**

```bash
git add docs/BACKLOG.md
git commit -m "docs: mark b026 empty loading states"
```

