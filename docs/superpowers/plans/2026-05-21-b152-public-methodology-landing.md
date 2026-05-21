# B-152 Public Methodology Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public methodology landing page on the domain root, separate from the protected dashboard.

**Architecture:** Serve a static `public/` page with its own CSS and bitmap preview asset. Document a separate local service on port 8500 and keep Streamlit on port 8501 behind Cloudflare Access.

**Tech Stack:** Static HTML/CSS, PNG asset, systemd template, Cloudflare Tunnel docs, pytest static checks.

---

### Task 1: Static Contract

**Files:**
- Create: `tests/test_public_landing_static.py`
- Create: `tests/test_public_root_deploy_static.py`

- [x] **Step 1: Write failing tests**

Require public HTML/CSS/PNG files, public-safe content, no runtime dashboard leakage, route separation docs, and a static-service template.

Observed:

- `python -m pytest tests/test_public_landing_static.py tests/test_public_root_deploy_static.py -q` -> 7 failures because no B-152 files existed.

### Task 2: Static Landing And Route Docs

**Files:**
- Create: `public/index.html`
- Create: `public/methodology.html`
- Create: `public/assets/methodology.css`
- Create: `public/assets/methodology-preview.png`
- Create: `public/robots.txt`
- Create: `public/sitemap.xml`
- Create: `public/_headers`
- Create: `systemd/methodology-landing.service`
- Create: `docs/PUBLIC_METHODOLOGY_LANDING.md`
- Modify: `docs/DEPLOY_CLOUDFLARE_TUNNEL.md`
- Modify: `docs/DEPLOY_RASPBERRY_PI.md`
- Modify: `config/cloudflared-config.yml.example`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [x] **Step 1: Implement the static surface**

Add a no-script public landing page that explains the seven pillars, links to the protected dashboard, and avoids live dashboard data.

- [x] **Step 2: Document deployment separation**

Document `http://localhost:8500` for the public root and `http://localhost:8501` for the dashboard, with Cloudflare Access retained on the dashboard host.

- [ ] **Step 3: Verify, review, commit, push, deploy**

Run focused/full local QA, request focused review, commit as `feat: add public methodology landing`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.
