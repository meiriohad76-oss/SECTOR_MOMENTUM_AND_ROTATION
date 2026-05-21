# B-141 Docker Compose Dev Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Docker Compose support for easier local dashboard development.

**Architecture:** Add a simple Python slim Dockerfile for the Streamlit app and a compose service that maps port `8501`, mounts local Streamlit config and `data/` artifacts for development, writes container state to `data/state.json`, and keeps secrets/generated state out of the image build context.

**Tech Stack:** Docker, Docker Compose, Streamlit, pytest static scaffold checks.

---

### Task 1: Static Docker Contract

**Files:**
- Create: `tests/test_docker_compose_static.py`

- [x] **Step 1: Write failing tests**

Require `Dockerfile`, `docker-compose.yml`, and `.dockerignore` to exist with the expected Streamlit command, port mapping, mounted local data/state path, healthcheck, yfinance default, and secret exclusions.

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_docker_compose_static.py -q`

Expected: FAIL because the Docker scaffold is missing.

### Task 2: Compose Scaffold And Docs

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b141-docker-compose-dev.md`

- [x] **Step 1: Implement scaffold**

Add the dev Dockerfile, compose service, and dockerignore. Keep it a local dev path, not a replacement for Pi systemd deployment.

- [x] **Step 2: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_docker_compose_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `chore: add docker compose dev stack`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Implementation evidence captured during development:

```powershell
python -m pytest tests/test_docker_compose_static.py -q
# 3 passed
python -m pytest tests/test_docker_compose_static.py tests/test_scoring.py -q
# 10 passed after review fixes
docker compose config
# exit 0
docker compose build
# failed before build: Docker Desktop/daemon was unavailable at npipe:////./pipe/dockerDesktopLinuxEngine
```

Review fixes: switched Compose default provider to `yfinance`, moved container state persistence to `STATE_FILE=/app/data/state.json`, removed the fragile root `state.json` bind mount, and broadened `.dockerignore` secret/private-key exclusions.

Second review fixes: added explicit common private-key filename exclusions to `.dockerignore` and regression coverage for `STATE_FILE` environment import behavior.
