# B-023 Click-Through Drill-Down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable ticker drill navigation from alert, pick, RRG, and external query-param entry points.

**Architecture:** Put pure navigation logic in `src/navigation.py` so tests can run without Streamlit. Keep `app.py` wiring thin: initialize from query params, call the helper from native buttons, and let existing drill-down rendering consume `st.session_state.drill_ticker`.

**Tech Stack:** Python, Streamlit session state/query params, pytest.

---

## File Structure

- Create `src/navigation.py`: pure helper functions for ticker normalization, query-param initialization, and selecting a drill ticker.
- Create `tests/test_navigation.py`: deterministic tests using simple fake session/query mappings.
- Modify `app.py`: import helper, initialize from `st.query_params`, add alert/pick/RRG drill buttons, and keep the existing selectbox path.
- Modify `docs/BACKLOG.md`: mark B-023 implemented for native/query-param click-through with custom component deferred.
- Modify `README.md`: document `?ticker=XLK` deep links.

---

### Task 1: Navigation Helper

**Files:**
- Create: `tests/test_navigation.py`
- Create: `src/navigation.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from src import navigation


def test_initial_drill_ticker_uses_valid_query_param():
    session = {}
    query = {"ticker": ["xlk"]}

    selected = navigation.initialize_drill_ticker(session, query, ["XLF", "XLK"], default="XLF")

    assert selected == "XLK"
    assert session["drill_ticker"] == "XLK"


def test_initial_drill_ticker_falls_back_when_query_param_unknown():
    session = {}
    query = {"ticker": "NOPE"}

    selected = navigation.initialize_drill_ticker(session, query, ["XLF", "XLK"], default="XLF")

    assert selected == "XLF"
    assert session["drill_ticker"] == "XLF"


def test_select_drill_ticker_updates_session_and_query_params():
    session = {"drill_ticker": "XLF"}
    query = {}

    changed = navigation.select_drill_ticker(session, query, "xlk", ["XLF", "XLK"])

    assert changed is True
    assert session["drill_ticker"] == "XLK"
    assert query["ticker"] == "XLK"


def test_select_drill_ticker_rejects_malformed_or_unknown_values():
    session = {"drill_ticker": "XLF"}
    query = {"ticker": "XLF"}

    changed = navigation.select_drill_ticker(session, query, "not a ticker", ["XLF", "XLK"])

    assert changed is False
    assert session["drill_ticker"] == "XLF"
    assert query["ticker"] == "XLF"
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_navigation.py -q`

Expected: import failure because `src/navigation.py` does not exist.

- [ ] **Step 3: Implement minimal helper**

```python
from __future__ import annotations

import re
from collections.abc import MutableMapping, Sequence


_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_ticker_param(value) -> str | None:
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if _TICKER_RE.match(text) else None


def _valid_tickers(tickers: Sequence[str]) -> set[str]:
    return {str(ticker).upper() for ticker in tickers}


def initialize_drill_ticker(
    session_state: MutableMapping,
    query_params: MutableMapping,
    tickers: Sequence[str],
    default: str = "XLK",
) -> str:
    valid = _valid_tickers(tickers)
    current = normalize_ticker_param(session_state.get("drill_ticker"))
    requested = normalize_ticker_param(query_params.get("ticker"))
    fallback = normalize_ticker_param(default)
    selected = requested if requested in valid else current if current in valid else fallback
    if selected not in valid:
        selected = sorted(valid)[0] if valid else fallback
    session_state["drill_ticker"] = selected
    return selected


def select_drill_ticker(
    session_state: MutableMapping,
    query_params: MutableMapping,
    ticker,
    tickers: Sequence[str],
) -> bool:
    normalized = normalize_ticker_param(ticker)
    if normalized not in _valid_tickers(tickers):
        return False
    changed = session_state.get("drill_ticker") != normalized
    session_state["drill_ticker"] = normalized
    query_params["ticker"] = normalized
    return changed
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_navigation.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit helper**

```bash
git add src/navigation.py tests/test_navigation.py
git commit -m "feat: add drill navigation helpers"
```

---

### Task 2: Streamlit Wiring

**Files:**
- Modify: `app.py`
- Test: `tests/test_navigation.py`

- [ ] **Step 1: Add import and initialize from query params**

Add:

```python
from src.navigation import initialize_drill_ticker, select_drill_ticker
```

After `scored` is available, call:

```python
initialize_drill_ticker(st.session_state, st.query_params, sorted(scored.index.tolist()))
```

- [ ] **Step 2: Add a local navigation wrapper**

Add near render helpers:

```python
def _go_to_drill(ticker: str) -> None:
    if select_drill_ticker(st.session_state, st.query_params, ticker, sorted(scored.index.tolist())):
        st.rerun()
```

- [ ] **Step 3: Wire alert buttons**

In `render_alerts()`, after `_md(html)`, add columns/buttons for transition tickers:

```python
drill_tickers = [r.get("ticker") for r in transitions[:8] if r.get("ticker") in scored.index]
if drill_tickers:
    cols = st.columns(min(len(drill_tickers), 4))
    for idx, ticker in enumerate(drill_tickers):
        with cols[idx % len(cols)]:
            if st.button(f"DRILL {ticker}", key=f"alert_drill_{idx}_{ticker}"):
                _go_to_drill(ticker)
```

- [ ] **Step 4: Wire pick buttons**

In `render_picks()`, after `_md(html)`, add:

```python
pick_tickers = selected_picks.index.tolist()
cols = st.columns(min(len(pick_tickers), 4))
for idx, ticker in enumerate(pick_tickers):
    with cols[idx % len(cols)]:
        if st.button(f"DRILL {ticker}", key=f"pick_drill_{idx}_{ticker}"):
            _go_to_drill(ticker)
```

- [ ] **Step 5: Wire RRG quadrant buttons**

In the right-column quadrant loop, after the quadrant card HTML, add:

```python
for ticker in tickers[:8]:
    if st.button(f"DRILL {ticker}", key=f"rrg_drill_{q}_{ticker}"):
        _go_to_drill(ticker)
```

- [ ] **Step 6: Keep selectbox query params synced**

Replace the direct assignment in `render_drill()`:

```python
if new_sel != sel:
    _go_to_drill(new_sel)
```

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_navigation.py -q`

Expected: all tests pass.

---

### Task 3: Docs, QA, Review, Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update README**

Add a short note under state transition alerts:

```markdown
Dashboard deep links support `?ticker=XLK`; the app opens with that ticker selected in the per-ticker drill-down.
```

- [ ] **Step 2: Update backlog**

Replace the B-023 entry with an implemented/key detail:

```markdown
### B-023 - Click-through from cards/alerts/RRG to drill-down - IMPLEMENTED
**Status:** Native Streamlit drill buttons and `?ticker=...` deep links are implemented. Full-card HTML clicks and Plotly dot-click capture remain deferred custom-component work.
```

- [ ] **Step 3: Run verification**

Run:

```bash
python -m pytest tests/test_navigation.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected:

- focused tests pass
- full suite passes
- compileall exits 0
- diff check exits 0, allowing existing CRLF warnings

- [ ] **Step 4: Request review**

Ask a reviewer to inspect uncommitted changes for deterministic tests, Streamlit state/query-param safety, and UI blast radius.

- [ ] **Step 5: Commit implementation**

```bash
git add app.py src/navigation.py tests/test_navigation.py README.md docs/BACKLOG.md docs/superpowers/specs/2026-05-20-b023-click-through-drilldown-design.md docs/superpowers/plans/2026-05-20-b023-click-through-drilldown.md
git commit -m "feat: add drill-down navigation"
```
