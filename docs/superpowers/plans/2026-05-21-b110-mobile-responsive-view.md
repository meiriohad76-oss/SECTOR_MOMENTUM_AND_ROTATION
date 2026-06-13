# B-110 Mobile Responsive View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Streamlit dashboard less cramped on phone-width screens without changing methodology behavior or data flow.

**Architecture:** Keep all scoring/data code untouched. Add small app markup hooks around native Streamlit button-column groups that are known to become narrow on mobile, then extend `static/style.css` responsive rules for header, section heads, tables, alerts, action rows, RRG/drill button blocks, and narrow drill metrics.

**Tech Stack:** Streamlit, CSS media queries, pytest static coverage, existing HTTP smoke deployment.

---

### Task 1: Responsive Markup Hooks

**Files:**
- Modify: `app.py`
- Create: `tests/test_mobile_responsive_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to add:

```python
assert '<div class="drill-buttons-slot"></div>' in app_source
assert '<div class="rrg-class-controls-slot"></div>' in app_source
assert app_source.index('<div class="rrg-class-controls-slot"></div>') < app_source.index("cols = st.columns(len(cls_list))")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_mobile_responsive_static.py -q`

Expected: FAIL because the hooks do not exist yet.

- [ ] **Step 3: Implement hooks**

In `_render_drill_buttons()`, render `_md('<div class="drill-buttons-slot"></div>')` before `st.columns(...)`.

In `render_rrg()`, render `_md('<div class="rrg-class-controls-slot"></div>')` immediately before the class selector `st.columns(len(cls_list))`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_mobile_responsive_static.py -q`

Expected: PASS for app hook checks.

### Task 2: CSS Responsive Polish

**Files:**
- Modify: `static/style.css`
- Modify: `tests/test_mobile_responsive_static.py`

- [ ] **Step 1: Add failing CSS assertions**

Require `static/style.css` to include mobile guards for:

```python
".header {"
".header .meta {"
".section-head {"
".alert-row { grid-template-columns: 16px 64px 1fr; }"
".full-table { overflow-x: auto; -webkit-overflow-scrolling: touch; }"
".full-table table { min-width: 860px; }"
".drill-buttons-slot + div[data-testid=\"stHorizontalBlock\"]"
".rrg-class-controls-slot + div[data-testid=\"stHorizontalBlock\"]"
"@media (max-width: 520px)"
".drill-metrics { grid-template-columns: 1fr; }"
".portfolio-actions .pa-row { grid-template-columns: 1fr; }"
".macro-tile .tile-value { white-space: normal; }"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_mobile_responsive_static.py -q`

Expected: FAIL because the CSS guards are missing.

- [ ] **Step 3: Implement CSS**

Extend the existing `@media (max-width: 760px)` and add `@media (max-width: 520px)`. Keep typography modest and use horizontal scrolling for large data tables instead of squeezing all columns.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_mobile_responsive_static.py tests/test_custom_universe_app_static.py tests/test_backtest_dashboard_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b110-mobile-responsive-view.md`

- [ ] **Step 1: Update docs and backlog**

Move B-110 from Ideas into completed backlog status. Note that B-110 improves responsive layout through CSS/app hooks, while real screenshot/browser QA remains a separate visual validation risk when Playwright or browser tooling is available.

- [ ] **Step 2: Run full local QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: all pass.

- [ ] **Step 3: Local HTTP smoke**

Run a temporary Streamlit server on a free port and verify `curl` returns HTTP `200` for `/?ticker=XLK`.

- [ ] **Step 4: Review**

Request focused review for B-110 mobile responsive changes. Fix Critical/Important feedback and rerun QA.

- [ ] **Step 5: Commit, push, and deploy**

Commit as `feat: improve mobile responsive layout`, push to GitHub, verify remote SHA, pull on Pi, run focused B-110 tests, full Pi pytest, restart service, and HTTP smoke.
