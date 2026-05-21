# B-120 Email Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional daily email digest for LOW severity state transitions, intended to run at 08:00 ET.

**Architecture:** Extend `src.alerts` with pure filtering/formatting helpers and a safe SMTP sender that is disabled unless email secrets are configured. Add a small script entry point that reads the persisted transition log and sends yesterday's low-severity digest for cron/systemd timers; no dashboard page load sends email.

**Tech Stack:** Python stdlib `email.message`, `smtplib`, `zoneinfo`, existing Streamlit/env secret resolver, pytest monkeypatching.

---

### Task 1: Low-Severity Digest Helpers

**Files:**
- Modify: `src/alerts.py`
- Modify: `tests/test_alerts.py`

- [ ] **Step 1: Write failing tests**

Add tests that call `low_severity_digest_transitions()` with transitions from yesterday, today, and high-severity destinations. Expected behavior: only yesterday's non-`EXIT` / non-`BEARISH_STAGE_4` transitions remain.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_alerts.py -q`

Expected: FAIL because the digest helper does not exist.

- [ ] **Step 3: Implement helpers**

Add `HIGH_SEVERITY_STATES`, `digest_date_for_now()`, and `low_severity_digest_transitions()`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_alerts.py -q`

Expected: PASS.

### Task 2: Safe SMTP Sender

**Files:**
- Modify: `src/alerts.py`
- Modify: `tests/test_alerts.py`
- Modify: `.streamlit/secrets.toml.example`

- [ ] **Step 1: Write failing tests**

Add tests for `format_email_digest()` and `send_low_severity_email_digest()`: unconfigured secrets skip network calls, configured SMTP sends one `EmailMessage`, and SMTP errors are swallowed.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_alerts.py -q`

Expected: FAIL because the formatting and SMTP sender are missing.

- [ ] **Step 3: Implement sender**

Read `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `EMAIL_DIGEST_FROM`, and `EMAIL_DIGEST_TO` from secrets/env. Send only when host, sender, recipients, and low-severity transitions are present.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_alerts.py -q`

Expected: PASS.

### Task 3: Cron-Friendly Script And Docs

**Files:**
- Create: `scripts/send_email_digest.py`
- Create: `tests/test_email_digest_script.py`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b120-email-digest.md`

- [ ] **Step 1: Write failing script test**

Add a test that imports the script, monkeypatches `recent_transitions()` and `send_low_severity_email_digest()`, calls `main()`, and asserts it passes chronological transitions to the sender.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_email_digest_script.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement script and docs**

Create `scripts/send_email_digest.py`, document the email secrets, and move B-120 to implemented status while noting that actual 08:00 ET delivery requires scheduling the script on the Pi.

- [ ] **Step 4: Full QA, review, commit, push, deploy**

Run:

```powershell
python -m pytest tests/test_alerts.py tests/test_email_digest_script.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Request focused review, fix Critical/Important feedback, commit as `feat: add email transition digest`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

### Task 4: Review Fix - ET Transition Date Alignment

**Files:**
- Modify: `src/scoring.py`
- Modify: `tests/test_scoring.py`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b120-email-digest.md`

- [ ] **Step 1: Write failing regression test**

Add a test that patches the state-machine clock to `2026-05-21T01:00:00Z` and asserts persisted transition dates are `2026-05-20`, the US/Eastern local day.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_scoring.py::test_apply_state_machine_dates_transitions_by_us_eastern_day -q`

Expected: FAIL because transition dates are stamped with UTC dates.

- [ ] **Step 3: Implement ET date helper**

Add `_now_utc()` for testable clock injection and `_transition_date()` that converts the clock to `America/New_York` before writing state-machine transition dates.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_scoring.py::test_apply_state_machine_dates_transitions_by_us_eastern_day tests/test_alerts.py tests/test_email_digest_script.py -q`

Expected: PASS.

Review-fix evidence captured during implementation:

```powershell
python -m pytest tests/test_scoring.py::test_apply_state_machine_dates_transitions_by_us_eastern_day tests/test_alerts.py tests/test_email_digest_script.py -q
# 11 passed
python -m pytest -q
# 268 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0, LF/CRLF warnings only
python scripts/send_email_digest.py
# email_digest=skipped
```
