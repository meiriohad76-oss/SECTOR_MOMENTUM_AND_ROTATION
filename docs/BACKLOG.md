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

## Completed in `backlog-stepwise-qa`

### B-010 · Wire Massive AI to ETF primary-flow source (Pillar 7 stub #1) - IMPLEMENTED
**Status:** provider seam implemented in `backlog-stepwise-qa`; production default remains neutral until `FLOW_STUB_MODE=false`, `MASSIVE_API_KEY`, and per-ticker source URLs are configured.
**Files:** `src/flow.py`, `tests/test_flow.py`, `README.md`, `.streamlit/secrets.toml.example`.
**Activation:** configure `ETF_PRIMARY_FLOW_URL_<TICKER>` values and set `FLOW_STUB_MODE=false`.
**Notes:** ETF primary flow computes daily delta shares times current NAV over the latest 5 dated observations, divided by latest AUM. Other Pillar 7 provider stubs remain neutral until B-020.

### B-130 · Portfolio / single-stock analyzer - IMPLEMENTED
**Status:** parser, read-only holding analysis, and Streamlit UI implemented in `backlog-stepwise-qa`.
**Files:** `src/portfolio.py`, `tests/test_portfolio.py`, `app.py`, `static/style.css`, `requirements.txt`, `README.md`.
**Inputs:** single ticker text input; `.csv`, `.xlsx`, or `.xls` holdings upload with ticker/symbol aliases and optional shares, market value, weight, sector, account, and notes columns.
**Outputs:** validation errors, missing tickers, state/class exposure tables, action lists, and per-holding methodology rows using the existing scored dashboard snapshot.
**Safety:** read-only/in-memory only; no broker API, no portfolio persistence, no scoring recomputation, and no analyzer state writes.
**QA:** parser/analyzer tests cover malformed files, Excel read errors, missing/invalid tickers, numeric validation, weight inference, zero-weight handling, duplicate scored indexes, string booleans, and display formatting.

### B-012 · Cloudflare Access lockdown - VERIFIED
**Status:** public dashboard URL is protected by Cloudflare Access as of 2026-05-21.
**Evidence:** `docs/superpowers/plans/2026-05-21-b012-cloudflare-access-verification.md`.
**Observed behavior:** unauthenticated requests to `https://sentimentdashboard.ahaddashboards.uk` redirect to `ahadahad.cloudflareaccess.com/cdn-cgi/access/login/...`, include `Www-Authenticate: Cloudflare-Access`, and return a `Sign in - Cloudflare Access` page instead of the Streamlit dashboard.
**Residual risk:** rerun verification after Cloudflare policy edits; this check does not audit the allowed email list.

### B-020 · Massive / FINRA / SEC provider flow seams - IMPLEMENTED
**Status:** all four remaining Pillar 7 provider seams are implemented in `backlog-stepwise-qa` with provider-specific opt-in stub flags and fail-closed neutral fallbacks.
**Files:** `src/flow.py`, `tests/test_flow.py`, `.streamlit/secrets.toml.example`, `README.md`.
**Evidence:** `docs/superpowers/plans/2026-05-21-b020-provider-flow-status.md`.
**Implemented feeds:** Massive `/v3/trades` block-trade upside ratio, FINRA ATS weekly dark-pool percentage, FINRA consolidated short-interest delta, and SEC 13F net-buy parsing from configured data-set zip plus CUSIP mappings.
**Activation:** leave `MASSIVE_TRADES_STUB_MODE`, `FINRA_ATS_STUB_MODE`, `FINRA_SHORT_INTEREST_STUB_MODE`, and `SEC_13F_STUB_MODE` unset/`true` until each feed is configured; flip individual flags to `false` for live validation.
**QA:** `python -m pytest tests/test_flow.py -q` -> `33 passed`; `python -m pytest -q` -> `184 passed`.
**Residual risk:** live provider validation depends on configured keys/user-agent/CUSIP mappings and should be repeated after provider schema changes.

### B-100 - Theme ETF universe - IMPLEMENTED
**Status:** theme ETFs are now a first-class universe class in `backlog-stepwise-qa`.
**Files:** `src/universe.py`, `tests/test_universe.py`, `README.md`, `docs/sector-rotation-methodology.md`, `docs/PRODUCT_DESIGN.md`.
**Tickers:** `ARKK`, `HACK`, `MOO`, `URA`, `LIT`, `TAN`, `ICLN`, and `BOTZ`.
**Behavior:** `TAN` and `ICLN` moved from `US Industries` to `Themes` to avoid duplicate tickers; theme ETFs rank within their own class with `TOP_N["Themes"] == 3`.
**Evidence:** `docs/superpowers/plans/2026-05-21-b100-theme-etfs.md`.

