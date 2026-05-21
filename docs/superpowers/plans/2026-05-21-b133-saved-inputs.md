# B-133 Saved Watchlists And Portfolios Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save, load, and delete named watchlists and portfolios locally after entering a ticker list or uploaded holdings.

**Architecture:** Add a pure `src.saved_inputs` JSON store that persists named `watchlist` and `portfolio` records under `data/saved_inputs.json`. Wire the existing Custom Universe and Portfolio Analyzer sections to save parsed, validated inputs and load them back into the existing read-only analysis paths. The feature does not add broker APIs, cloud sync, scoring recomputation, provider fetches from saved inputs, or state-machine writes.

**Tech Stack:** Python dataclasses, JSON file persistence, existing portfolio/custom-universe parsers, Streamlit, pytest.

---

### Task 1: Pure Local Store

**Files:**
- Create: `src/saved_inputs.py`
- Create: `tests/test_saved_inputs.py`
- Modify: `.gitignore`
- Modify: `.dockerignore`

- [x] **Step 1: Write failing store tests**

Cover saving/replacing watchlists, saving/loading portfolios as `HoldingInput` objects, deleting only the selected kind/name, corrupt JSON fallback, and ignoring generated user data in git/docker contexts.

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_saved_inputs.py -q
```

Expected: FAIL because `src.saved_inputs` does not exist yet.

Observed: FAIL during collection because `src.saved_inputs` did not exist yet.

- [x] **Step 3: Implement store helpers**

Create `src/saved_inputs.py` with:

- `DEFAULT_SAVED_INPUTS_PATH = ROOT / "data" / "saved_inputs.json"`
- `SavedInput` dataclass with `kind`, `name`, `tickers`, `holdings`, and `updated_at`
- `SaveResult` dataclass with `ok`, `message`, and optional `item`
- `load_saved_inputs(path=None) -> list[SavedInput]`
- `save_watchlist(name, tickers, path=None, now=None) -> SaveResult`
- `save_portfolio(name, holdings, path=None, now=None) -> SaveResult`
- `delete_saved_input(kind, name, path=None) -> bool`

The store should normalize names, replace case-insensitive duplicates per kind, normalize/dedupe ticker symbols, preserve portfolio `HoldingInput` fields, write JSON atomically, and fail closed with a clear message instead of raising for bad names or empty inputs.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_saved_inputs.py -q
```

Expected: PASS.

Observed: `python -m pytest tests/test_saved_inputs.py -q` -> `7 passed in 0.24s`.

### Task 2: Streamlit Wiring

**Files:**
- Modify: `app.py`
- Create: `tests/test_saved_inputs_app_static.py`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b133-saved-inputs.md`

- [x] **Step 1: Write failing app static tests**

Require `app.py` to import saved-input helpers, define `SAVED_INPUTS_PATH`, expose save/load/delete controls for both portfolio and custom-universe flows, and keep saved inputs inside existing analysis helpers without new fetch/scoring/state-machine paths.

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_saved_inputs_app_static.py -q
```

Expected: FAIL because app wiring does not exist yet.

Observed: `3 failed`; failures required app saved-input imports/controls and README documentation.

- [x] **Step 3: Wire saved watchlist controls**

In `render_custom_universe_builder()`, load saved `watchlist` records, let the user load/delete a named watchlist, and let them save the currently parsed pasted/uploaded ticker list under a name. Loading a watchlist should set `st.session_state.custom_universe_text` and continue through `parse_custom_universe_text()`.

- [x] **Step 4: Wire saved portfolio controls**

In `render_portfolio_analyzer()`, load saved `portfolio` records, let the user load/delete a named portfolio, and let them save the currently parsed ticker/uploaded holdings under a name. Loading a portfolio should call `_render_portfolio_analysis(PortfolioInputResult(...))` and preserve read-only behavior.

- [x] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_saved_inputs.py tests/test_saved_inputs_app_static.py tests/test_portfolio.py tests/test_custom_universe.py tests/test_custom_universe_app_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:

- `python -m pytest tests/test_saved_inputs.py tests/test_saved_inputs_app_static.py -q` -> `10 passed in 0.23s`
- `python -m pytest tests/test_saved_inputs.py tests/test_saved_inputs_app_static.py tests/test_performance_audit.py -q` -> `16 passed in 0.47s`
- `python -m pytest tests/test_saved_inputs.py tests/test_saved_inputs_app_static.py tests/test_portfolio.py tests/test_custom_universe.py tests/test_custom_universe_app_static.py tests/test_performance_audit.py -q` -> `52 passed in 2.06s`
- `python -m pytest -q` -> `324 passed in 24.20s`
- `python -m compileall app.py src scripts` -> exit 0
- `git diff --check` -> exit 0

- [ ] **Step 6: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `feat: save named watchlists and portfolios`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.
