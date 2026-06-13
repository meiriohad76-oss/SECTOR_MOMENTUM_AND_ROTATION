# B-140 GitHub Actions Pi Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions scaffolding for push-to-Pi deploys on `backlog-stepwise-qa`.

**Architecture:** Use GitHub's Ubuntu runner plus OpenSSH, not a third-party deploy action. The workflow validates required secrets, SSHes into the existing Pi checkout with a pinned known-hosts entry, fast-forwards the branch, syncs dependencies from `requirements.txt`, runs the full test suite on the Pi, restarts the Streamlit service by terminating its current systemd `MainPID`, and performs the same local HTTP smoke used by manual deployments.

**Tech Stack:** GitHub Actions YAML, SSH, existing Pi systemd service, pytest static workflow tests.

---

### Task 1: Static Workflow Contract

**Files:**
- Create: `tests/test_github_actions_deploy_static.py`

- [ ] **Step 1: Write failing static tests**

Add tests requiring `.github/workflows/deploy-pi.yml` to trigger on `backlog-stepwise-qa`, use `PI_HOST`, `PI_USER`, `PI_SSH_KEY`, `PI_KNOWN_HOSTS`, `PI_REPO_PATH`, fast-forward with `git pull --ff-only origin backlog-stepwise-qa`, sync dependencies with `./.venv/bin/python -m pip install -r requirements.txt`, run `./.venv/bin/python -m pytest -q`, restart via `systemctl show "$PI_SERVICE_NAME" -p MainPID --value`, and smoke `http://127.0.0.1:8501/?ticker=XLK`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_github_actions_deploy_static.py -q`

Expected: FAIL because the workflow and docs do not exist.

### Task 2: Workflow And Docs

**Files:**
- Create: `.github/workflows/deploy-pi.yml`
- Create: `docs/DEPLOY_GITHUB_ACTIONS_PI.md`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b140-github-actions-pi-deploy.md`

- [ ] **Step 1: Implement workflow**

Add a workflow triggered by push to `backlog-stepwise-qa` and manual dispatch. Keep deployment secrets-driven and fail fast when required secrets are missing.

- [ ] **Step 2: Document operator setup**

Document `PI_HOST`, `PI_USER`, `PI_SSH_KEY`, `PI_KNOWN_HOSTS`, `PI_REPO_PATH`, and `PI_SERVICE_NAME`, plus the requirement that GitHub Actions can reach the Pi over SSH.

- [ ] **Step 3: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_github_actions_deploy_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: PASS, with only normal LF/CRLF warnings from `git diff --check`.

- [ ] **Step 4: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `ci: add github actions pi deploy`, push to GitHub, verify remote SHA, manually deploy this workflow commit to the Pi one last time, and record that live GitHub Actions execution is pending secrets/network configuration.
