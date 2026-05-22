# Sentiment Board — Backlog

All ticket work is tracked here so nothing falls off. Ordered by category, then by impact-per-effort within each.

Status legend:
- 🔥 **Ready to deploy** — code exists, just needs push + pull + restart
- 🎯 **Next session** — well-scoped, would do this first if asked
- 💡 **Researched, not built** — spec is clear, requires focused work
- 🌟 **Idea** — captured for later, may or may not pursue

## Completed in `backlog-stepwise-qa`

### B-001 · HTML render fix for action cards (BLUF) - IMPLEMENTED
**Status:** `_md()` HTML wrapper is implemented and deployed with the dashboard branch.
**File:** `app.py`.
**Behavior:** wrapper strips leading whitespace before calling `st.markdown(..., unsafe_allow_html=True)` so indented HTML inside f-strings is not rendered as a markdown code block.
**Evidence:** verified through the current full pytest/static suite and repeated Pi HTTP smoke checks on the deployed `backlog-stepwise-qa` branch.

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

### B-111 - Sector spaghetti chart - IMPLEMENTED
**Status:** a US sector relative-strength spaghetti chart is implemented in `backlog-stepwise-qa`.
**Files:** `src/visuals.py`, `tests/test_visuals.py`, `tests/test_sector_spaghetti_app_static.py`, `app.py`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** the chart overlays all available US sector ETFs versus SPY over the latest 252 trading days, normalizes every line to 100 at the start of the window, sorts traces by latest relative strength, and renders after the RRG section.
**Safety:** uses already-loaded dashboard OHLCV only; no new fetch path, no scoring changes, no state writes, and no persistence.
**Evidence:** `docs/superpowers/plans/2026-05-21-b111-sector-spaghetti-chart.md`.
**Residual risk:** static and pure helper tests verify behavior; browser screenshot QA should be added when browser tooling is available.

### B-112 - Custom time-range selector in per-ticker drill-down - IMPLEMENTED
**Status:** a per-ticker drill-down chart range selector is implemented in `backlog-stepwise-qa`.
**Files:** `src/visuals.py`, `tests/test_visuals.py`, `tests/test_drill_range_app_static.py`, `app.py`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** the drill-down exposes `3M`, `6M`, `1Y`, `3Y`, and `MAX` ranges. The selected range clips the visible price/30wMA, CMF, and OBV chart windows by the latest available data date while rolling indicators keep the full loaded OHLCV warmup.
**Safety:** uses existing in-memory OHLCV only; no provider fetch, scoring, alerting, state-machine, or persistence behavior changes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b112-drill-time-range-selector.md`.
**Residual risk:** `MAX` means all data already loaded by the dashboard run, currently bounded by the app's configured OHLCV payload; screenshot-level browser QA should be added when browser tooling is available.

### B-113 - Hover preview on table rows - IMPLEMENTED
**Status:** desktop hover previews are implemented for full matrix ticker rows in `backlog-stepwise-qa`.
**Files:** `src/table_preview.py`, `tests/test_table_preview.py`, `tests/test_table_hover_preview_static.py`, `app.py`, `static/style.css`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** hovering a ticker row in the full 7-pillar matrix reveals a compact RRG preview card with ticker, quadrant, mini RRG dot, RS-ratio, RS-momentum, S-score, and F-score.
**Safety:** uses already-computed scored-row fields only; no JavaScript, provider fetch, scoring, alerting, state-machine, or persistence behavior changes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b113-table-hover-preview.md`.
**Residual risk:** CSS-only hover behavior is covered by static tests and HTTP smoke; screenshot-level browser QA should be added when browser tooling is available.

### B-114 - State transition pulse animation - IMPLEMENTED
**Status:** transition pulse animation is implemented for recent alert rows and active pick cards in `backlog-stepwise-qa`.
**Files:** `src/transition_pulse.py`, `tests/test_transition_pulse.py`, `tests/test_transition_pulse_app_static.py`, `app.py`, `static/style.css`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** tickers with transitions dated today in the existing state-machine transition log receive a `pulse-transition` class. Alert rows and matching active pick cards briefly pulse using the new state color.
**Safety:** visual-only CSS/markup change; no provider fetch, scoring, alert delivery, state-machine, or persistence behavior changes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b114-state-transition-pulse.md`.
**Residual risk:** static and pure helper tests verify class wiring; screenshot-level browser animation QA should be added when browser tooling is available.

### B-115 - Comparison view - IMPLEMENTED
**Status:** a 2-4 ticker side-by-side comparison view is implemented in `backlog-stepwise-qa`.
**Files:** `src/comparison_view.py`, `tests/test_comparison_view.py`, `tests/test_comparison_view_app_static.py`, `app.py`, `static/style.css`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** a capped `COMPARE TICKERS` multiselect renders compact cards for state, class, S/F, momentum, Weinstein stage, RRG quadrant, class rank, selection flag, and veto status.
**Safety:** read-only UI from the current scored dataframe; no provider fetch, scoring, alerting, state-machine, or persistence behavior changes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b115-comparison-view.md`.
**Residual risk:** static and pure helper tests verify rendering logic; screenshot-level responsive browser QA should be added when browser tooling is available.

