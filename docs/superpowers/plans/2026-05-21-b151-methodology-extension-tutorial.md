# B-151 Methodology Extension Tutorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tutorial that explains how to add a sector, indicator, or pillar safely.

**Architecture:** Keep this as static operator documentation under `docs/`, guarded by a static pytest file that verifies the tutorial names the source files, safety boundaries, and verification commands. Link it from README and mark the backlog ticket implemented.

**Tech Stack:** Markdown documentation, pytest static checks.

---

### Task 1: Static Contract

**Files:**
- Create: `tests/test_methodology_tutorial_static.py`

- [x] **Step 1: Write failing tests**

Require the tutorial file, the three extension paths, provider/state safety language, verification commands, and README/backlog links.

Observed:

- `python -m pytest tests/test_methodology_tutorial_static.py -q` -> 4 failures because `docs/how-to-add-sector-indicator-pillar.md` and README/backlog links did not exist.

### Task 2: Tutorial And Links

**Files:**
- Create: `docs/how-to-add-sector-indicator-pillar.md`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [x] **Step 1: Write the tutorial**

Document how to add a sector/universe class, add an indicator, and add or change a pillar. Include exact files, tests, provider boundaries, state-machine boundaries, and Pi verification expectations.

- [ ] **Step 2: Verify, review, commit, push, deploy**

Run focused/full local QA, request focused review, commit as `docs: add methodology extension tutorial`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.