### B-101 - Crypto exposure universe - IMPLEMENTED
**Status:** crypto exposure ETFs are now a separate universe class in `backlog-stepwise-qa`.
**Files:** `src/universe.py`, `tests/test_universe.py`, `README.md`, `docs/sector-rotation-methodology.md`, `docs/PRODUCT_DESIGN.md`.
**Tickers:** `BITO`, `IBIT`, and `ETHE`.
**Behavior:** crypto tickers rank only against each other in the `Crypto` class, with `TOP_N["Crypto"] == 1` to reflect the separate volatility regime called out in the backlog.
**Evidence:** `docs/superpowers/plans/2026-05-21-b101-crypto-exposure.md`.

### B-102 - Mega-cap stock universe - IMPLEMENTED
**Status:** mega-cap individual stocks are now a separate universe class in `backlog-stepwise-qa`.
**Files:** `src/universe.py`, `tests/test_universe.py`, `app.py`, `README.md`, `docs/sector-rotation-methodology.md`, `docs/PRODUCT_DESIGN.md`.
**Tickers:** `NVDA`, `AAPL`, `MSFT`, `AMZN`, `GOOGL`, `META`, and `TSLA`.
**Behavior:** mega-cap stocks rank only against each other in the `Mega-Cap Stocks` class, with `TOP_N["Mega-Cap Stocks"] == 3`.
**Evidence:** `docs/superpowers/plans/2026-05-21-b102-mega-cap-stocks.md`.

### B-103 - Macro context header tiles - IMPLEMENTED
**Status:** VIX, gold, oil, and USD context tiles render in the Market state header in `backlog-stepwise-qa`.
**Files:** `src/macro_tiles.py`, `tests/test_macro_tiles.py`, `tests/test_macro_tiles_app_static.py`, `app.py`, `static/style.css`.
**Symbols:** `^VIX`, `GLD`, `USO`, and `UUP`.
**Behavior:** context symbols are fetched with the dashboard OHLCV payload; missing data renders as `DATA PENDING`; macro context does not change methodology scoring or state-machine behavior.
**Evidence:** `docs/superpowers/plans/2026-05-21-b103-macro-context-tiles.md`.

### B-104 - Session high/low tile - IMPLEMENTED
**Status:** the Market state header now includes a session range tile in `backlog-stepwise-qa`.
**Files:** `src/macro_tiles.py`, `tests/test_macro_tiles.py`, `tests/test_macro_tiles_app_static.py`, `app.py`.
**Behavior:** the tile uses the latest SPY high, low, and close from the dashboard OHLCV payload; close location in the latest high/low range controls the tile tone; missing or malformed range data renders as `DATA PENDING`.
**Evidence:** `docs/superpowers/plans/2026-05-21-b104-session-range-tile.md`.

### B-105 - Custom universe builder web UI - IMPLEMENTED
**Status:** a read-only custom universe section is implemented in `backlog-stepwise-qa`.
**Files:** `src/custom_universe.py`, `tests/test_custom_universe.py`, `tests/test_custom_universe_app_static.py`, `app.py`, `static/style.css`, `README.md`.
**Inputs:** pasted ticker lists separated by comma, semicolon, whitespace, or newlines; `.csv`, `.xlsx`, or `.xls` files with ticker/symbol/holding/asset aliases.
**Behavior:** the UI validates and de-duplicates tickers, reports invalid/duplicate/missing entries, ranks matched tickers by current `S_score` inside the custom list, shows class/state count summaries and action buckets, and exposes drill buttons for matched tickers.
**Safety:** read-only/in-memory only; no OHLCV fetch from user input, no mutation of `src/universe.py`, no watchlist persistence, and no `state.json` writes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b105-custom-universe-builder.md`.

### B-110 - Mobile-first responsive view - IMPLEMENTED
**Status:** phone-width responsive guards are implemented in `backlog-stepwise-qa`.
**Files:** `app.py`, `static/style.css`, `tests/test_mobile_responsive_static.py`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** header metadata wraps, section heads stack, BLUF/action/status/pick grids collapse, alert rows simplify, full tables scroll horizontally, RRG class controls and drill buttons wrap into usable rows, custom-universe summaries stack, and narrow drill metrics collapse to one column.
**Safety:** CSS/markup-only; no scoring, data-fetch, provider, persistence, or state-machine behavior changes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b110-mobile-responsive-view.md`.
**Residual risk:** local verification includes static coverage and HTTP smoke; screenshot-level mobile browser QA should be added when Playwright or browser tooling is available in the environment.

---

## 🎯 Next-session priorities