### B-116 - 30wMA reference line in sparklines - IMPLEMENTED
**Status:** pick-card sparklines now include a 30-week moving-average reference line when enough weekly history is loaded in `backlog-stepwise-qa`.
**Files:** `src/visuals.py`, `tests/test_visuals.py`, `app.py`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** `svg_sparkline()` computes the latest weekly 30wMA from loaded daily closes, folds it into the SVG y-scale, and renders a subtle dashed horizontal line before the price path.
**Safety:** visual-only helper change using already-loaded OHLCV; no provider fetch, scoring, alerting, state-machine, or persistence behavior changes.
**Evidence:** `docs/superpowers/plans/2026-05-21-b116-sparkline-30wma-reference.md`.
**Residual risk:** SVG helper tests verify markup and warmup behavior; screenshot-level card QA should be added when browser tooling is available.

### B-117 - Custom dashboard palettes - IMPLEMENTED
**Status:** Solarized, Nord, and Mono palette options are implemented in `backlog-stepwise-qa`.
**Files:** `src/preferences.py`, `src/run_journal.py`, `tests/test_preferences.py`, `tests/test_view_preferences_static.py`, `tests/test_run_journal.py`, `tests/test_run_journal_app_static.py`, `app.py`, `static/style.css`, `README.md`, `docs/PRODUCT_DESIGN.md`.
**Behavior:** `VIEW OPTIONS` now includes a `Palette` radio with `Default`, `Solarized`, `Nord`, and `Mono`. The app renders selected palette variables into the page CSS and also writes `data-palette` on the document root for traceability while preserving the dark/light theme toggle.
**Safety:** visual-only preference/CSS change; no provider fetch, scoring, alerting, or state-machine behavior changes. A stable run-journal fingerprint prevents palette/theme/density reruns from appending duplicate methodology runs.
**Evidence:** `docs/superpowers/plans/2026-05-21-b117-custom-palettes.md`.
**Residual risk:** static tests verify palette wiring and token presence; screenshot-level palette QA should be added when browser tooling is available.

### B-011 · Build backtest harness (academic-rigorous, 2–3 days)
**Status:** deterministic pandas/numpy accounting core, historical methodology target-builder, methodology-backed manual report output, historical simulation evidence, full narrative methodology report, notebook inspection guide, in-sample/out-of-sample metrics, acceptance-gate evidence, dashboard artifact surfacing with normalized equity and drawdown charts, optional Massive OHLCV ingestion, methodology-state artifact export, and fast live-data smoke mode implemented in `backlog-stepwise-qa`; manual runner available via `python scripts/run_backtest.py`, with quick provider validation via `python scripts/run_backtest.py --live-smoke`.
**Tooling:** pandas/numpy core now; optional `vectorbt` adapter remains a future parity layer after deterministic accounting stays green.
**Latest slice:** the manual runner now writes `docs/backtest_methodology_report.md` with narrative research sections and metadata hash coverage, and `notebooks/backtest_methodology_report.ipynb` provides a lightweight artifact inspection guide without embedding secrets or rerunning network calls by default. Earlier slice: the manual runner summarizes the historical methodology simulation with rebalance count, state ticker count, selected ticker count, state transition count, and state transitions per ticker-year; acceptance gates use that simulated transition rate instead of a `0.0` placeholder. Earlier slice: the dashboard Backtest Lab transforms the verified `docs/backtest_equity.csv` artifact into normalized equity and drawdown charts, so methodology and benchmark paths can be compared from the same base and by underwater depth. Earlier slice: `scripts/run_backtest.py --live-smoke` fetches the required B-011 ticker set over a short period, validates that live OHLCV is available, and exits without writing report/equity/metadata artifacts or running the expensive full historical target loop. Earlier slice: the manual report now prints the evidence/rule behind each acceptance gate, including OOS Sharpe, OOS drawdown versus 75% of equal-weight OOS drawdown, OOS annualized turnover, and state-transition limits. Earlier slice: the report includes full-period, in-sample, and out-of-sample metrics, and acceptance gates use the strategy and equal-weight benchmark out-of-sample metrics with `2015-01-01` as the current OOS boundary. Earlier slice: `src.data.fetch_ohlcv()` supports `provider="massive"` via Massive aggregate bars and `provider="auto"` to prefer Massive when `MASSIVE_API_KEY` is configured, while keeping yfinance as the default. `scripts/run_backtest.py` uses the historical methodology target builder as the strategy path, includes `BIL` for Antonacci absolute momentum, and compares the methodology equity curve against 60/40 and equal-weight sectors. The dashboard Backtest Lab displays `docs/backtest_report.md` and chart views from `docs/backtest_equity.csv` when those manual artifacts exist and match `docs/backtest_metadata.json`; it does not run backtests on page load. Earlier slice: `build_historical_methodology_targets()` accepts preloaded OHLCV, slices each rebalance snapshot without lookahead, uses pure scoring modules, converts selected tickers to target weights, records states via `decide_state()`, avoids `apply_state_machine()` / `state.json` writes, and forces provider-backed ETF flow neutral to avoid current-data leakage.
**Deliverables per §8 of methodology:**
- CAGR, Sharpe, Sortino, max drawdown, Calmar
- Turnover, transaction cost sensitivity (3/5/10 bps)
- Compare to 60/40 SPY/AGG + equal-weight 11-sector benchmark
- Acceptance gates: OOS Sharpe ≥ 0.7, max DD ≤ 75% of benchmark
**Output:** manual summary report, full methodology report, simulation metadata, notebook inspection guide, equity chart artifact, and `docs/backtest_states.csv` methodology-state artifact for B-132 personal trade-history alignment; dashboard Backtest Lab reads the summary/equity artifacts when present and renders normalized equity plus drawdown views.
**Provider evidence:** Massive short live-data smoke was validated locally and on AHADPI5 on 2026-05-22 with `OHLCV_PROVIDER=massive python scripts/run_backtest.py --live-smoke --smoke-period 2mo`; all 14 required B-011 tickers were available and no artifacts were written.
**Residual risk:** refresh long-window evidence after provider schemas change or material data availability changes.

