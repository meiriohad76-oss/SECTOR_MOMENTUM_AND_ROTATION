# B-117 Custom Palettes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add custom dashboard palettes: Solarized, Nord, and Mono.

**Architecture:** Keep the existing dark/light theme toggle. Add a separate palette preference in `src.preferences`, expose it in the `VIEW OPTIONS` expander, and render the selected palette as server-side CSS variables so the UI does not depend on client script execution. The app still sets `data-palette` on the document root for traceability. A run-journal fingerprint guard prevents visual-only reruns from appending duplicate methodology runs.

**Tech Stack:** Streamlit session state, CSS custom properties, run-journal fingerprinting, pytest helper and static app/CSS coverage.

---

### Task 1: Palette Preference Helper

**Files:**
- Modify: `src/preferences.py`
- Modify: `tests/test_preferences.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring `initialize_preferences()` to set `color_palette` to `Default`, normalize invalid values, and `palette_key("Solarized") == "solarized"`, `palette_key("Nord") == "nord"`, `palette_key("Mono") == "mono"`, with invalid values returning `default`. Add server-side `palette_css_variables()` tests for Solarized dark/light tokens and default fallback.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_preferences.py -q`

Expected: FAIL because palette support is not implemented.

- [ ] **Step 3: Implement helper**

Add `PALETTE_OPTIONS`, `DEFAULT_PALETTE`, initialize `color_palette`, implement `palette_key()`, and render normalized palette/theme token overrides with `palette_css_variables()`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_preferences.py -q`

Expected: PASS.

### Task 2: App Wiring And CSS Tokens

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Modify: `tests/test_view_preferences_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to import `PALETTE_OPTIONS`, `palette_key`, and `palette_css_variables`, compute `_palette_key = palette_key(st.session_state.color_palette)`, append `_palette_css` into the style payload, set `document.documentElement.setAttribute("data-palette","{_palette_key}")`, and render a `st.radio("Palette", PALETTE_OPTIONS, key="color_palette")`.

Require CSS to include `data-palette="solarized"`, `data-palette="nord"`, and `data-palette="mono"` variable overrides.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_view_preferences_static.py -q`

Expected: FAIL because palette wiring and CSS are not implemented.

- [ ] **Step 3: Implement app/CSS**

Wire the preference radio into `render_view_preferences()`, inject selected palette CSS variables server-side, set the document attribute with the theme/density bootstrap script, and add dark/light-compatible CSS variable overrides for Solarized, Nord, and Mono.

### Task 2.5: Run-Journal Duplicate Guard

**Files:**
- Modify: `src/run_journal.py`
- Modify: `tests/test_run_journal.py`
- Modify: `tests/test_run_journal_app_static.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring a stable `dashboard_run_fingerprint()` that changes when methodology inputs change, and static app coverage requiring `_record_dashboard_run()` to compare `run_journal_last_fingerprint` before calling `append_dashboard_run()`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_run_journal.py tests/test_run_journal_app_static.py -q`

Expected: FAIL because fingerprinting and the app guard are not implemented.

- [ ] **Step 3: Implement guard**

Compute fingerprint from scored rows, BLUF decisions, metadata, provider, git SHA, and app version. If it matches `st.session_state.run_journal_last_fingerprint`, skip the append. Store the fingerprint only after a successful append.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_preferences.py tests/test_view_preferences_static.py tests/test_run_journal.py tests/test_run_journal_app_static.py -q`

Expected: PASS.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_preferences.py tests/test_view_preferences_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b117-custom-palettes.md`

- [ ] **Step 1: Update docs and backlog**

Move B-117 from Ideas into implemented status. Document that palettes are visual-only CSS token overrides.

Review-fix evidence captured during implementation:

```powershell
python -m pytest tests/test_preferences.py tests/test_view_preferences_static.py tests/test_run_journal.py tests/test_run_journal_app_static.py -q
# 24 passed
python -m pytest -q
# 260 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0, LF/CRLF warnings only
curl.exe -s -o NUL -w "%{http_code}" "http://127.0.0.1:8502/?ticker=XLK"
# HTTP_STATUS=200
```

- [ ] **Step 2: Full local QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Local HTTP smoke**

Run Streamlit temporarily and verify HTTP `200` on `/?ticker=XLK`.

- [ ] **Step 4: Review**

Request focused review. Fix Critical/Important feedback and rerun QA.

- [ ] **Step 5: Commit, push, and deploy**

Commit as `feat: add custom dashboard palettes`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
