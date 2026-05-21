# B-113 Table Hover Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hover preview to full matrix table rows showing a compact RRG dot context.

**Architecture:** Keep the full table server-rendered HTML. Add a focused `src.table_preview` helper that converts a scored row into safe preview markup and normalized mini-RRG dot coordinates. Wire `app.py` to place the preview inside the ticker cell and use CSS to reveal it on row hover.

**Tech Stack:** Python HTML escaping, pandas-compatible row access, CSS hover states, pytest pure helper and static app/CSS coverage.

---

### Task 1: Pure Preview Helper

**Files:**
- Create: `src/table_preview.py`
- Create: `tests/test_table_preview.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring:

```python
def test_rrg_preview_position_centers_and_clamps_values():
    assert rrg_preview_position(100, 100) == (50.0, 50.0)
    assert rrg_preview_position(140, 60) == (100.0, 0.0)
```

```python
def test_table_row_rrg_preview_html_escapes_text_and_includes_metrics():
    row = {
        "state": "STAGE_2_BULLISH",
        "rrg_quadrant": "Leading",
        "rs_ratio": 104.25,
        "rs_momentum": 97.5,
        "S_score": 1.234,
        "F_score": -0.25,
    }

    html = table_row_rrg_preview_html('XLK"<', row)

    assert "XLK&quot;&lt;" in html
    assert 'class="row-preview"' in html
    assert 'class="mini-rrg"' in html
    assert "--rrg-x:60.6%;" in html
    assert "--rrg-y:43.8%;" in html
    assert "RS 104.2" in html
    assert "MOM 97.5" in html
    assert "S +1.23" in html
    assert "F -0.25" in html
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_table_preview.py -q`

Expected: FAIL because `src.table_preview` does not exist.

- [ ] **Step 3: Implement helper**

Implement `rrg_preview_position()` and `table_row_rrg_preview_html()` in `src/table_preview.py`. Clamp coordinates to `0..100`, default missing/non-finite RRG values to `100`, escape user-visible text, and keep the helper independent from Streamlit.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_table_preview.py -q`

Expected: PASS.

### Task 2: Full Table Wiring And CSS

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Create: `tests/test_table_hover_preview_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to import `table_row_rrg_preview_html`, compute `preview_html = table_row_rrg_preview_html(tkr, r)` inside the full table loop, and place `{preview_html}` inside `<td class="t table-ticker">`.

Require `static/style.css` to define `.table-ticker`, `.row-preview`, `.mini-rrg`, `.mini-rrg-dot`, `.full-table tr:hover .row-preview`, and a mobile rule hiding `.row-preview`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_table_hover_preview_static.py -q`

Expected: FAIL because the app and CSS are not wired yet.

- [ ] **Step 3: Implement app/CSS**

Use the helper in `render_full_table()` and add CSS that positions the preview absolutely without changing table row height. Disable the hover card under `760px`.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_table_preview.py tests/test_table_hover_preview_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b113-table-hover-preview.md`

- [ ] **Step 1: Update docs and backlog**

Move B-113 from Ideas into implemented status. Document that the preview is CSS-only, desktop-hover oriented, and uses already-computed RRG fields.

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

Commit as `feat: add table hover previews`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