## Implemented with config / live-validation pending

### B-021 · Telegram / Slack alerting on state transitions — IMPLEMENTED / KEYS PENDING
**Status:** Telegram bot and Slack webhook channels are implemented in `backlog-stepwise-qa`; live validation awaits alert secrets.
**Files:** `src/alerts.py`, `src/scoring.py`, `tests/test_alerts.py`, `tests/test_scoring.py`, `.streamlit/secrets.toml.example`, `README.md`.
**Activation:** leave `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `SLACK_WEBHOOK_URL` unset to disable network calls. Configure Telegram and/or Slack secrets to enable delivery.
**Behavior:** `apply_state_machine()` persists `state.json` and the transition log before sending alerts. Provider failures are swallowed so scoring does not fail because an alert endpoint is down.
**Deferred:** Pushover, retry/backoff, dedup, and macro-channel alerts remain future backlog work.

### B-120 · Email digest at 08:00 ET — IMPLEMENTED / SMTP CONFIG PENDING
**Status:** LOW-severity daily email digest helpers and script entry point are implemented in `backlog-stepwise-qa`; live delivery awaits SMTP secrets and a Pi cron/systemd schedule.
**Files:** `src/alerts.py`, `src/scoring.py`, `scripts/send_email_digest.py`, `tests/test_alerts.py`, `tests/test_scoring.py`, `tests/test_email_digest_script.py`, `.streamlit/secrets.toml.example`, `README.md`.
**Activation:** leave `SMTP_HOST` and/or `EMAIL_DIGEST_TO` unset to disable network calls. Configure SMTP secrets, then schedule `./.venv/bin/python scripts/send_email_digest.py` for `08:00 America/New_York`.
**Behavior:** the digest filters yesterday's transitions in US/Eastern time, excludes immediate HIGH states (`EXIT`, `BEARISH_STAGE_4`), sends one plain-text email when configured, and returns `email_digest=skipped` when there is nothing to send or SMTP is unavailable.
**Evidence:** `docs/superpowers/plans/2026-05-21-b120-email-digest.md`.
**Residual risk:** unit tests mock SMTP; live SMTP validation and scheduler enablement remain environment configuration tasks.

### B-122 · RSS / iCal feed of state transitions — IMPLEMENTED / PUBLISH CONFIG PENDING
**Status:** RSS and iCal transition feed generation is implemented in `backlog-stepwise-qa`; public publishing/sync is left to deployment configuration.
**Files:** `src/transition_feeds.py`, `scripts/export_transition_feeds.py`, `tests/test_transition_feeds.py`, `tests/test_export_transition_feeds_script.py`, `.gitignore`, `README.md`.
**Activation:** run `./.venv/bin/python scripts/export_transition_feeds.py` on the Pi. Generated files are `data/feeds/transitions.rss` and `data/feeds/transitions.ics`.
**Behavior:** reads the persisted transition log, normalizes transition feed items, writes RSS 2.0 newest-first items and iCal all-day events, and escapes XML/iCal text.
**Evidence:** `docs/superpowers/plans/2026-05-21-b122-transition-feeds.md`.
**Residual risk:** tests verify artifact generation and formatting; external feed hosting/subscription is not configured yet. iCal line folding and corrupted-date hardening remain future compatibility polish.

### B-123 · Discord / Mattermost webhooks — IMPLEMENTED / WEBHOOK CONFIG PENDING
**Status:** Discord and Mattermost transition webhook routes are implemented in `backlog-stepwise-qa`; live validation awaits webhook URLs.
**Files:** `src/alerts.py`, `tests/test_alerts.py`, `.streamlit/secrets.toml.example`, `README.md`.
**Activation:** leave `DISCORD_WEBHOOK_URL` and `MATTERMOST_WEBHOOK_URL` unset to disable network calls. Configure either URL in Streamlit secrets or environment variables to enable delivery.
**Behavior:** after `apply_state_machine()` persists transitions, configured Discord and Mattermost webhooks receive the same transition text as Slack. Discord uses the normal `content` payload; Mattermost uses the Slack-compatible `text` payload. Provider failures are swallowed so scoring remains non-blocking.
**Evidence:** `docs/superpowers/plans/2026-05-21-b123-discord-mattermost-webhooks.md`.
**Residual risk:** unit tests mock webhook delivery; live provider validation remains a configuration task.

### B-022 · FRED macro overlay — IMPLEMENTED / PI LIVE VALIDATED
**Status:** FRED-backed macro classifier and deterministic tests implemented in `backlog-stepwise-qa`; live validation passed on AHADPI5 after `FRED_API_KEY` was configured.
**Files:** `src/fred_data.py`, `src/macro.py`, `tests/test_fred_data.py`, `tests/test_macro.py`.
**Series:** `INDPRO`, `T10Y2Y`, `T10Y3M`, `UNRATE`, `NFCI`, `RECPROUSM156N`, `BAMLH0A0HYM2`.
**Impact:** upgrades cycle phase from coarse 2-signal fallback to a tested FRED-backed Stovall/Fidelity-style 4-phase classifier once the free key is configured.
**Evidence:** AHADPI5 fetched all 7 current FRED series on 2026-05-22 and returned `FRED_PHASE=MID` with note `INDPRO YoY +1.4%; curve +0.49`.
**Expansion candidates:** see `docs/FRED_DATA_OPPORTUNITIES.md` for additional rates, inflation, liquidity, growth, credit, stress, and commodity series validated or triaged from FRED.

### B-154 · Expanded FRED macro context + journal snapshot — IMPLEMENTED
**Status:** read-only grouped FRED macro context and B-153 journal metadata snapshot are implemented in `backlog-stepwise-qa`.
**Files:** `src/macro_tiles.py`, `app.py`, `static/style.css`, `tests/test_macro_tiles.py`, `tests/test_macro_tiles_app_static.py`, `tests/test_run_journal_app_static.py`, `docs/FRED_DATA_OPPORTUNITIES.md`, `docs/superpowers/plans/2026-05-22-b154-fred-macro-context-journal.md`.
**Behavior:** the dashboard renders grouped FRED rows for rates, inflation, liquidity, growth, credit, and commodities from the already-cached FRED payload; the FRED fetch list now covers every grouped context series. Missing series render as `DATA PENDING`. The same JSON-safe snapshot is stored in run-journal metadata as `fred_macro_snapshot` for later debrief/backtest analysis.
**Safety:** read-only context only; no scoring, state-machine, alert, provider-flow, or veto logic changes.

### B-155 · Macro-conditioned debrief summaries — IMPLEMENTED
**Status:** FRED snapshot metadata is now used by the B-153 debrief engine to summarize recommendation outcomes by macro condition.
**Files:** `src/run_debrief.py`, `tests/test_run_debrief.py`, `app.py`, `tests/test_run_debrief_dashboard_static.py`, `src/component_docs.py`, `README.md`, `docs/FRED_DATA_OPPORTUNITIES.md`, `docs/superpowers/plans/2026-05-22-b155-macro-conditioned-debrief.md`.
**Behavior:** each debrief record carries run metadata, and `summarize_debriefs_by_macro_condition()` buckets matured outcomes by FRED series, group, label, condition (`rising`, `falling`, `flat`, or YoY sign fallback), action, and horizon. The dashboard Debrief lab shows an optional Macro-conditioned outcomes table when journaled runs contain `fred_macro_snapshot` metadata.
**Safety:** analysis-only; no scoring, state-machine, alerting, provider fetching, credential handling, or recommendation logic changes.

### B-156 · FRED macro backtest variants — IMPLEMENTED
**Status:** opt-in B-011 macro-conditioned exposure variants are implemented in `backlog-stepwise-qa`.
**Files:** `src/backtest.py`, `scripts/run_backtest.py`, `tests/test_backtest.py`, `tests/test_run_backtest_script.py`, `README.md`, `docs/FRED_DATA_OPPORTUNITIES.md`, `docs/superpowers/plans/2026-05-22-b156-fred-macro-backtest-variants.md`.
**Behavior:** `python scripts/run_backtest.py --macro-variants` fetches historical FRED series when configured and adds analysis-only variant rows for curve-falling, high-yield-spread-rising, and stress-rising defensive filters. The variant engine aligns macro observations with forward-fill only, so later macro releases cannot affect earlier rebalance decisions. Normal manual backtests do not fetch FRED unless the flag is used.
**Safety:** research/reporting only; no live scoring, state-machine, alerting, provider-flow, veto, portfolio, or broker behavior changes.

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

## Evidence-gated research backlog

### B-157 · Full FRED historical validation report — IMPLEMENTED
**Status:** B-157 is implemented and live-run on AHADPI5 with Massive OHLCV plus configured FRED history.
**Files:** `src/backtest.py`, `scripts/run_backtest.py`, `tests/test_backtest.py`, `tests/test_run_backtest_script.py`, `docs/fred_macro_validation_report.md`, `docs/fred_macro_validation_summary.csv`, `docs/backtest_metadata.json`.
**Evidence:** `OHLCV_PROVIDER=massive ./.venv/bin/python scripts/run_backtest.py --macro-variants` on AHADPI5 generated the dated FRED validation report at 2026-05-22T07:22:03Z. The corrected run bypassed the OHLCV cache, fetched all 14 required tickers from Massive, used Massive OHLCV from 2018-06-19 to 2026-05-21, applied conservative FRED availability lags, used a 2024-01-05 walk-forward OOS split because the fixed 2015 split predates available Massive history, and returned 20 FRED series.
**Result:** no FRED macro rule is promoted. `BAMLH0A0HYM2` HY-spread-rising, `STLFSI4` stress-rising, and `T10Y2Y` curve-falling defensive variants are all labeled `needs more testing`. No variant earned a `candidate` label.
**Safety:** research only; no scoring, state-machine, alert, provider-flow, veto, recommendation, broker, or criteria-value changes.

### B-158 · FRED evidence gate for live promotion — 💡 RESEARCHED, NOT BUILT
**Purpose:** promote FRED-derived criteria only if a future B-157-style validation shows robust historical improvement over the current methodology.
**Scope:** define the exact criteria values, macro filters, or veto rules to change from the B-157 evidence; add deterministic tests, documentation, and A/B comparison against the current methodology.
**Current gate:** blocked by the 2026-05-22 B-157 report because no tested rule earned a `candidate` label.
**Acceptance:** the implementation plan cites a validation report with at least one `candidate`, lists the evidence thresholds used for promotion, includes regression coverage for both promoted and rejected rules, and documents rollback behavior.
**Safety:** no FRED macro rule can enter live scoring, veto logic, alerts, recommendations, or dashboard decision text until the B-157 evidence gate passes and is reviewed.

### B-159 · Massive historical provider-data backtest variants — 🎯 NEXT SESSION
**Purpose:** use Massive (formerly Polygon) historical data to validate algorithm improvements and criteria values the same way B-157 validates FRED macro rules.
**Scope:** compare default/yfinance OHLCV backtests against Massive aggregate bars, then evaluate any timestamped Massive provider features that can be aligned as-of, such as trade-tape or block-trade signals.
**Acceptance:** save a dated report that documents which Massive endpoints/data sets were actually available, the historical coverage by ticker/date, baseline-vs-Massive metric differences, parameter sweeps for provider-derived criteria, and leakage/survivorship controls.
**Safety:** provider-backed historical flow remains neutral unless timestamped as-of provider snapshots exist; no Massive-derived rule can change live scoring, vetoes, alerts, recommendations, or Pillar 7 weights from this ticket alone.

### B-160 · Massive evidence gate for live promotion — 💡 RESEARCHED, NOT BUILT
**Purpose:** promote Massive-derived criteria only if B-159 shows durable improvement and no data-leakage issue.
**Scope:** convert validated Massive historical findings into explicit candidate changes for Pillar 7 weights, thresholds, provider-flow features, or alert/veto rules.
**Acceptance:** the promotion plan cites the B-159 report, includes before/after backtest tables, deterministic tests for threshold behavior, live-provider failure-mode tests, and documentation of the activation flags or configuration required.
**Safety:** no Massive/provider-flow rule can enter live scoring, veto logic, alerts, recommendations, or dashboard decision text until the B-159 evidence gate passes and is reviewed.

---

## Completed v3+ ideas

### Universe & data

### Visual / UX

### Notifications & integrations
#### B-121 · Push notifications for HIGH severity (mobile install via PWA) — IMPLEMENTED / VAPID CONFIG PENDING
**Status:** static PWA alert shell, service worker, high-severity notification feed writer, and best-effort Web Push sender seam are implemented in `backlog-stepwise-qa`; live browser push delivery awaits VAPID keys and subscription capture.
**Files:** `src/pwa_push.py`, `scripts/send_pwa_push_notifications.py`, `public/pwa.html`, `public/pwa-sw.js`, `public/manifest.webmanifest`, `public/notification-feed.json`, `tests/test_pwa_push.py`, `tests/test_remaining_backlog_app_static.py`, `.gitignore`, `.dockerignore`, `README.md`, `docs/BACKLOG.md`.
**Activation:** configure `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL`, optional `PWA_DASHBOARD_URL`, and local browser subscriptions in `data/pwa_push_subscriptions.json`; then run `./.venv/bin/python scripts/send_pwa_push_notifications.py` after dashboard state transitions are recorded.
**Behavior:** only `EXIT` and `BEARISH_STAGE_4` transitions produce HIGH-severity payloads. The public PWA assets contain no API keys, local state files, run-journal content, or account data.
**Residual risk:** browser subscription capture and production VAPID delivery still require environment configuration and mobile-browser validation.

### Portfolio features
#### B-131 · P&L tracker — IMPLEMENTED / BROKER API CONFIG PENDING
**Status:** local holdings-based unrealized P&L tracker is implemented in `backlog-stepwise-qa`; live broker API sync remains a credential/config integration layer.
**Files:** `src/pl_tracker.py`, `tests/test_pl_tracker.py`, `app.py`, `tests/test_remaining_backlog_app_static.py`, `README.md`, `docs/BACKLOG.md`.
**Behavior:** uploaded/saved holdings with shares and cost basis are joined to the dashboard's already-loaded prices, then surfaced as cost, value, unrealized P&L, P&L %, and missing-input diagnostics. No broker API calls, order placement, cloud sync, state-machine writes, or scoring changes were added.
**Residual risk:** Alpaca/IBKR import adapters should be added only after broker credentials and account scope are available.

#### B-132 · Backtest "your trades" — IMPLEMENTED
**Status:** personal trade-history methodology alignment is implemented in `backlog-stepwise-qa`.
**Files:** `src/personal_trades.py`, `tests/test_personal_trades.py`, `scripts/run_backtest.py`, `tests/test_run_backtest_script.py`, `app.py`, `tests/test_remaining_backlog_app_static.py`, `README.md`, `docs/BACKLOG.md`.
**Behavior:** `scripts/run_backtest.py` now emits `docs/backtest_states.csv` with historical methodology states. The dashboard accepts a CSV/XLS/XLSX trade-history upload and compares each BUY/SELL against the latest methodology state at or before the trade date, reporting aligned, against-method, and unavailable counts. Uploaded trades are in-memory only and are not persisted.
**Residual risk:** this is methodology-alignment evidence, not tax/accounting-grade realized P&L or broker reconciliation.
#### B-133 · Save named watchlists / portfolios locally — IMPLEMENTED
**Status:** named watchlists and portfolios can be saved, loaded, and deleted from the dashboard using a local JSON store.
**Files:** `src/saved_inputs.py`, `tests/test_saved_inputs.py`, `tests/test_saved_inputs_app_static.py`, `app.py`, `.gitignore`, `.dockerignore`, `README.md`, `docs/superpowers/plans/2026-05-21-b133-saved-inputs.md`.
**Behavior:** custom-universe ticker lists and portfolio holdings are persisted to `data/saved_inputs.json`, ignored by git/docker, then loaded back into the existing read-only analysis paths. No broker API, cloud sync, scoring recomputation, provider fetch from saved inputs, or state-machine writes were added.
**Residual risk:** local JSON persistence is single-user and file-based; concurrent browser sessions editing the same saved item are last-write-wins.

### Engineering & ops
#### B-140 · GitHub Actions auto-deploy to Pi — IMPLEMENTED / SECRETS CONFIG PENDING
**Status:** GitHub Actions workflow and operator guide are implemented in `backlog-stepwise-qa`; live runs await GitHub repo secrets and a Pi SSH endpoint reachable by GitHub.
**Files:** `.github/workflows/deploy-pi.yml`, `tests/test_github_actions_deploy_static.py`, `docs/DEPLOY_GITHUB_ACTIONS_PI.md`, `README.md`, `docs/BACKLOG.md`.
**Activation:** configure `PI_HOST`, `PI_USER`, `PI_SSH_KEY`, `PI_KNOWN_HOSTS`, `PI_REPO_PATH`, and optional `PI_SERVICE_NAME` as GitHub repository secrets. The workflow runs on push to `backlog-stepwise-qa` and via manual dispatch.
**Behavior:** SSHes to the Pi with a pinned host key, fast-forwards the branch, syncs `requirements.txt`, runs full pytest on the Pi, restarts the Streamlit service by terminating its current `MainPID`, and polls `http://127.0.0.1:8501/?ticker=XLK` for HTTP `200`.
**Evidence:** `docs/superpowers/plans/2026-05-21-b140-github-actions-pi-deploy.md`.
**Residual risk:** not live-validated from GitHub Actions because repo secrets and a GitHub-reachable SSH endpoint are still configuration tasks.

