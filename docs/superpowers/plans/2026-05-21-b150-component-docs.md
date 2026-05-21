# B-150 Component Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generated Storybook-style component inventory for the Streamlit dashboard.

**Architecture:** Keep the docs source as a pure metadata catalog in `src/component_docs.py`; render the generated reference panel from `app.py` without adding provider calls, scoring work, or state-machine writes. Static tests guard app wiring and unit tests guard the catalog coverage.

**Tech Stack:** Python, Streamlit markdown, pytest static/unit checks, existing CSS tokens.

---

### Task 1: Catalog And Renderer

**Files:**
- Create: `src/component_docs.py`
- Test: `tests/test_component_docs.py`

- [x] **Step 1: Write failing tests**

Require `src.component_docs` to expose the dashboard catalog, table rows, generated HTML, and render-function coverage.

Observed:

- `python -m pytest tests/test_component_docs.py tests/test_component_docs_app_static.py -q` failed with `ModuleNotFoundError: No module named 'src.component_docs'`.

- [x] **Step 2: Implement pure catalog**

Add `ComponentDoc`, `DASHBOARD_COMPONENT_DOCS`, `documented_render_functions()`, `component_docs_rows()`, and `component_docs_html()`.

- [x] **Step 3: Verify focused catalog tests**

Observed:

- `python -m pytest tests/test_component_docs.py tests/test_component_docs_app_static.py -q` -> `5 passed in 0.30s`.

### Task 2: Dashboard Surface

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Test: `tests/test_component_docs_app_static.py`

- [x] **Step 1: Wire the generated panel**

Import the pure catalog, add `render_component_docs()`, and render it after the methodology explainer and before the live decision panels.

- [x] **Step 2: Add compact component-doc styling**

Use the existing dashboard tokens, section header, card radius, and responsive grid constraints.

- [x] **Step 3: Verify focused app/static tests**

Observed:

- `python -m pytest tests/test_component_docs.py tests/test_component_docs_app_static.py tests/test_performance_audit_app_static.py tests/test_mobile_responsive_static.py -q` -> `11 passed in 0.20s`.
- `python -m compileall app.py src` -> exit 0.
- `git diff --check` -> exit 0, with expected CRLF warnings on Windows.

### Task 3: Documentation, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b150-component-docs.md`

- [x] **Step 1: Document behavior and residual risk**

README documents the generated component inventory and backlog marks B-150 implemented with the Streamlit-native residual risk.

- [ ] **Step 2: Review, full QA, commit, push, deploy**

Request focused review, fix Critical/Important findings, run full local pytest, commit as `feat: add dashboard component docs`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.
