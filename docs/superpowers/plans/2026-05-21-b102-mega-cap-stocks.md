# B-102 Mega-Cap Stocks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mega-cap individual stocks as their own ranked universe class.

**Architecture:** `src/universe.py` remains the source of truth. B-102 introduces `MEGA_CAP_STOCKS` for the explicit backlog tickers, adds a `Mega-Cap Stocks` class, includes those tickers in scored/data-fetch universes, and updates visible copy from ETF-only language to instrument-level language where the whole universe is described.

**Tech Stack:** Python, pytest, existing Streamlit/scoring universe helpers.

---

### Task 1: Add Mega-Cap Stock Universe Coverage Tests

**Files:**
- Modify: `tests/test_universe.py`
- Test: `tests/test_universe.py`

- [ ] **Step 1: Write the failing test**

```python
EXPECTED_MEGA_CAP_STOCKS = ("NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA")


def test_mega_cap_stock_universe_contains_backlog_tickers():
    assert tuple(universe.MEGA_CAP_STOCKS) == EXPECTED_MEGA_CAP_STOCKS
    assert UNIVERSE_BY_CLASS["Mega-Cap Stocks"] == universe.MEGA_CAP_STOCKS


def test_mega_cap_stocks_classify_as_their_own_class():
    for ticker in EXPECTED_MEGA_CAP_STOCKS:
        assert class_of(ticker) == "Mega-Cap Stocks"


def test_product_design_summary_documents_instrument_universe_count():
    text = (ROOT / "docs" / "PRODUCT_DESIGN.md").read_text(encoding="utf-8")

    assert "83+ instruments" in text
    assert "mega-cap stocks" in text
    assert "76+ ETFs" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe.py -q`
Expected: FAIL because `MEGA_CAP_STOCKS` and `Mega-Cap Stocks` do not exist yet and docs still say `76+ ETFs`.

### Task 2: Implement Mega-Cap Stocks in the Universe Source

**Files:**
- Modify: `src/universe.py`
- Test: `tests/test_universe.py`

- [ ] **Step 1: Write minimal implementation**

Add `MEGA_CAP_STOCKS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA"]`.
Add `"Mega-Cap Stocks": MEGA_CAP_STOCKS` to `UNIVERSE_BY_CLASS`.
Add `+ MEGA_CAP_STOCKS` to `SCORED_TICKERS`.
Add `"Mega-Cap Stocks": 3` to `TOP_N`.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_universe.py -q`
Expected: all tests pass.

### Task 3: Update Source-of-Truth Documentation, Live Copy, and Backlog

**Files:**
- Modify: `README.md`
- Modify: `app.py`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/sector-rotation-methodology.md`
- Modify: `docs/BACKLOG.md`
- Test: `tests/test_universe.py`, `git diff --check`

- [ ] **Step 1: Update visible count and class wording**

Change whole-universe copy from `76+ ETFs` to `83+ instruments`, and mention mega-cap stocks.

- [ ] **Step 2: Reconcile the methodology source of truth**

Add a `Mega-cap individual stocks` section containing `NVDA AAPL MSFT AMZN GOOGL META TSLA`, and add `N_mega_cap_stocks = 3` to the top-N target table.

- [ ] **Step 3: Move B-102 from Ideas to completed backlog**

Add a B-102 completed note with files and behavior, then remove the B-102 bullet from Ideas.

### Task 4: Verify, Commit, Push, and Deploy

**Files:**
- All modified files from Tasks 1-3

- [ ] **Step 1: Run local QA**

Run:

```powershell
python -m pytest tests/test_universe.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: tests pass, compileall exits 0, whitespace check exits 0.

- [ ] **Step 2: Commit and push**

Run:

```powershell
git add app.py src/universe.py tests/test_universe.py README.md docs/BACKLOG.md docs/PRODUCT_DESIGN.md docs/sector-rotation-methodology.md docs/superpowers/plans/2026-05-21-b102-mega-cap-stocks.md
git commit -m "feat: add mega-cap stock universe"
git push
```

- [ ] **Step 3: Deploy to Pi and smoke test**

Run the standard Pi pull, `tests/test_universe.py`, full pytest, service restart, and local HTTP smoke.
