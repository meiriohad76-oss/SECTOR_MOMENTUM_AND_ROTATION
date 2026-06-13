# B-114 State Transition Pulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a brief pulse animation when a ticker has just changed state.

**Architecture:** Reuse the existing persisted transition log returned by `recent_transitions()`. Add a pure helper that identifies tickers with transitions dated today using the state-machine UTC date convention, then wire the helper into alert rows and pick cards through CSS classes only.

**Tech Stack:** Python date handling, Streamlit-rendered HTML, CSS keyframes, pytest pure helper and static app/CSS coverage.

---

### Task 1: Pure Transition Pulse Helper

**Files:**
- Create: `src/transition_pulse.py`
- Create: `tests/test_transition_pulse.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring:

```python
def test_transition_pulse_class_matches_today_transition_case_insensitive():
    transitions = [{"ticker": "XLK", "date": "2026-05-21", "to": "WARNING"}]

    assert transition_pulse_class("xlk", transitions, current_date="2026-05-21") == "pulse-transition"
```

```python
def test_transition_pulse_class_ignores_stale_or_unknown_ticker():
    transitions = [{"ticker": "XLF", "date": "2026-05-20", "to": "EXIT"}]

    assert transition_pulse_class("XLF", transitions, current_date="2026-05-21") == ""
    assert transition_pulse_class("XLK", transitions, current_date="2026-05-21") == ""
```

```python
def test_transition_pulse_tickers_accepts_iso_datetime_dates():
    transitions = [{"ticker": "XLK", "date": "2026-05-21T02:00:00+00:00"}]

    assert transition_pulse_tickers(transitions, current_date="2026-05-21") == {"XLK"}
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_transition_pulse.py -q`

Expected: FAIL because `src.transition_pulse` does not exist.

- [ ] **Step 3: Implement helper**

Implement `transition_pulse_tickers()` and `transition_pulse_class()` in `src/transition_pulse.py`. Default `current_date` to `datetime.now(timezone.utc).date().isoformat()`, compare uppercase tickers, and accept `YYYY-MM-DD` or ISO datetime-like date strings.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_transition_pulse.py -q`

Expected: PASS.

### Task 2: App Wiring And CSS Animation

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Create: `tests/test_transition_pulse_app_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to import `transition_pulse_class`, add `pulse_class = transition_pulse_class(ticker, transitions)` in alert rendering and `pulse_class = transition_pulse_class(tkr, transitions)` in pick rendering, and include `{pulse_class}` in `.alert-row` and `.pick` class strings.

Require `static/style.css` to define `@keyframes state-pulse`, `.pulse-transition`, `.pick.pulse-transition`, `.alert-row.pulse-transition`, and `@media (prefers-reduced-motion: reduce)` disabling the animation.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_transition_pulse_app_static.py -q`

Expected: FAIL because the app and CSS are not wired yet.

- [ ] **Step 3: Implement app/CSS**

Add the helper import, append pulse classes to eligible alert rows and pick cards, add state-color CSS variables for pulse colors, and respect reduced motion.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_transition_pulse.py tests/test_transition_pulse_app_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b114-state-transition-pulse.md`

- [ ] **Step 1: Update docs and backlog**

Move B-114 from Ideas into implemented status. Document that the pulse is visual-only, uses the existing state transition log, and respects reduced-motion settings.

- [ ] **Step 2: Full local QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Local HTTP smoke**

Run Streamlit temporarily and verify HTTP `200` on `/?ticker=XLK`.

- [ ] **Step 4: Review**

Request focused review. Fix Critical/Important feedback and rerun QA.

- [ ] **Step 5: Commit, push, and deploy**

Commit as `feat: add transition pulse animation`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
