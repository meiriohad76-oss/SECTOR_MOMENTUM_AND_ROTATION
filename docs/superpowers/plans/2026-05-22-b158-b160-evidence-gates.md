# B-158/B-160 Evidence Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement fail-closed evidence gates for FRED and Massive promotion tickets without changing live scoring or recommendations when no validation candidate exists.

**Architecture:** Add a pure `src/evidence_gates.py` module that evaluates validation summary rows and formats an operator report. Add a read-only CLI in `scripts/evaluate_evidence_gates.py` that reads committed validation CSVs and writes `docs/evidence_gate_report.md`. Keep B-158/B-160 research-only unless a future validation report contains candidate rows and the promotion ticket is explicitly reviewed.

**Tech Stack:** Python, pandas, pytest, Markdown report artifacts.

---

### Task 1: Pure Evidence Gate Core

**Files:**
- Create: `src/evidence_gates.py`
- Create: `tests/test_evidence_gates.py`

- [ ] **Step 1: Write failing tests**

```python
def test_evidence_gate_blocks_when_no_candidates():
    frame = pd.DataFrame([
        {"variant": "Curve falling defensive", "promotion_label": "needs more testing"},
        {"variant": "Stress rising defensive", "promotion_label": "do not promote"},
    ])

    decision = evaluate_promotion_gate(
        ticket="B-158",
        source="FRED macro",
        summary=frame,
        validation_report_path="docs/fred_macro_validation_report.md",
    )

    assert decision.status == "blocked_no_candidates"
    assert decision.candidate_count == 0
    assert decision.blockers == ["No candidate rows were present in the validation summary."]
```

- [ ] **Step 2: Run test to verify RED**

Run: `python -m pytest tests/test_evidence_gates.py -q`

Expected: FAIL because `src.evidence_gates` does not exist.

- [ ] **Step 3: Implement minimal core**

```python
@dataclass(frozen=True)
class PromotionGateDecision:
    ticket: str
    source: str
    status: str
    candidate_count: int
    candidate_variants: tuple[str, ...]
    blockers: tuple[str, ...]
```

- [ ] **Step 4: Run focused test**

Run: `python -m pytest tests/test_evidence_gates.py -q`

Expected: PASS.

### Task 2: Gate Report CLI

**Files:**
- Create: `scripts/evaluate_evidence_gates.py`
- Create: `tests/test_evaluate_evidence_gates_script.py`
- Create: `docs/evidence_gate_report.md`

- [ ] **Step 1: Write failing CLI tests**

```python
def test_evaluate_evidence_gates_script_writes_fail_closed_report(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "FRED_VALIDATION_SUMMARY_PATH", tmp_path / "fred.csv")
    monkeypatch.setattr(script, "MASSIVE_VALIDATION_SUMMARY_PATH", tmp_path / "massive.csv")
    monkeypatch.setattr(script, "EVIDENCE_GATE_REPORT_PATH", tmp_path / "report.md")

    assert script.main([]) == 0
    assert "blocked_no_candidates" in script.EVIDENCE_GATE_REPORT_PATH.read_text()
```

- [ ] **Step 2: Implement CLI**

```python
def main(argv=None) -> int:
    fred = evaluate_promotion_gate(...)
    massive = evaluate_promotion_gate(...)
    EVIDENCE_GATE_REPORT_PATH.write_text(format_evidence_gate_report([fred, massive]))
    return 0
```

- [ ] **Step 3: Run focused tests**

Run: `python -m pytest tests/test_evidence_gates.py tests/test_evaluate_evidence_gates_script.py -q`

Expected: PASS.

### Task 3: Backlog And QA

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update B-158 and B-160**

Mark both as implemented fail-closed evidence gates, with live promotion blocked by current reports because no candidate rows exist.

- [ ] **Step 2: Run local QA**

Run:
```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Commit, push, deploy, and Pi QA**

Run:
```powershell
git add src/evidence_gates.py scripts/evaluate_evidence_gates.py tests/test_evidence_gates.py tests/test_evaluate_evidence_gates_script.py docs/evidence_gate_report.md docs/BACKLOG.md docs/superpowers/plans/2026-05-22-b158-b160-evidence-gates.md
git commit -m "feat: add fail-closed evidence gates"
git push origin backlog-stepwise-qa
```

Expected: local and Pi QA pass, service remains active, and HTTP smoke returns 200.
