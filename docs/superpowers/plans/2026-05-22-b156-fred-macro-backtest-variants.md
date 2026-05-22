# B-156 FRED Macro Backtest Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in B-011 macro-conditioned exposure variants that test whether selected FRED macro conditions would have improved historical methodology outcomes.

**Architecture:** Keep variant logic in pure `src/backtest.py` so it accepts already-loaded prices, target weights, and macro series. Wire `scripts/run_backtest.py --macro-variants` to fetch FRED only when explicitly requested, then include variant rows in manual report metadata without changing scoring or live dashboard decisions.

**Tech Stack:** Python dataclasses, pandas, pytest, existing FRED fetch helper, B-011 manual report artifacts.

---

### Task 1: Pure Macro Variant Engine

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [x] **Step 1: Write failing tests**

Added tests for:

- macro condition masks using only observations known at or before each rebalance date
- defensive exposure variants beating a crash path when a curve-falling condition is known
- report formatting for macro variant rows

Run:

```powershell
python -m pytest tests/test_backtest.py::test_macro_condition_mask_uses_past_observations_only tests/test_backtest.py::test_evaluate_macro_condition_variants_compares_defensive_filter tests/test_backtest.py::test_format_backtest_report_includes_macro_variant_table -q
```

Observed RED:

```text
AttributeError: module 'src.backtest' has no attribute 'macro_condition_mask'
AttributeError: module 'src.backtest' has no attribute 'evaluate_macro_condition_variants'
TypeError: format_backtest_report() got an unexpected keyword argument 'macro_variant_summary'
```

- [x] **Step 2: Implement pure helpers**

Implemented `MacroVariantRule`, `macro_condition_mask()`, and `evaluate_macro_condition_variants()`. The engine supports `rising`, `falling`, `flat`, `above`, `below`, `positive`, and `negative` conditions; aligns macro history to target dates with forward-fill only; scales existing target weights during active macro conditions; and reports total-return, Sharpe, and drawdown deltas.

- [x] **Step 3: Add report table**

Added an optional `Macro Condition Variants` section to `format_backtest_report()` and `format_methodology_report()` when a non-empty variant summary is supplied.

### Task 2: Manual Runner Wiring

**Files:**
- Modify: `tests/test_run_backtest_script.py`
- Modify: `scripts/run_backtest.py`

- [x] **Step 1: Write failing tests**

Added tests proving the parser exposes `--macro-variants` and that FRED fetching / variant evaluation happens only when enabled.

Run:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_run_backtest_parser_exposes_macro_variants_flag tests/test_run_backtest_script.py::test_run_backtest_builds_macro_variant_summary_only_when_enabled -q
```

Observed RED:

```text
SystemExit: 2, unrecognized arguments: --macro-variants
AttributeError: scripts.run_backtest has no attribute 'fetch_fred'
```

- [x] **Step 2: Implement opt-in runner path**

Added `--macro-variants`, default FRED rules for curve-falling, high-yield-spread-rising, and stress-rising defensive filters, `_build_macro_variant_summary()`, and metadata serialization under `macro_variant_summary`.

- [x] **Step 3: Verify focused and affected tests**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_macro_condition_mask_uses_past_observations_only tests/test_backtest.py::test_evaluate_macro_condition_variants_compares_defensive_filter tests/test_backtest.py::test_format_backtest_report_includes_macro_variant_table tests/test_run_backtest_script.py::test_run_backtest_parser_exposes_macro_variants_flag tests/test_run_backtest_script.py::test_run_backtest_builds_macro_variant_summary_only_when_enabled -q
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
```

Observed:

```text
focused -> 5 passed
affected -> 55 passed
```

Reviewer follow-up found that `_write_artifacts()` was not receiving the non-empty macro variant frame, so metadata would stay empty even when reports showed macro rows. Added a regression test:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_run_backtest_writes_macro_variant_summary_to_metadata -q
```

Observed RED:

```text
IndexError: list index out of range
```

After passing `macro_variant_summary=macro_variant_summary` into `_write_artifacts()`, observed:

```text
1 passed
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q -> 56 passed
reviewer re-check -> no remaining issues found
```

### Task 3: Docs, QA, Deploy

**Files:**
- Modify: `docs/BACKLOG.md`
- Modify: `docs/FRED_DATA_OPPORTUNITIES.md`
- Modify: `README.md`
- Modify: `docs/superpowers/handoffs/2026-05-21-backlog-completion-pause.md`

- [x] **Step 1: Document B-156**

Documented the opt-in macro variant flag, no-lookahead alignment, and no scoring/state-machine/provider-flow changes.

- [x] **Step 2: Run local QA**

Required:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:

```text
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q -> 56 passed
python -m pytest -q -> 371 passed
python -m compileall app.py src scripts -> exit 0
git diff --check -> exit 0
```

- [ ] **Step 3: Review, push, deploy, and verify Pi**

Required:

```powershell
git push origin backlog-stepwise-qa
ssh -i "$env:USERPROFILE\.ssh\codex_ahadpi_ed25519" -o BatchMode=yes -o ConnectTimeout=8 ahad@10.100.102.18 'cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION && git pull --ff-only origin backlog-stepwise-qa && ./.venv/bin/python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q && ./.venv/bin/python -m pytest -q && systemctl is-active sector-dashboard && curl -s -o /dev/null -w "%{http_code}" --max-time 8 "http://127.0.0.1:8501/?ticker=XLK"'
```
