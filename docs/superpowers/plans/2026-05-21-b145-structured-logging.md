# B-145 Structured Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured JSON logging with optional HTTP log shipping for Pi operations.

**Architecture:** Add a pure `src.structured_logging` module that configures an idempotent JSONL file logger under `data/logs/app.jsonl` and optionally ships each record to a generic JSON HTTP endpoint via `LOG_SHIP_URL` / `LOG_SHIP_TOKEN`. Wire the Streamlit app to log dashboard run-journal success/failure events without changing scoring, state-machine, or alert behavior.

**Tech Stack:** Python standard-library `logging`, `requests`, pytest static and unit coverage.

---

### Task 1: Structured Logger Contract

**Files:**
- Create: `tests/test_structured_logging.py`
- Create: `tests/test_structured_logging_app_static.py`

- [x] **Step 1: Write failing tests**

Cover JSONL formatting, idempotent logger setup across reruns, optional HTTP shipping, invalid log levels, and static app wiring around dashboard run-journal events.

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_structured_logging.py tests/test_structured_logging_app_static.py -q
```

Expected: FAIL because `src.structured_logging` and app wiring do not exist yet.

Evidence:

```powershell
python -m pytest tests/test_structured_logging.py tests/test_structured_logging_app_static.py -q
# collection error: cannot import name 'structured_logging' from 'src'
```

### Task 2: Logging Implementation And Docs

**Files:**
- Create: `src/structured_logging.py`
- Modify: `app.py`
- Modify: `.gitignore`
- Modify: `.dockerignore`
- Modify: `.streamlit/secrets.toml.example`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b145-structured-logging.md`

- [x] **Step 1: Implement logger module**

Add `JsonLineFormatter`, `HttpJsonLogHandler`, `configure_structured_logging()`, and `log_event()`. Keep shipping optional and non-blocking; a broken endpoint must never stop dashboard rendering.

- [x] **Step 2: Wire app events**

Configure `APP_LOGGER` once at import time and log `dashboard_run_recorded` / `dashboard_run_journal_error` from `_record_dashboard_run()`.

- [x] **Step 3: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_structured_logging.py tests/test_structured_logging_app_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Evidence:

```powershell
python -m pytest tests/test_structured_logging.py tests/test_structured_logging_app_static.py tests/test_run_journal_app_static.py -q
# 8 passed before review fixes
python -m pytest tests/test_email_digest_script.py tests/test_structured_logging.py tests/test_structured_logging_app_static.py tests/test_run_journal_app_static.py -q
# 11 passed after review fixes
python scripts/send_email_digest.py
# direct run measured at about 0.65s after avoiding the heavy scoring import
python -m pytest -q
# 300 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0
```

Review fixes: changed HTTP log shipping to start a daemon background thread by default, added `async_mode=False` for deterministic direct handler tests, made blank environment values override Streamlit secrets so `LOG_SHIP_URL=""` disables shipping, and made `scripts/send_email_digest.py` avoid importing `src.scoring` for its simple transition-log read.

- [x] **Step 4: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `feat: add structured json logging`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Completion evidence:

```powershell
python -m pytest tests/test_email_digest_script.py tests/test_structured_logging.py tests/test_structured_logging_app_static.py tests/test_run_journal_app_static.py -q
# 11 passed
python -m pytest -q
# 300 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0
git push origin backlog-stepwise-qa
# bc1cabd pushed
```

Pi evidence:

```bash
git pull --ff-only
# fast-forwarded to bc1cabd
./.venv/bin/python -m pytest tests/test_email_digest_script.py tests/test_structured_logging.py tests/test_structured_logging_app_static.py tests/test_run_journal_app_static.py -q
# 11 passed
./.venv/bin/python scripts/send_email_digest.py
# email_digest=skipped
./.venv/bin/python -m pytest -q
# 300 passed
curl http://127.0.0.1:8501/?ticker=XLK
# HTTP 200 after service restart poll 7
```