#### B-141 · Docker Compose for local development — IMPLEMENTED
**Status:** Dockerfile, compose service, and static coverage are implemented in `backlog-stepwise-qa`.
**Files:** `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `tests/test_docker_compose_static.py`, `README.md`, `docs/BACKLOG.md`.
**Activation:** run `docker compose up --build`, then open `http://127.0.0.1:8501/?ticker=XLK`.
**Behavior:** builds a Python 3.12 Streamlit container, exposes port `8501`, defaults to yfinance for free local data, mounts `.streamlit/` and `data/`, writes container state to `data/state.json`, and adds an HTTP healthcheck.
**Residual risk:** static tests verify scaffold contents; Docker runtime build was attempted locally but Docker Desktop/daemon was unavailable, so runtime container startup still needs validation on a Docker-enabled machine.

- **B-142** Unit tests for data/indicators/flow/scoring — DONE in `backlog-stepwise-qa`; pytest harness covers pure modules before provider integration.
#### B-143 · Parallel indicator computations — IMPLEMENTED
**Status:** `compute_all_indicators()` now computes eligible ticker rows through a bounded `ThreadPoolExecutor` by default while preserving deterministic ticker order.
**Files:** `src/indicators.py`, `tests/test_indicators.py`, `docs/superpowers/plans/2026-05-21-b143-parallel-indicators.md`.
**Behavior:** excludes the same T-bill/index tickers as before, uses up to `min(8, os.cpu_count(), eligible_ticker_count)` workers by default, accepts `max_workers=1` for serial debugging, and keeps the app/backtest call sites unchanged.
**Residual risk:** tests patch the executor contract and verify output order; they do not benchmark real dashboard latency across a large live universe.

