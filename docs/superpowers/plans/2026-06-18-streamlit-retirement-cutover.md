# Streamlit Retirement Cutover Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Most steps are operational (Pi SSH, Cloudflare config) — they cannot be automated and must be done manually.

**Goal:** Deploy Next.js + FastAPI as production on Pi, run parallel for 1 week, flip the Cloudflare route, retire Streamlit after 30-day rollback window.

**Prerequisites:** Phase 1 gate (visual similarity ≥ 0.90 all 9 views) AND Phase 2 gate (full table + debrief lab + custom universe panel all shipping) must both be complete before starting this plan.

**Architecture:** Systemd services already exist (`systemd/sector-api.service`, `systemd/sector-next.service`). Pi SSH deploy is already set up via GitHub Actions (`deploy-pi.yml`). Cloudflare tunnel config routes are updated manually.

**Tech Stack:** Raspberry Pi (AHADPI5), systemd, Cloudflare tunnel, git.

---

## Pre-flight checklist (run before starting)

- [ ] **Confirm Phase 1 gate:**

```powershell
cd "c:\Users\meiri\momentum and flow"
python scripts/check_b170_retirement_readiness.py --min-similarity 0.90
```

Expected: `b170_visual_parity ok=true`.

- [ ] **Confirm Phase 2 gate (API endpoints):**

With QA API running (`python scripts/serve_next_qa_api.py --port 8765`):

```powershell
python -c "
import urllib.request, json
# debrief endpoint
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/api/v1/debrief', timeout=5)
    print('debrief:', r.status)
except Exception as e:
    print('debrief FAIL:', e)
"
```

Note: QA server may not have debrief/universe routes — that's OK. The gate is that the real FastAPI has them. Verify on Pi in Task 2.

---

## Task 1: Push to Pi via GitHub Actions

**Files:**
- Trigger: `.github/workflows/deploy-pi.yml`

- [ ] **Step 1: Push current main to GitHub**

```powershell
cd "c:\Users\meiri\momentum and flow"
git push origin main
```

Expected: GitHub Actions workflow triggers automatically on push to main.

- [ ] **Step 2: Monitor the deploy workflow**

Open GitHub → Actions → `deploy-pi.yml` → latest run.

Expected: All steps pass including pytest on Pi, ops readiness check, and Streamlit service HTTP 200.

- [ ] **Step 3: Confirm Pi Streamlit is still healthy**

```powershell
# SSH to Pi and check
ssh ahadpi5 "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8501/?ticker=XLK"
```

Expected: `200`.

---

## Task 2: Install FastAPI service on Pi

**Files:**
- Reference: `systemd/sector-api.service`
- Reference: `docs/DEPLOY_RASPBERRY_PI.md`

- [ ] **Step 1: SSH to Pi**

```powershell
ssh ahadpi5
```

- [ ] **Step 2: Check if sector-api.service is already installed**

```bash
systemctl --user status sector-api 2>/dev/null || echo "not installed"
```

- [ ] **Step 3: Install sector-api.service (if not already installed)**

```bash
cd /path/to/repo   # replace with actual Pi repo path
cp systemd/sector-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable sector-api
systemctl --user start sector-api
```

- [ ] **Step 4: Verify FastAPI is healthy**

```bash
sleep 5
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool | head -5
```

Expected: JSON response with health status. No errors.

- [ ] **Step 5: Verify debrief endpoint returns data**

```bash
curl -s http://127.0.0.1:8000/api/v1/debrief | python3 -c "import json,sys; d=json.load(sys.stdin); print('runs:', len(d['runs']), 'decisions:', len(d['decisions']))"
```

Expected: `runs: N decisions: M` where N ≥ 1 (Pi has run journal from previous Streamlit runs).

- [ ] **Step 6: Verify universe analyze endpoint**

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/universe/analyze \
  -H "Content-Type: application/json" \
  -d '{"tickers":["XLK","XLE"]}' | python3 -c "import json,sys; d=json.load(sys.stdin); print('available:', d['available_count'], 'missing:', d['missing_count'])"
```

Expected: `available: 2 missing: 0` (both tickers are in the universe).

---

## Task 3: Install Next.js service on Pi

**Files:**
- Reference: `systemd/sector-next.service`
- Reference: `docs/DEPLOY_RASPBERRY_PI.md`

- [ ] **Step 1: Build Next.js on Pi**

```bash
cd /path/to/repo/web
npm ci
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 2: Install sector-next.service**

```bash
cd /path/to/repo
cp systemd/sector-next.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable sector-next
systemctl --user start sector-next
```

- [ ] **Step 3: Verify Next.js is serving**

```bash
sleep 8
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3100/?presentation=c
```

Expected: `200`.

- [ ] **Step 4: Run full retirement readiness check on Pi**

```bash
cd /path/to/repo
python scripts/check_b170_retirement_readiness.py \
  --api-base-url http://127.0.0.1:8000 \
  --next-url http://127.0.0.1:3100/?presentation=c \
  --streamlit-url http://127.0.0.1:8501/?ticker=XLK \
  --min-similarity 0.90
```

Expected:
```
b170_feature_parity ok=true ...
b170_data_parity ok=true ...
b170_visual_parity ok=true ...
b170_operational_parity ok=true ...
b170_rollback ok=true ...
```

