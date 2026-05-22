# B-155 Macro-Conditioned Debrief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the journaled FRED macro snapshot to summarize matured recommendation outcomes by macro condition.

**Architecture:** Keep the feature inside the pure debrief boundary first: `src/run_debrief.py` reads run metadata already loaded from the SQLite journal and never fetches providers. The dashboard only formats the resulting rows in the existing Debrief lab when macro snapshot metadata is present.

**Tech Stack:** Python dataclasses, pandas, SQLite run journal metadata, Streamlit table rendering, pytest/static tests.

---

### Task 1: Pure Macro Debrief Buckets

**Files:**
- Modify: `tests/test_run_debrief.py`
- Modify: `src/run_debrief.py`

- [x] **Step 1: Write the failing test**

Add a test that appends two journal runs with `metadata["fred_macro_snapshot"]["T10Y2Y"]` set to rising and falling conditions, then calls `debrief_journal()` and `summarize_debriefs_by_macro_condition(records, horizon="1w", series_ids=("T10Y2Y",))`.

Run:

```powershell
python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py -q
```

Observed RED:

```text
ImportError: cannot import name 'summarize_debriefs_by_macro_condition' from 'src.run_debrief'
```

- [x] **Step 2: Implement the minimal pure helper**

Add `run_metadata` to `DecisionDebrief`, pass `run["metadata"]` from `debrief_run_details()`, and implement `summarize_debriefs_by_macro_condition()` with condition labels from `delta` first, then `yoy_pct` fallback.

- [x] **Step 3: Verify the focused debrief tests**

Run:

```powershell
python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py -q
```

Observed GREEN:

```text
9 passed
```

Reviewer follow-up added one regression test to ensure macro metadata with only unmatured forward windows does not produce a dashboard-ready macro bucket:

```powershell
python -m pytest tests/test_run_debrief.py::test_macro_condition_summary_suppresses_unmatured_outcomes -q
```

Observed RED before the fix:

```text
AssertionError: assert [{'action': 'BUY', 'available_count': 0, ...}] == []
```

Observed GREEN after suppressing `available_count == 0` macro buckets:

```text
2 passed
```

### Task 2: Dashboard Surface

**Files:**
- Modify: `app.py`
- Modify: `tests/test_run_debrief_dashboard_static.py`
- Modify: `src/component_docs.py`

- [x] **Step 1: Extend the static dashboard test**

Assert that `app.py` imports and calls `summarize_debriefs_by_macro_condition(records` inside `render_debrief_lab()` and still does not call `fetch_ohlcv()` inside the debrief section.

- [x] **Step 2: Render an optional macro-conditioned table**

Add `_debrief_macro_frame()` and show it in a collapsed `Macro-conditioned outcomes` expander when the table is non-empty.

- [x] **Step 3: Update component docs**

Document that the Debrief lab consumes FRED macro snapshot metadata and has a macro-conditioned state.

### Task 3: Docs, QA, Deploy

**Files:**
- Modify: `docs/BACKLOG.md`
- Modify: `docs/FRED_DATA_OPPORTUNITIES.md`
- Modify: `README.md`
- Modify: `docs/superpowers/handoffs/2026-05-21-backlog-completion-pause.md`

- [x] **Step 1: Document B-155**

Add B-155 to the backlog and explain that it is analysis-only with no scoring, state-machine, alerting, provider fetching, or credential changes.

- [x] **Step 2: Run local QA**

Required commands:

```powershell
python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py tests/test_component_docs.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:

```text
python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py tests/test_component_docs.py -q -> 13 passed
python -m pytest -q -> 365 passed
python -m compileall app.py src scripts -> exit 0
git diff --check -> exit 0
```

- [x] **Step 3: Push and verify on AHADPI5**

Required commands:

```powershell
git push origin backlog-stepwise-qa
ssh -i "$env:USERPROFILE\.ssh\codex_ahadpi_ed25519" -o BatchMode=yes -o ConnectTimeout=8 ahad@10.100.102.18 'cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION && git pull --ff-only origin backlog-stepwise-qa && ./.venv/bin/python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py tests/test_component_docs.py -q && ./.venv/bin/python -m pytest -q && systemctl is-active sector-dashboard && curl -s -o /dev/null -w "%{http_code}" --max-time 8 "http://127.0.0.1:8501/?ticker=XLK"'
```

Observed:

```text
git push origin backlog-stepwise-qa -> a6543c9..298bb90
AHADPI5 git pull --ff-only -> fast-forwarded to 298bb90f4f04949d24a152a679401b53c8707ccd
Pi focused pytest -> 13 passed
Pi full pytest -> 365 passed
systemctl is-active sector-dashboard -> active
dashboard HTTP smoke before restart -> 200
```

The first non-sudo service restart smoke checked too early while systemd was still `activating`:

```text
OLD_PID=604098
NEW_PID=0
system state -> activating
dashboard HTTP smoke -> 000
```

Follow-up status showed systemd completed the restart, and the fresh process served the dashboard:

```text
NEW_PID=617229
git rev-parse HEAD -> 298bb90f4f04949d24a152a679401b53c8707ccd
ActiveState/SubState -> active/running
dashboard HTTP smoke -> 200
```

- [x] **Step 4: Record final evidence**

Update this plan and the handoff with commit SHA, local QA, Pi QA, service status, and dashboard HTTP smoke result.
