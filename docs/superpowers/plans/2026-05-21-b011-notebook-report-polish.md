# B-011 Notebook And Report Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the B-011 report-polish follow-up by producing a richer generated methodology report and a checked-in notebook-style reproducibility guide for inspecting backtest artifacts.

**Architecture:** Keep the expensive historical simulation in `scripts/run_backtest.py`. Add a pure Markdown formatter in `src/backtest.py` for the full methodology report, have the runner write `docs/backtest_methodology_report.md` and include its hash in metadata, and add `notebooks/backtest_methodology_report.ipynb` as a lightweight guide that reads existing artifacts rather than rerunning the backtest.

**Tech Stack:** Python, pandas, JSON notebook format, pytest.

---

## File Structure

- Modify `tests/test_backtest.py`: add a pure formatter test for the full methodology report.
- Modify `src/backtest.py`: add `format_methodology_report()`.
- Modify `tests/test_run_backtest_script.py`: assert the runner writes and hashes the full report artifact.
- Modify `scripts/run_backtest.py`: add `METHODOLOGY_REPORT_PATH`, write the full report, and include `methodology_report_sha256` in metadata.
- Create `notebooks/backtest_methodology_report.ipynb`: reproducibility guide that loads existing artifacts.
- Create `tests/test_backtest_notebook_static.py`: validate notebook JSON and artifact references.
- Modify `README.md` and `docs/BACKLOG.md`: document the full report and notebook guide.

---

### Task 1: Full Methodology Report Formatter

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing test**

Add a test that calls `backtest.format_methodology_report()` with existing metrics, benchmark metrics, gates, window metrics, and simulation summary. Assert the output contains:

- `# Historical Methodology Backtest Report`
- `## Executive Summary`
- `## Methodology Under Test`
- `## Evidence Tables`
- `## Acceptance Gates`
- `## Limitations And Next Work`
- a statement that results are research evidence, not investment advice.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_format_methodology_report_includes_research_narrative_sections -q
```

Expected: fails because `format_methodology_report()` does not exist.

- [ ] **Step 3: Implement formatter**

Add `format_methodology_report()` in `src/backtest.py`. It should reuse existing table helpers, include the simulation summary, include window metrics, include gate details, and list limitations:

- provider-backed historical flow is neutral until as-of provider snapshots exist
- manual artifacts are evidence, not a live-edge claim
- notebook/report does not replace deterministic tests

- [ ] **Step 4: Run GREEN**

Run the same focused test. Expected: pass.

---

### Task 2: Runner Full Report Artifact

**Files:**
- Modify: `tests/test_run_backtest_script.py`
- Modify: `scripts/run_backtest.py`

- [ ] **Step 1: Write failing runner assertions**

Update path test to include `METHODOLOGY_REPORT_PATH == ROOT / "docs" / "backtest_methodology_report.md"`.

Patch that path in runner tests. In the successful runner test, assert:

- full report path exists
- report contains `Historical Methodology Backtest Report`
- metadata includes `methodology_report_sha256`

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_run_backtest_artifact_paths_are_repo_root_anchored tests/test_run_backtest_script.py::test_run_backtest_fetches_benchmarks_and_writes_rich_report -q
```

Expected: fails because the path and artifact are not implemented.

- [ ] **Step 3: Implement runner artifact**

Add `METHODOLOGY_REPORT_PATH`, generate `methodology_report = backtest.format_methodology_report(...)`, write it atomically with existing artifacts, and add its SHA-256 to metadata.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
```

Expected: pass.

---

### Task 3: Notebook Guide

**Files:**
- Create: `notebooks/backtest_methodology_report.ipynb`
- Create: `tests/test_backtest_notebook_static.py`

- [ ] **Step 1: Write failing static tests**

Create tests that:

- parse the notebook as JSON
- assert `nbformat == 4`
- assert it references `docs/backtest_report.md`, `docs/backtest_methodology_report.md`, `docs/backtest_equity.csv`, and `docs/backtest_metadata.json`
- assert it contains `python scripts/run_backtest.py --live-smoke`
- assert it does not contain `MASSIVE_API_KEY`

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest_notebook_static.py -q
```

Expected: fails because the notebook does not exist.

- [ ] **Step 3: Add notebook**

Create a minimal valid notebook with Markdown and code cells that:

- explains artifact generation commands
- loads metadata/report/equity with standard Python and pandas
- builds normalized equity and drawdown frames
- does not embed secrets or run network calls by default

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_backtest_notebook_static.py -q
```

Expected: pass.

---

### Task 4: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update docs**

Document `docs/backtest_methodology_report.md` and `notebooks/backtest_methodology_report.ipynb`.

- [ ] **Step 2: Run verification**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py tests/test_backtest_notebook_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: all commands exit 0, allowing only normal CRLF warnings.

- [ ] **Step 3: Request review**

Review focus: report wording does not overclaim, runner metadata hashes all artifacts, notebook is valid JSON and does not include secrets, no dashboard/state writes.

- [ ] **Step 4: Commit, push, deploy**

Commit:

```powershell
git add src/backtest.py tests/test_backtest.py scripts/run_backtest.py tests/test_run_backtest_script.py notebooks/backtest_methodology_report.ipynb tests/test_backtest_notebook_static.py README.md docs/BACKLOG.md docs/superpowers/plans/2026-05-21-b011-notebook-report-polish.md
git commit -m "feat: add backtest methodology report guide"
git push
```

Deploy to Pi with focused tests, full tests, compile, service restart, and HTTP smoke.
