# B-153.3 Debrief Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure debrief engine that joins run-journal decisions to forward returns so the app can later measure recommendation quality.

**Architecture:** Keep the engine out of `app.py` and out of network boundaries. `src/run_debrief.py` will accept journal details or a journal database path plus already-loaded OHLCV frames, compute 1w/4w/13w/26w forward outcomes, classify hits by decision action, and summarize action-level hit rates. B-153.4 can later surface these results in Streamlit and reports.

**Tech Stack:** Python dataclasses, pandas, pytest, existing `src.run_journal` and `src.data.close_price` helpers.

---

### Task 1: Pure Forward Outcome Calculations

**Files:**
- Create: `tests/test_run_debrief.py`
- Create: `src/run_debrief.py`

- [x] **Step 1: Write failing tests**

Create tests for `compute_forward_outcomes()` using synthetic daily closes. Cover a BUY that gains after 1w, an EXIT that falls after 1w, and a too-short series that marks the horizon unavailable instead of raising.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_run_debrief.py -q
```

Observed: import failure because `src.run_debrief` did not exist yet.

- [x] **Step 3: Implement minimal forward outcome engine**

Create:

```python
FORWARD_WINDOWS = {"1w": 5, "4w": 20, "13w": 65, "26w": 130}

@dataclass(frozen=True)
class ForwardOutcome:
    horizon: str
    days: int
    start_date: str | None
    end_date: str | None
    start_price: float | None
    end_price: float | None
    forward_return: float | None
    max_drawdown: float | None
    hit: bool | None
    status: str
```

Rules:
- Baseline is the first available close on or after `started_at_utc`.
- End price is the close `days` trading rows after baseline.
- BUY is a hit when forward return is positive.
- EXIT, WATCH, and SELL are hits when forward return is negative or zero.
- Missing ticker, no baseline, or insufficient future data returns unavailable outcomes.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_run_debrief.py -q
```

Observed: `4 passed` for `tests/test_run_debrief.py`.

---

### Task 2: Join Journal Decisions To Outcomes

**Files:**
- Modify: `tests/test_run_debrief.py`
- Modify: `src/run_debrief.py`

- [x] **Step 1: Write failing journal-join test**

Use `append_run()` to create a temporary run with scored snapshots and BLUF decisions. Call `debrief_journal(db_path, ohlcv)` and assert it returns per-decision debrief records with run metadata, score context, action, rationale, and forward outcomes.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_run_debrief.py -q
```

Observed as part of the initial RED cycle before `src/run_debrief.py` existed.

- [x] **Step 3: Implement journal join helpers**

Create:

```python
@dataclass(frozen=True)
class DecisionDebrief:
    run_id: str
    started_at_utc: str
    ticker: str
    action: str
    decision_type: str
    rationale: str | None
    state: str | None
    s_score: float | None
    f_score: float | None
    outcomes: dict[str, ForwardOutcome]
    payload: Mapping[str, Any]
```

Add:
- `debrief_run_details(details, ohlcv, windows=FORWARD_WINDOWS)`
- `debrief_journal(db_path, ohlcv, windows=FORWARD_WINDOWS, limit=50)`

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_run_debrief.py -q
```

Observed: `4 passed` for `tests/test_run_debrief.py`.

---

### Task 3: Summaries And Threshold Review Candidates

**Files:**
- Modify: `tests/test_run_debrief.py`
- Modify: `src/run_debrief.py`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/specs/2026-05-21-b153-run-journal-debrief-engine-design.md`

- [x] **Step 1: Write failing summary tests**

Add tests for:
- `summarize_debriefs(records)` producing count, available count, hit rate, and average forward return per action and horizon.
- `threshold_review_candidates(records, horizon="4w", min_abs_return=0.02)` returning failed recommendations with meaningful adverse forward moves.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_run_debrief.py -q
```

Observed as part of the initial RED cycle before `src/run_debrief.py` existed.

- [x] **Step 3: Implement summaries**

Summaries must skip unavailable outcomes and sort by action then horizon. Threshold candidates must include run id, ticker, action, horizon, forward return, state, S score, F score, and rationale.

- [x] **Step 4: Run focused QA**

Run:

```powershell
python -m pytest tests/test_run_debrief.py tests/test_run_journal.py -q
```

Observed after review fix: `15 passed`.

- [x] **Step 5: Run full QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:
- `python -m pytest -q` -> `173 passed`
- `python -m compileall app.py src scripts` -> exit 0
- `git diff --check` -> exit 0

- [x] **Step 6: Review and commit**

Request code review, fix any findings, then commit:

```powershell
git add src/run_debrief.py tests/test_run_debrief.py docs/BACKLOG.md docs/superpowers/specs/2026-05-21-b153-run-journal-debrief-engine-design.md docs/superpowers/plans/2026-05-21-b153-debrief-engine.md
git commit -m "feat: add run debrief engine"
```

Review found malformed price and zero-baseline gaps; regression tests were added and the focused/full QA gates passed after the fix.
