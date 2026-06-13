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

- [x] **Step 3: Verify, review, commit, push, deploy**

Run focused/full local QA, request focused review, commit as `feat: add public methodology landing`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Observed:

- Focused review found three issues before commit: broad public-page account/state wording, public methodology links that would 404 under `public/`, and a robots sitemap without a file. Fixed with stronger static tests, `public/methodology.html`, and `public/sitemap.xml`.
- Re-review: no blocking issues; prior findings addressed.
- Focused local verification: `python -m pytest tests/test_public_landing_static.py tests/test_public_root_deploy_static.py -q` -> `8 passed in 0.17s`.
- Full local verification: `python -m pytest -q` -> `341 passed in 14.40s`.
- Compile verification: `python -m compileall app.py src scripts` -> exit 0.
- Diff verification: `git diff --check` -> exit 0, with expected CRLF warnings on Windows.
- Local static smoke: temporary `python -m http.server 8500 --bind 127.0.0.1 --directory public`; `/`, `/methodology.html`, `/assets/methodology-preview.png`, and `/sitemap.xml` all returned `200`.
- Local commit: `b4d95c2 feat: add public methodology landing`.
- GitHub branch: `backlog-stepwise-qa` at `b4d95c2f79bf7af0374239c95996b074f16d0f5f`.
- Pi pull: fast-forwarded `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION` to `b4d95c2`.
- Pi focused verification: `./.venv/bin/python -m pytest tests/test_public_landing_static.py tests/test_public_root_deploy_static.py -q` -> `8 passed in 0.03s`.
- Pi full verification: `./.venv/bin/python -m pytest -q` -> `341 passed in 5.02s`.
- Pi static smoke: temporary `./.venv/bin/python -m http.server 8500 --bind 127.0.0.1 --directory public`; `/`, `/methodology.html`, `/assets/methodology-preview.png`, and `/sitemap.xml` all returned `200`.
- Pi dashboard smoke: `dashboard active=active app=200 health=200`.
- Residual configuration: `methodology-landing.service` and Cloudflare root routing are documented but not installed/applied in this ticket because that requires operator-level Pi/systemd and Cloudflare configuration.
