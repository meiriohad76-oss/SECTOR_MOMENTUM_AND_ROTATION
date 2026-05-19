# Sentiment Board — Backlog

All un-deployed suggestions captured here so nothing falls off. Ordered by category, then by impact-per-effort within each.

Status legend:
- 🔥 **Ready to deploy** — code exists, just needs push + pull + restart
- 🎯 **Next session** — well-scoped, would do this first if asked
- 💡 **Researched, not built** — spec is clear, requires focused work
- 🌟 **Idea** — captured for later, may or may not pursue

---

## 🔥 Pending push / deploy

### B-001 · HTML render fix for action cards (BLUF) — JUST FIXED
**Status:** code patched, awaiting deploy
**File:** `app.py` (new `_md()` helper)
**Symptom:** action cards rendered as raw HTML text because indented HTML inside f-strings was treated as a markdown code block by Streamlit.
**Fix:** wrapper strips leading whitespace before calling `st.markdown(..., unsafe_allow_html=True)`. Applied to 14 call sites.
**Deploy:** push from Windows → pull on Pi → `sudo systemctl restart sector-dashboard`.

---

## 🎯 Next-session priorities

### B-010 · Wire Massive AI to ETF primary-flow source (Pillar 7 stub #1)
**File:** `src/flow.py` — replace `etf_primary_flow_5d_pct()` stub.
**Approach:** Massive AI structured Web Data API → iShares ETF holdings/SHO daily JSON (e.g., for XLK use the BlackRock holdings endpoint). Compute Δshares × NAV / AUM over 5 days.
**Effort:** half a day with the Massive API docs in hand.
**Why first:** biggest signal-quality jump per hour of work. Also de-risks the integration pattern for the other 4 stubs (block trades, dark pool, short interest, 13F).

### B-011 · Build backtest harness (academic-rigorous, 2–3 days)
**Tooling:** `vectorbt` engine, 2003–today data, walk-forward optimization.
**Deliverables per §8 of methodology:**
- CAGR, Sharpe, Sortino, max drawdown, Calmar
- Turnover, transaction cost sensitivity (3/5/10 bps)
- Compare to 60/40 SPY/AGG + equal-weight 11-sector benchmark
- Acceptance gates: OOS Sharpe ≥ 0.7, max DD ≤ 75% of benchmark
**Output:** Jupyter notebook + summary report in `docs/`, charts in dashboard `/backtest` page.
**Why second:** validates whether the methodology actually has edge before more design polish.

### B-012 · Cloudflare Access lockdown — confirm policy is saved
**Status:** application setup started, policy rules incomplete in screenshots.
**Action:** verify `https://sentimentdashboard.ahaddashboards.uk` shows the Cloudflare email-OTP wall in incognito. If not, re-do the Policy steps in `one.dash.cloudflare.com → Access → Applications → pi-ai → Policies`.

---

## 💡 Researched but not built

### B-020 · Massive AI flow integration — remaining 4 stubs
After B-010 establishes the pattern, wire the rest:
- **B-020a** `block_trade_upside_ratio()` — Polygon `/v3/trades` or NYSE TAQ delayed via Massive
- **B-020b** `dark_pool_pct()` — FINRA ATS Transparency weekly CSV
- **B-020c** `short_interest_delta_15d()` — FINRA Reg SHO bi-monthly file
- **B-020d** `thirteen_f_net_buys_q()` — SEC EDGAR Form 13F-HR (XBRL parsing)

Each is ~2–4 hours after the integration pattern is set. Flip `STUB_MODE = False` in `flow.py` when done.

### B-021 · Telegram / Slack alerting on state transitions
**File:** `src/scoring.py` — add `_notify_transition(ticker, from_state, to_state)` hook inside `apply_state_machine()`.
**Send to:** Telegram bot, Slack webhook, or Pushover.
**Severity tiers from methodology §6:**
- LOW (info digest, 08:00 daily): `WARNING` transitions
- HIGH (immediate push): `EXIT` and `BEARISH_STAGE_4`
- MACRO (separate channel): Faber 10mo flip on SPY
**Effort:** ~1 hour for one channel, ~2 hours if templating + retry + dedup.

### B-022 · FRED macro overlay — full ISM PMI + business cycle
**File:** `src/macro.py` — `business_cycle_phase_full()` stub already commented in.
**API:** https://fred.stlouisfed.org/docs/api/api_key.html (free key, no rate limit issues).
**Series:** `MANEMP` (ISM PMI), `T10Y2Y` (yield curve), `INDPRO` (industrial production).
**Effort:** ~30 lines + FRED_API_KEY env var.
**Impact:** sharpens cycle phase from coarse 2-signal to proper Stovall/Fidelity 4-phase.

### B-023 · Click-through from cards/alerts/RRG → drill-down
**Limitation:** Streamlit's native `st.markdown` can't dispatch a `st.rerun()` from a click inside the HTML.
**Fix:** use `streamlit-extras` `stx.tabs` or a custom Streamlit component (a few JS lines) to bridge a `data-ticker` click → session_state update.
**Effort:** ~1 hour.
**Why useful:** matches the Claude Design mockup behavior; reduces friction.

