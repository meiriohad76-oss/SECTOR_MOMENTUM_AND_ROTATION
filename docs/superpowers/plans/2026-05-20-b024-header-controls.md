# B-024 Header Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put working refresh and theme controls in the visible header area instead of after the footer.

**Architecture:** Add a tiny pure helper module for control state transitions, then keep Streamlit wiring in `app.py`. Render native Streamlit buttons immediately after the header and style their wrapper as a fixed top-right control group in CSS.

**Tech Stack:** Python, Streamlit native buttons, CSS, pytest.

---

## File Structure

- Create `src/controls.py`: pure helpers for theme toggling and cache refresh.
- Create `tests/test_controls.py`: deterministic unit tests for helper behavior.
- Modify `app.py`: import helpers, add `render_header_controls()`, call it after `render_header()`, remove bottom controls.
- Modify `static/style.css`: add fixed header-control styles targeting a wrapper class around the Streamlit buttons.
- Modify `docs/BACKLOG.md`: mark B-024 implemented and note custom component deferred.

---

### Task 1: Control Helpers

**Files:**
- Create: `tests/test_controls.py`
- Create: `src/controls.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from src import controls


class FakeCache:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


def test_toggle_theme_flips_dark_to_light():
    session = {"theme": "dark"}

    assert controls.toggle_theme(session) == "light"
    assert session["theme"] == "light"


def test_toggle_theme_flips_light_to_dark():
    session = {"theme": "light"}

    assert controls.toggle_theme(session) == "dark"
    assert session["theme"] == "dark"


def test_toggle_theme_defaults_unknown_theme_to_dark():
    session = {"theme": "solarized"}

    assert controls.toggle_theme(session) == "dark"
    assert session["theme"] == "dark"


def test_refresh_market_data_clears_cache():
    cache = FakeCache()

    assert controls.refresh_market_data(cache) is True
    assert cache.cleared is True
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_controls.py -q`

Expected: import failure because `src/controls.py` does not exist.

- [ ] **Step 3: Implement minimal helper**

```python
from __future__ import annotations

from collections.abc import MutableMapping


def toggle_theme(session_state: MutableMapping) -> str:
    current = session_state.get("theme")
    next_theme = "light" if current == "dark" else "dark"
    session_state["theme"] = next_theme
    return next_theme


def refresh_market_data(cache) -> bool:
    cache.clear()
    return True
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_controls.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit helper**

```bash
git add src/controls.py tests/test_controls.py
git commit -m "feat: add header control helpers"
```

---

### Task 2: Header Control Wiring

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Test: `tests/test_controls.py`

- [ ] **Step 1: Import helpers**

Add to `app.py` imports:

```python
from src.controls import refresh_market_data, toggle_theme
```

- [ ] **Step 2: Add `render_header_controls()`**

Add near render helpers:

```python
def render_header_controls():
    _md('<div class="header-controls-slot"></div>')
    ctrl_col1, ctrl_col2 = st.columns(2)
    with ctrl_col1:
        if st.button("↻", key="refresh_btn", help="Refresh data", use_container_width=True):
            refresh_market_data(_load_data)
            st.rerun()
    with ctrl_col2:
        icon = "☀" if st.session_state.theme == "dark" else "☾"
        if st.button(icon, key="theme_btn", help="Toggle theme", use_container_width=True):
            toggle_theme(st.session_state)
            st.rerun()
```

- [ ] **Step 3: Move control render call**

In compose section:

```python
render_header()
render_header_controls()
```

Remove the bottom block:

```python
# floating refresh / theme controls ...
ctrl_col1, ctrl_col2, _ = st.columns([1, 1, 18])
...
```

- [ ] **Step 4: Add CSS**

Append to `static/style.css`:

```css
/* ---------- Header native controls ---------- */
.header-controls-slot + div[data-testid="stHorizontalBlock"] {
  position: fixed;
  top: 12px;
  right: 28px;
  width: 78px;
  z-index: 1000;
  gap: 8px !important;
}
.header-controls-slot + div[data-testid="stHorizontalBlock"] [data-testid="column"] {
  width: 34px !important;
  flex: 0 0 34px !important;
}
.header-controls-slot + div[data-testid="stHorizontalBlock"] button {
  width: 34px;
  height: 34px;
  min-height: 34px;
  padding: 0;
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--panel);
  color: var(--fg-dim);
  font-family: var(--font-mono);
}
.header-controls-slot + div[data-testid="stHorizontalBlock"] button:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--panel-hover);
}
```

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_controls.py -q`

Expected: all tests pass.

---

### Task 3: Docs, QA, Review, Commit

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update backlog**

Replace B-024 with:

```markdown
### B-024 · Floating refresh / theme buttons in the header — IMPLEMENTED
**Status:** Native Streamlit refresh/theme controls render immediately after the header and are fixed top-right via CSS.
**Deferred:** custom component bridge and animated fetching state remain future polish.
```

- [ ] **Step 2: Run verification**

Run:

```bash
python -m pytest tests/test_controls.py -q
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

Ask a reviewer to inspect the helper, Streamlit button placement, CSS selector blast radius, docs, and test coverage.

- [ ] **Step 4: Smoke local app**

Run Streamlit on an available local port and verify an HTTP 200 response:

```powershell
python -m streamlit run app.py --server.headless=true --server.port=8501 --server.address=127.0.0.1
```

- [ ] **Step 5: Commit implementation**

```bash
git add app.py static/style.css src/controls.py tests/test_controls.py docs/BACKLOG.md docs/superpowers/specs/2026-05-20-b024-header-controls-design.md docs/superpowers/plans/2026-05-20-b024-header-controls.md
git commit -m "feat: move controls into header"
```
