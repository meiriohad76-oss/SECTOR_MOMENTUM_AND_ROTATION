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

- [x] **Step 2: Verify, review, commit, push, deploy**

Run focused/full local QA, request focused review, commit as `docs: add methodology extension tutorial`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Observed:

- Focused review: no blocking issues; reviewer noted a minor defensive-ticker wording mismatch, fixed before commit.
- Focused local verification: `python -m pytest tests/test_methodology_tutorial_static.py -q` -> `4 passed in 0.06s`.
- Full local verification: `python -m pytest -q` -> `333 passed in 21.97s`.
- Compile verification: `python -m compileall app.py src scripts` -> exit 0.
- Diff verification: `git diff --check` -> exit 0, with expected CRLF warnings on Windows.
- Local commit: `1c6b90c docs: add methodology extension tutorial`.
- GitHub branch: `backlog-stepwise-qa` at `1c6b90c41d754eb27231282ea5354cac4321ad42`.
- Pi pull: fast-forwarded `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION` to `1c6b90c`.
- Pi focused verification: `./.venv/bin/python -m pytest tests/test_methodology_tutorial_static.py -q` -> `4 passed in 0.03s`.
- Pi full verification: `./.venv/bin/python -m pytest -q` -> `333 passed in 4.94s`.
- Pi service smoke: `poll_1 sha=1c6b90c41d754eb27231282ea5354cac4321ad42 active=active app=200 health=200`.