#### B-144 · Local DuckDB OHLCV store — IMPLEMENTED
**Status:** `fetch_ohlcv()` now reads a persistent local DuckDB cache before provider calls and writes successful provider frames back to cache.
**Files:** `src/ohlcv_store.py`, `src/data.py`, `tests/test_ohlcv_store.py`, `requirements.txt`, `docs/superpowers/plans/2026-05-21-b144-duckdb-ohlcv-cache.md`.
**Behavior:** cache defaults to `data_cache/ohlcv.duckdb`, can be moved with `OHLCV_CACHE_PATH`, can be disabled with `OHLCV_CACHE_ENABLED=false`, serves only period-covering fresh daily data, fetches only cache misses, and preserves the existing de-duplicated ticker order.
**Residual risk:** cache freshness uses a small daily-data tolerance and is covered by unit tests; it has not yet been load-tested with the full live universe over many months of Pi writes.

#### B-145 · Structured JSON logging — IMPLEMENTED
**Status:** app-level JSONL logging and optional best-effort HTTP log shipping are implemented in `backlog-stepwise-qa`.
**Files:** `src/structured_logging.py`, `tests/test_structured_logging.py`, `tests/test_structured_logging_app_static.py`, `app.py`, `.gitignore`, `.dockerignore`, `.streamlit/secrets.toml.example`, `docs/superpowers/plans/2026-05-21-b145-structured-logging.md`.
**Behavior:** writes compact JSON lines to `data/logs/app.jsonl` by default, keeps Streamlit reruns idempotent by replacing prior structured handlers, logs dashboard run-journal success/failure events, and optionally posts the same JSON payload to `LOG_SHIP_URL` with `LOG_SHIP_TOKEN` bearer auth.
**Residual risk:** shipping is a generic JSON HTTP endpoint rather than a provider-specific Logflare/Loki schema; endpoint mapping may need a small adapter once the target service is chosen.