### B-011 · Build backtest harness (academic-rigorous, 2–3 days)
**Status:** deterministic pandas/numpy accounting core, historical methodology target-builder, methodology-backed manual report output, historical simulation evidence, full narrative methodology report, notebook inspection guide, in-sample/out-of-sample metrics, acceptance-gate evidence, dashboard artifact surfacing with normalized equity and drawdown charts, optional Massive OHLCV ingestion, and fast live-data smoke mode implemented in `backlog-stepwise-qa`; manual runner available via `python scripts/run_backtest.py`, with quick provider validation via `python scripts/run_backtest.py --live-smoke`. Remaining B-011 polish is live long-window evidence capture when data/API keys are available.
**Tooling:** pandas/numpy core now; optional `vectorbt` adapter remains a future parity layer after deterministic accounting stays green.
**Latest slice:** the manual runner now writes `docs/backtest_methodology_report.md` with narrative research sections and metadata hash coverage, and `notebooks/backtest_methodology_report.ipynb` provides a lightweight artifact inspection guide without embedding secrets or rerunning network calls by default. Earlier slice: the manual runner summarizes the historical methodology simulation with rebalance count, state ticker count, selected ticker count, state transition count, and state transitions per ticker-year; acceptance gates use that simulated transition rate instead of a `0.0` placeholder. Earlier slice: the dashboard Backtest Lab transforms the verified `docs/backtest_equity.csv` artifact into normalized equity and drawdown charts, so methodology and benchmark paths can be compared from the same base and by underwater depth. Earlier slice: `scripts/run_backtest.py --live-smoke` fetches the required B-011 ticker set over a short period, validates that live OHLCV is available, and exits without writing report/equity/metadata artifacts or running the expensive full historical target loop. Earlier slice: the manual report now prints the evidence/rule behind each acceptance gate, including OOS Sharpe, OOS drawdown versus 75% of equal-weight OOS drawdown, OOS annualized turnover, and state-transition limits. Earlier slice: the report includes full-period, in-sample, and out-of-sample metrics, and acceptance gates use the strategy and equal-weight benchmark out-of-sample metrics with `2015-01-01` as the current OOS boundary. Earlier slice: `src.data.fetch_ohlcv()` supports `provider="massive"` via Massive aggregate bars and `provider="auto"` to prefer Massive when `MASSIVE_API_KEY` is configured, while keeping yfinance as the default. `scripts/run_backtest.py` uses the historical methodology target builder as the strategy path, includes `BIL` for Antonacci absolute momentum, and compares the methodology equity curve against 60/40 and equal-weight sectors. The dashboard Backtest Lab displays `docs/backtest_report.md` and chart views from `docs/backtest_equity.csv` when those manual artifacts exist and match `docs/backtest_metadata.json`; it does not run backtests on page load. Earlier slice: `build_historical_methodology_targets()` accepts preloaded OHLCV, slices each rebalance snapshot without lookahead, uses pure scoring modules, converts selected tickers to target weights, records states via `decide_state()`, avoids `apply_state_machine()` / `state.json` writes, and forces provider-backed ETF flow neutral to avoid current-data leakage.
**Deliverables per §8 of methodology:**
- CAGR, Sharpe, Sortino, max drawdown, Calmar
- Turnover, transaction cost sensitivity (3/5/10 bps)
- Compare to 60/40 SPY/AGG + equal-weight 11-sector benchmark
- Acceptance gates: OOS Sharpe ≥ 0.7, max DD ≤ 75% of benchmark
**Output:** manual summary report, full methodology report, simulation metadata, notebook inspection guide, and equity chart artifact; dashboard Backtest Lab reads the summary/equity artifacts when present and renders normalized equity plus drawdown views.
**Why second:** validates whether the methodology actually has edge before more design polish.

## 💡 Researched but not built

