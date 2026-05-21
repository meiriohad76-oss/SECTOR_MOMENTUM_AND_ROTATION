# B-123 Discord And Mattermost Webhooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional Discord and Mattermost webhook delivery alongside the existing Telegram and Slack transition alerts.

**Architecture:** Keep `send_transition_alerts()` as the single alert boundary called after state persistence. Add two optional webhook secrets that post Slack-compatible JSON payloads and reuse the existing fail-open alert behavior so scoring never fails because an alert provider is down.

**Tech Stack:** Existing `requests` dependency, Streamlit/env secret resolution, pytest monkeypatching.

---

### Task 1: Webhook Routing

**Files:**
- Modify: `src/alerts.py`
- Modify: `tests/test_alerts.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring `send_transition_alerts()` to post to `DISCORD_WEBHOOK_URL` and `MATTERMOST_WEBHOOK_URL` when configured, while preserving Telegram and Slack behavior.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_alerts.py -q`

Expected: FAIL because the new webhook secrets are ignored.

- [ ] **Step 3: Implement routing**

Resolve `DISCORD_WEBHOOK_URL` and `MATTERMOST_WEBHOOK_URL`, post `{"text": text}` to each configured URL, and swallow `requests.RequestException` exactly like Slack.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_alerts.py -q`

Expected: PASS.

### Task 2: Docs, QA, Review, Deploy

**Files:**
- Modify: `.streamlit/secrets.toml.example`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b123-discord-mattermost-webhooks.md`

- [ ] **Step 1: Update operator docs**

Document the new secrets and move B-123 into implemented status with live validation pending webhook URLs.

- [ ] **Step 2: Full QA**

Run:

```powershell
python -m pytest tests/test_alerts.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `feat: add discord mattermost webhooks`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Implementation evidence captured during development:

```powershell
python -m pytest tests/test_alerts.py -q
# 10 passed
```

Review fix: Discord uses the normal webhook payload shape (`content`) while Mattermost keeps the Slack-compatible `text` payload. Added a provider-specific regression test and a non-blocking failure test for those routes.
