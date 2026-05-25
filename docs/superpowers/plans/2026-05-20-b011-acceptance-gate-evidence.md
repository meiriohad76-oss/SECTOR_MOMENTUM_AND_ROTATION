# B-011 Acceptance Gate Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the manual B-011 report explain exactly which evidence each acceptance gate used.

**Architecture:** Keep evidence generation in pure `src/backtest.py`. `evaluate_acceptance_gates()` will attach a short evidence/rule string to each gate, and `format_gate_report()` will render that evidence without changing the core pass/fail contract. The manual runner stays unchanged because it already passes OOS metrics into the gates.

**Tech Stack:** Python, pandas, pytest, existing B-011 report helpers.

---

## File Structure

- Modify `tests/test_backtest.py`: assert gate dictionaries include evidence strings and report text renders them.
- Modify `src/backtest.py`: extend `_gate()` and `evaluate_acceptance_gates()` with evidence/rule text; render it in `format_gate_report()`.
- Modify `README.md` and `docs/BACKLOG.md`: mention that the manual report includes gate evidence/rules.

---

### Task 1: Gate Evidence Contract

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing tests**

Add assertions to `test_evaluate_acceptance_gates_compares_oos_to_equal_weight_benchmark()` that:

- `report["oos_sharpe"]["evidence"]` mentions `strategy OOS Sharpe >= 0.70`
- `report["max_drawdown"]["evidence"]` mentions `75% of equal-weight OOS drawdown`
- `report["annualized_turnover"]["evidence"]` mentions `strategy OOS annualized turnover <= 300%`

Update `test_format_gate_report_includes_pass_fail_lines()` to assert those evidence strings render in the report.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_backtest.py::test_evaluate_acceptance_gates_compares_oos_to_equal_weight_benchmark tests/test_backtest.py::test_format_gate_report_includes_pass_fail_lines -q
```

Expected: fails because gate dictionaries do not include evidence.

- [ ] **Step 3: Implement evidence strings**

In `src/backtest.py`, add an optional `evidence` field to `_gate()` and provide deterministic evidence strings from `evaluate_acceptance_gates()`. Keep `name`, `value`, `threshold`, and `passed` unchanged.

- [ ] **Step 4: Render evidence**

In `format_gate_report()`, keep the existing pass/fail line and append an indented `Evidence:` line when a gate includes evidence.

- [ ] **Step 5: Run focused verification**

```powershell
python -m pytest tests/test_backtest.py -q
```

Expected: backtest tests pass.

---

### Task 2: Docs And Full QA

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update docs**

Document that the manual report now prints the evidence/rule behind each acceptance gate.

- [ ] **Step 2: Run verification**

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Request review and commit**

Ask a reviewer to inspect gate evidence wording and contract compatibility, then commit if approved:

```powershell
git add src/backtest.py tests/test_backtest.py README.md docs/BACKLOG.md docs/superpowers/plans/2026-05-20-b011-acceptance-gate-evidence.md
git commit -m "feat: explain backtest gate evidence"
```