#### B-146 · yfinance stale-cache fallback banner — IMPLEMENTED
**Status:** `fetch_ohlcv_result()` now exposes provider/cache metadata while `fetch_ohlcv()` keeps the original dict-returning contract.
**Files:** `src/data.py`, `src/ohlcv_store.py`, `app.py`, `static/style.css`, `tests/test_data.py`, `tests/test_ohlcv_store.py`, `tests/test_provider_fallback_app_static.py`, `docs/superpowers/plans/2026-05-21-b146-yfinance-fallback.md`.
**Behavior:** fresh DuckDB cache still serves first, provider misses still fetch normally, and yfinance gaps can fall back to explicit stale cached OHLCV with a compact dashboard provider-status banner. Symbols still missing after provider/cache fallback are surfaced in result warnings for operator visibility.
**Residual risk:** the banner has static coverage and unit coverage for stale yfinance fallback; it has not yet been screenshot-tested across all responsive breakpoints.
#### B-147 · Streamlit performance audit — IMPLEMENTED
**Status:** dashboard reruns now emit a `dashboard_performance_audit` structured log event with rerun classification, changed session-state keys, provider, scored row count, and per-section timings.
**Files:** `src/performance_audit.py`, `app.py`, `tests/test_performance_audit.py`, `tests/test_performance_audit_app_static.py`, `docs/superpowers/plans/2026-05-21-b147-streamlit-performance-audit.md`.
**Behavior:** theme, density, BLUF mode, sparkline style, and palette changes classify as `visual_only`; non-visual controls classify as `interactive`. The app times `load_data`, `compute_signals`, and each major render section without changing provider fetch, scoring, state-machine, or alert behavior.
**Residual risk:** this ticket records audit evidence but does not yet skip expensive work on visual-only reruns; use the collected logs to choose the next optimization safely.
- **B-148** Migration from 32-bit Pi 2 (retired) to Pi 5 — DONE ✅

