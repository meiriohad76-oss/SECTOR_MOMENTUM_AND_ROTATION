# B-116 Sparkline 30wMA Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 30-week moving-average reference line to pick-card sparklines.

**Architecture:** Keep sparkline generation inside `src.visuals.svg_sparkline()`. Compute the latest weekly 30wMA from the loaded daily close history, fold that level into the sparkline y-scale when available, and render a subtle dashed horizontal SVG line before the price path.

**Tech Stack:** pandas weekly resampling, inline SVG, pytest visual-helper tests.

---

### Task 1: 30wMA SVG Reference Line

**Files:**
- Modify: `src/visuals.py`
- Modify: `tests/test_visuals.py`

- [x] **Step 1: Write failing tests**

Add tests requiring:

```python
def test_svg_sparkline_adds_30wma_reference_when_available():
    dates = pd.bdate_range("2024-01-01", periods=220)
    frame = pd.DataFrame({"close": list(range(100, 320))}, index=dates)

    html = svg_sparkline(frame, "#26d65b", style="line")

    assert 'class="spark-ma30"' in html
    assert 'stroke-dasharray="4 3"' in html
```

```python
def test_svg_sparkline_omits_30wma_reference_without_weekly_warmup():
    dates = pd.bdate_range("2024-01-01", periods=40)
    frame = pd.DataFrame({"close": list(range(100, 140))}, index=dates)

    html = svg_sparkline(frame, "#26d65b", style="line")

    assert 'class="spark-ma30"' not in html
```

Review follow-up also added a deterministic scaling regression where the 30wMA sits above the visible 90-day price range and the emitted `y1/y2` coordinates must match the expected scaled level inside the SVG viewBox.

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_visuals.py::test_svg_sparkline_adds_30wma_reference_when_available tests/test_visuals.py::test_svg_sparkline_omits_30wma_reference_without_weekly_warmup -q`

Expected: FAIL because the reference line is not rendered yet.

- [x] **Step 3: Implement helper logic**

In `svg_sparkline()`, compute the latest weekly `close.rolling(30).mean()`. If finite, include it in the min/max scaling and render `<line class="spark-ma30" ... stroke-dasharray="4 3">` before the price path. Keep `style="off"` returning empty markup and preserve existing filled/line behavior.

- [x] **Step 4: Verify focused tests**

Run: `python -m pytest tests/test_visuals.py -q`

Expected: PASS.

### Task 2: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b116-sparkline-30wma-reference.md`

- [x] **Step 1: Update docs and backlog**

Move B-116 from Ideas into implemented status and remove the now-resolved open product question.

- [x] **Step 2: Full local QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [x] **Step 3: Local HTTP smoke**

Run Streamlit temporarily and verify HTTP `200` on `/?ticker=XLK`.

- [x] **Step 4: Review**

Request focused review. Fix Critical/Important feedback and rerun QA.

- [x] **Step 5: Commit, push, and deploy**

Commit as `feat: add 30wma sparkline reference`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