### B-024 · Floating refresh / theme buttons in the header
**Current state:** buttons at bottom of page (DOM order limitation).
**Fix:** use `streamlit-elements` or a tiny custom component that POSTs to a Streamlit endpoint to mutate session_state from a fixed-position button.
**Effort:** ~1 hour.

### B-025 · TweaksPanel parity (BLUF Compact / Hidden modes)
**Source:** `tweaks-panel.jsx` in the Claude Design export has a full preferences dropdown.
**Add to sidebar (or floating panel):**
- BLUF mode: Verdict / Compact / Hidden (replace section 1)
- Density: Comfortable / Compact
- Sparkline style: Filled / Line only / Off
**Effort:** ~2 hours.

### B-026 · Empty + loading state design
**Spec:** PRODUCT_DESIGN.md §11 mockup priorities 6 and 7.
**Empty state:** "no picks meet gates — risk-off basket" view, lists which defensive ETFs (TLT/GLD/BIL) the system would rotate to.
**Loading state:** skeleton bars where cards will appear, no spinning text-spinner.
**Effort:** ~1 hour each.

---

## 🌟 Ideas for v3+

### Universe & data
- **B-100** Add ARKK, HACK, MOO, URA, LIT, TAN, ICLN, BOTZ etc. (theme ETFs)
- **B-101** Add BITO, IBIT, ETHE for crypto exposure (different vol regime — needs separate z-score class)
- **B-102** Add mega-cap individual stocks (NVDA, AAPL, MSFT, AMZN, GOOGL, META, TSLA, etc.) in their own class
- **B-103** Add VIX, gold, oil, USD index as macro tiles in the header
- **B-104** Add a "session high / low" tile to the status row showing intraday context
- **B-105** Custom universe builder web UI (currently config-only)

### Visual / UX
- **B-110** Mobile-first responsive view (currently usable but cramped on phones)
- **B-111** Sector "spaghetti chart" — every sector's relative-strength line over 12 months, overlaid
- **B-112** Custom time-range selector in per-ticker drill-down
- **B-113** Hover preview on table rows (mini RRG dot popover)
- **B-114** State transition pulse animation when a ticker just flipped
- **B-115** Comparison view — pick 2–4 tickers, see side-by-side metrics
- **B-116** "30wMA reference line" baked into the sparklines (Weinstein context)
- **B-117** Dark / light theme custom palette options ("Solarized", "Nord", "Mono")

### Notifications & integrations
- **B-120** Email digest at 08:00 ET (LOW severity transitions)
- **B-121** Push notifications for HIGH severity (mobile install via PWA)
- **B-122** RSS / iCal feed of state transitions
- **B-123** Discord / Mattermost webhook in addition to Telegram/Slack

### Portfolio features
- **B-130** Portfolio overlay — paste CSV of holdings, see which are in WARNING / EXIT
- **B-131** P&L tracker (broker API integration — alpaca, IBKR)
- **B-132** Backtest "your trades" — run the methodology against a personal trade history

### Engineering & ops
- **B-140** Move from manual git commits to GitHub Actions auto-deploy to Pi
- **B-141** Add docker-compose for easier local development
- **B-142** Unit tests for data/indicators/flow/scoring — DONE in `backlog-stepwise-qa`; pytest harness covers pure modules before provider integration.
- **B-143** Parallelize indicator computations (currently sequential per-ticker)
- **B-144** Local DuckDB store for OHLC (skip yfinance refetch on Pi reboot)
- **B-145** Structured logging (JSON logs) + log shipping to a free Logflare/Grafana endpoint
- **B-146** Graceful degradation when yfinance rate-limits (cached fallback, banner)
- **B-147** Streamlit performance audit (which sections re-render unnecessarily on theme toggle)
- **B-148** Migration from 32-bit Pi 2 (retired) to Pi 5 — DONE ✅

### Documentation
- **B-150** Auto-generated component-doc page (Storybook-style) for the dashboard's React-equivalent components
- **B-151** "How to add a sector / indicator / pillar" tutorial
- **B-152** Public methodology landing page on the domain root (separate from the dashboard)

---

## Open product questions (from PRODUCT_DESIGN.md §15)

These need a design decision before building:

1. Should sparklines on cards include a horizontal 30-week MA reference line? (B-116)
2. State pill — color-only or also icon-tagged? (Linear-style vs Bloomberg)
3. On mobile, drop the RRG entirely or render with a "fullscreen" toggle?
4. Add a portfolio overlay feature? (B-130)

---

## Process / workflow notes

- **Deploy flow:** edit on Windows → `git add/commit/push` on Windows → SSH to Pi → `git pull` → `sudo systemctl restart sector-dashboard`. Pi never pushes.
- **Branches:** currently all work lands on `main`. Consider feature branches once collaborating.
- **Auth:** GitHub Personal Access Token stored in Windows credential helper. Renew every 90 days.
- **State file:** `state.json` on the Pi is the source of truth for state-machine transitions. Don't delete unless you want to reset history.
- **Cache TTL:** 1 hour (`@st.cache_data(ttl=3600)` in `app.py`). Click the ↻ button or run `_load_data.clear()` to force refresh.

---

## Last updated

2026-05-18, end of UX-redesign + Claude Design implementation session.