All 5 gates must be `ok=true` before proceeding.

---

## Task 4: Add staging Cloudflare route (parallel-run week)

**Files:**
- Reference: `docs/DEPLOY_CLOUDFLARE_TUNNEL.md`
- Manual: Cloudflare Zero Trust dashboard

- [ ] **Step 1: Add second public hostname in Cloudflare**

In Cloudflare Zero Trust dashboard → Networks → Tunnels → `pi-ai` tunnel → Public Hostnames:

Add:
- Subdomain: `next`
- Domain: `ahaddashboards.uk`
- Service: `http://localhost:3100`

This creates `next.ahaddashboards.uk` → Next.js.

- [ ] **Step 2: Verify the staging route from outside**

From your Windows machine (not Pi):

```powershell
curl -s -o $null -w "%{http_code}" https://next.ahaddashboards.uk/?presentation=c
```

Expected: `200`.

- [ ] **Step 3: Access the staging Next.js dashboard**

Open `https://next.ahaddashboards.uk/?presentation=c` in a browser (will require Cloudflare Access login).

Verify:
- Dashboard loads with live data from Pi run journal
- A/B/C screens work
- Full table expands and shows all tickers
- Debrief Lab shows run history
- Custom Universe Analyzer accepts tickers and returns results

- [ ] **Step 4: Record start date of parallel-run week**

Note the date. The production flip (Task 5) happens 7 days from today.

---

## Task 5: Flip production Cloudflare route

**Wait 7 days from Task 4 completion. During this time, monitor `next.ahaddashboards.uk` for any issues.**

- [ ] **Step 1: Confirm no rollback was triggered during parallel-run week**

No user-reported issues on `next.ahaddashboards.uk`.

- [ ] **Step 2: Update production hostname in Cloudflare**

In Cloudflare Zero Trust dashboard → Networks → Tunnels → `pi-ai` tunnel → Public Hostnames:

Find the existing hostname:
- Subdomain: `sentimentdashboard`
- Domain: `ahaddashboards.uk`
- Service: currently `http://localhost:8501` (Streamlit)

Update to:
- Service: `http://localhost:3100` (Next.js)

- [ ] **Step 3: Verify the flip**

```powershell
curl -s -o $null -w "%{http_code}" https://sentimentdashboard.ahaddashboards.uk/?presentation=c
```

Expected: `200`. Open in browser and confirm Next.js is serving (not Streamlit).

- [ ] **Step 4: Confirm Streamlit is still accessible on Pi (rollback ready)**

```bash
# SSH to Pi
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8501/?ticker=XLK
```

Expected: `200`. Streamlit is still running — just not publicly routed.

- [ ] **Step 5: Record the flip date**

Note the date. Streamlit can be retired 30 days from today if no rollback is triggered.

- [ ] **Step 6: Commit flip record**

```powershell
cd "c:\Users\meiri\momentum and flow"
git commit --allow-empty -m "ops: Cloudflare route flipped — Next.js is production, Streamlit on 30-day rollback"
```

---

## Task 6: Rollback procedure (use only if needed)

**This task is the emergency procedure. Only execute if production Next.js has a critical issue.**

- [ ] **Step 1: Revert Cloudflare hostname**

In Cloudflare Zero Trust dashboard → update `sentimentdashboard.ahaddashboards.uk` back to `http://localhost:8501`.

- [ ] **Step 2: Verify Streamlit is back**

```powershell
curl -s -o $null -w "%{http_code}" https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK
```

Expected: `200`.

- [ ] **Step 3: File a post-mortem issue and fix before reattempting the flip**

---

## Task 7: Retire Streamlit (30 days after Task 5)

**Only proceed if no rollback was triggered in the 30-day window.**

- [ ] **Step 1: Stop and disable Streamlit on Pi**

```bash
# SSH to Pi
systemctl --user stop sector-dashboard
systemctl --user disable sector-dashboard
```

- [ ] **Step 2: Archive `app.py` in the repo**

Add a deprecation header to `app.py` on the first line:

```python
# DEPRECATED 2026-MM-DD: Replaced by Next.js (web/) + FastAPI (src/api_server.py).
# This file is archived and no longer executed in production.
# The production route is https://sentimentdashboard.ahaddashboards.uk/ → Next.js on port 3100.
```

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md`, update the "Stack" table to remove the Streamlit row. Update the "Current branch" section. Remove "Known deferred work" entry for sparklines if implemented.

- [ ] **Step 4: Mark B-170 complete in BACKLOG.md**

In `docs/BACKLOG.md`, update the B-170 entry to say:

```
**Status:** COMPLETE. Next.js is production. Streamlit retired YYYY-MM-DD.
```

- [ ] **Step 5: Final commit**

```powershell
cd "c:\Users\meiri\momentum and flow"
git add app.py CLAUDE.md docs/BACKLOG.md
git commit -m "chore: retire Streamlit — Next.js is production

Streamlit ran as production from initial deployment until YYYY-MM-DD.
Next.js on port 3100 + FastAPI on port 8000 are now the sole production stack.
app.py is archived with a deprecation header; sector-dashboard.service is disabled on Pi.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push origin main
```