- **B-153** Run journal + debrief engine — IMPLEMENTED through B-153.4; the app now has an append-only local SQLite run journal, dashboard scoring/BLUF auto-recording, a pure forward-outcome debrief engine, and dashboard debrief surfacing. Future polish can add richer exported reports.

### Documentation
#### B-150 · Auto-generated component-doc page — IMPLEMENTED
**Status:** a generated Storybook-style component inventory is implemented in `backlog-stepwise-qa`.
**Files:** `src/component_docs.py`, `tests/test_component_docs.py`, `tests/test_component_docs_app_static.py`, `app.py`, `static/style.css`, `README.md`, `docs/BACKLOG.md`.
**Behavior:** the dashboard exposes a collapsed Component Docs panel generated from a pure metadata catalog. Each render section lists its source function, inputs, UI states, and QA coverage; the panel does not fetch OHLCV, recompute indicators, or mutate the state machine.
**Residual risk:** this is a Streamlit-native reference panel rather than a separate external Storybook server.
#### B-151 · How to add a sector / indicator / pillar tutorial — IMPLEMENTED
**Status:** an extension tutorial is implemented in `backlog-stepwise-qa`.
**Files:** `docs/how-to-add-sector-indicator-pillar.md`, `tests/test_methodology_tutorial_static.py`, `README.md`, `docs/BACKLOG.md`.
**Behavior:** the tutorial documents how to extend universe classes, indicators, and pillars while keeping methodology docs, component docs, provider safety, state-machine safety, and verification commands aligned.
#### B-152 · Public methodology landing page on domain root — IMPLEMENTED
**Status:** a static public methodology landing page and Pi/static-route deployment docs are implemented in `backlog-stepwise-qa`.
**Files:** `public/index.html`, `public/methodology.html`, `public/assets/methodology.css`, `public/assets/methodology-preview.png`, `public/robots.txt`, `public/sitemap.xml`, `public/_headers`, `systemd/methodology-landing.service`, `docs/PUBLIC_METHODOLOGY_LANDING.md`, `docs/DEPLOY_CLOUDFLARE_TUNNEL.md`, `config/cloudflared-config.yml.example`, `tests/test_public_landing_static.py`, `tests/test_public_root_deploy_static.py`, `README.md`, `docs/BACKLOG.md`.
**Behavior:** the public root serves static methodology education on port 8500, while the dashboard remains a separate Cloudflare Access-protected Streamlit route on port 8501. The page does not expose live picks, protected dashboard content, local files, or credential references.
**Residual risk:** live public-domain routing still depends on applying the Cloudflare DNS/tunnel or Pages configuration outside the repo.

---

## Open product questions (from PRODUCT_DESIGN.md §15)

Resolved for this backlog pass:

1. State pill — remain text + color with tooltip for accessibility; no icon-only taxonomy added.
2. Mobile RRG — keep RRG available with responsive wrapping/scrolling rather than dropping it.
3. Portfolio overlay feature — resolved by B-130 read-only analyzer, B-131 local P&L tracker, B-132 personal trade alignment, and B-133 saved inputs.

---

## Process / workflow notes

- **Deploy flow:** edit on Windows → `git add/commit/push` on Windows → SSH to Pi → `git pull` → `sudo systemctl restart sector-dashboard`. Pi never pushes.
- **Branches:** currently all work lands on `main`. Consider feature branches once collaborating.
- **Auth:** GitHub Personal Access Token stored in Windows credential helper. Renew every 90 days.
- **State file:** `state.json` on the Pi is the source of truth for state-machine transitions. Don't delete unless you want to reset history.
- **Cache TTL:** 1 hour (`@st.cache_data(ttl=3600)` in `app.py`). Click the ↻ button or call `refresh_market_data(_load_data)` to force refresh.

---

## Last updated

2026-05-22, added evidence-gated FRED and Massive validation backlog.