### B-021 · Telegram / Slack alerting on state transitions — IMPLEMENTED / KEYS PENDING
**Status:** Telegram bot and Slack webhook channels are implemented in `backlog-stepwise-qa`; live validation awaits alert secrets.
**Files:** `src/alerts.py`, `src/scoring.py`, `tests/test_alerts.py`, `tests/test_scoring.py`, `.streamlit/secrets.toml.example`, `README.md`.
**Activation:** leave `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `SLACK_WEBHOOK_URL` unset to disable network calls. Configure Telegram and/or Slack secrets to enable delivery.
**Behavior:** `apply_state_machine()` persists `state.json` and the transition log before sending alerts. Provider failures are swallowed so scoring does not fail because an alert endpoint is down.
**Deferred:** Pushover, severity-specific routing, retry/backoff, dedup, and macro-channel alerts remain future backlog work.

### B-022 · FRED macro overlay — IMPLEMENTED / KEY PENDING
**Status:** FRED-backed macro classifier and deterministic tests implemented in `backlog-stepwise-qa`; live validation awaits `FRED_API_KEY`.
**Files:** `src/fred_data.py`, `src/macro.py`, `tests/test_fred_data.py`, `tests/test_macro.py`.
**Series:** `INDPRO`, `T10Y2Y`, `T10Y3M`, `UNRATE`, `NFCI`, `RECPROUSM156N`, `BAMLH0A0HYM2`.
**Impact:** upgrades cycle phase from coarse 2-signal fallback to a tested FRED-backed Stovall/Fidelity-style 4-phase classifier once the free key is configured.

### B-023 · Click-through from cards/alerts/RRG → drill-down — IMPLEMENTED
**Status:** Native Streamlit drill buttons and `?ticker=...` deep links are implemented in `backlog-stepwise-qa`.
**Files:** `src/navigation.py`, `app.py`, `tests/test_navigation.py`, `README.md`.
**Behavior:** alert, pick, and RRG context controls update `st.session_state.drill_ticker` plus the URL query param, then rerun into the existing per-ticker drill-down.
**Deferred:** whole-card HTML clicks and Plotly dot-click capture still need a custom component or event bridge.

### B-024 · Floating refresh / theme buttons in the header — IMPLEMENTED
**Status:** Native Streamlit refresh/theme controls render immediately after the header and are fixed top-right via CSS.
**Files:** `src/controls.py`, `app.py`, `static/style.css`, `tests/test_controls.py`, `tests/test_header_controls_static.py`.
**Behavior:** refresh clears cached market data and reruns; theme toggles dark/light session state and reruns.
**Deferred:** custom component bridge and animated fetching state remain future polish.

### B-025 · TweaksPanel parity (BLUF Compact / Hidden modes) — IMPLEMENTED
**Status:** Native Streamlit `VIEW OPTIONS` expander is implemented near the header.
**Files:** `src/preferences.py`, `app.py`, `src/visuals.py`, `static/style.css`, `tests/test_preferences.py`, `tests/test_visuals.py`, `tests/test_view_preferences_static.py`.
**Controls:** BLUF mode (`Verdict`, `Compact`, `Hidden`), density (`Comfortable`, `Compact`), and sparkline style (`Filled`, `Line`, `Off`).
**Deferred:** custom floating React-style panel, persisted user profiles, and additional palettes remain future preference work.

### B-026 · Empty + loading state design — IMPLEMENTED
**Status:** dashboard-native empty and loading states are implemented in `backlog-stepwise-qa`.
**Files:** `src/ui_states.py`, `app.py`, `static/style.css`, `tests/test_ui_states.py`, `tests/test_empty_loading_states_static.py`.
**Empty state:** when no picks meet gates, the `Picks` section shows a risk-off basket focused on `TLT / GLD / BIL`, using scored state/S/F values when available and `DATA PENDING` fallbacks when not.
**Loading state:** first-page market-data fetch and indicator computation use a temporary inline skeleton placeholder; the old `st.spinner()` wrappers are removed.
**Deferred:** async fetching, stale-cache banners, provider retry UX, and custom frontend shimmer components remain future reliability/polish work.

---

## 🌟 Ideas for v3+

### Universe & data

### Visual / UX
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
- **B-131** P&L tracker (broker API integration — alpaca, IBKR)
- **B-132** Backtest "your trades" — run the methodology against a personal trade history
- **B-133** Save named watchlists / portfolios locally after B-130 read-only analyzer proves useful

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

- **B-153** Run journal + debrief engine — IMPLEMENTED through B-153.4; the app now has an append-only local SQLite run journal, dashboard scoring/BLUF auto-recording, a pure forward-outcome debrief engine, and dashboard debrief surfacing. Future polish can add richer exported reports.

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
4. Portfolio overlay feature? Resolved by B-130 read-only analyzer in `backlog-stepwise-qa`; future persistence/broker integration belongs in B-131/B-133.

---

## Process / workflow notes

- **Deploy flow:** edit on Windows → `git add/commit/push` on Windows → SSH to Pi → `git pull` → `sudo systemctl restart sector-dashboard`. Pi never pushes.
- **Branches:** currently all work lands on `main`. Consider feature branches once collaborating.
- **Auth:** GitHub Personal Access Token stored in Windows credential helper. Renew every 90 days.
- **State file:** `state.json` on the Pi is the source of truth for state-machine transitions. Don't delete unless you want to reset history.
- **Cache TTL:** 1 hour (`@st.cache_data(ttl=3600)` in `app.py`). Click the ↻ button or call `refresh_market_data(_load_data)` to force refresh.

---

## Last updated

2026-05-18, end of UX-redesign + Claude Design implementation session.
