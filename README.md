# Sector Rotation Dashboard

A Streamlit dashboard that monitors **83+ instruments across US sectors, US industries, international markets, style factors, thematic exposures, crypto exposures, and mega-cap stocks** using a 7-pillar layered methodology to identify bullish sectors and alert on bearish reversals.

> The methodology layers six peer-reviewed price pillars (cross-sectional momentum, Faber 10mo SMA, Weinstein Stage 2, Antonacci dual momentum, RRG, business cycle) with a seventh **institutional flow** pillar (CMF, OBV, MFI, RVOL, distribution days, block-trade tape, ETF creations, 13F, short interest).
>
> Full whitepaper: [`docs/sector-rotation-methodology.pdf`](docs/sector-rotation-methodology.pdf) · [`docs/sector-rotation-methodology.md`](docs/sector-rotation-methodology.md)

---

## What you get

- A **read-only portfolio / single-stock analyzer** that accepts one ticker or a CSV/XLS/XLSX holdings file and maps the input to the current methodology snapshot.
- A **read-only custom universe builder** that accepts pasted tickers or a CSV/XLS/XLSX ticker file, de-duplicates the list, and ranks matched tickers against the current methodology snapshot.
- A **responsive single-page dashboard layout** with phone-width guards for the header, section controls, alert rows, tables, drill controls, and compact action summaries.
- A **US sector relative-strength spaghetti chart** that overlays all sector ETF lines versus SPY over the last 12 months.
- A **per-ticker chart range selector** for drilling into 3M, 6M, 1Y, 3Y, or all currently loaded price/flow history.
- A **full-table hover preview** that shows a compact RRG dot card for each ticker row on desktop.
- A **single-page Streamlit app** (`app.py`) with two sections:
  - **Top:** 7-pillar heatmap — every ticker scored on every pillar, color-coded, with composite score and current state (`STAGE_2_BULLISH` / `HOLD` / `WARNING` / `EXIT` / `BEARISH_STAGE_4` / `STAGE_1_BASING`).
  - **Below:** drill-down tabs — RRG quadrant chart, cross-sectional momentum bar, institutional flow detail, state-machine transition log, per-ticker deep dive with price/CMF/OBV charts.
- A **persistent state machine** (`state.json`) so bearish transitions trigger only once and stay visible across sessions.
- A **bearish alert system** with three severity levels (WARNING → EXIT → BEARISH) plus three flow-only early warnings (distribution day, dark-pool sell, OBV/price divergence).
- **No paid feeds required for v1** — defaults to free Yahoo Finance data. Historical OHLCV can use Massive when `MASSIVE_API_KEY` is configured, and institutional-flow stubs ship pre-wired so you can drop in iShares SHO, Massive, FINRA, or SEC EDGAR feeds when ready.

## Backtest harness

B-011 adds a pure pandas/numpy backtest accounting core in `src/backtest.py`. The core is deterministic and covered by offline pytest cases for weight timing, drift, turnover, cost scenarios, benchmarks, acceptance gates, and no-lookahead historical methodology target construction.

The historical target builder accepts preloaded OHLCV, slices each rebalance snapshot through the rebalance date, scores it with pure `src/` modules, converts selected tickers into equal target weights, and records per-ticker states via `decide_state()` without calling `apply_state_machine()` or writing `state.json`. Provider-backed ETF flow is forced neutral in this historical path until as-of provider snapshots exist, so the builder stays OHLCV-only and avoids current-data leakage.

Manual backtest smoke run:

```powershell
python scripts/run_backtest.py
```

Fast live data smoke, without writing report artifacts or running the full historical methodology simulation:

```powershell
python scripts/run_backtest.py --live-smoke
```

The manual runner uses `OHLCV_PROVIDER=auto`: it prefers Massive aggregate bars when `MASSIVE_API_KEY` is configured and falls back to yfinance otherwise. Set `OHLCV_PROVIDER=massive` to force Massive historical bars, or `OHLCV_PROVIDER=yfinance` to force the free default. Keep `MASSIVE_VERIFY_SSL=true` unless a local certificate store blocks manual smoke testing; `MASSIVE_VERIFY_SSL=false` is an explicit troubleshooting override, not a production setting.

The runner writes `docs/backtest_report.md` when market data downloads successfully. Treat that report as manual evidence, not a replacement for the deterministic test suite.
The report uses the historical methodology target builder as the strategy path, then compares it with 60/40 and equal-weight sector benchmarks. It includes strategy metrics, benchmark comparison, 3/5/10 bps cost sensitivity, historical simulation evidence, in-sample / out-of-sample metrics, and acceptance-gate status with the evidence/rule behind each gate. The simulation evidence records rebalance count, state ticker coverage, selected ticker count, state transition count, and state transitions per ticker-year. Acceptance gates use out-of-sample metrics by default, with 2015-01-01 as the current OOS boundary, and the state-transition gate now uses the simulated historical states instead of a placeholder. The runner also writes `docs/backtest_methodology_report.md`, `docs/backtest_equity.csv`, and `docs/backtest_metadata.json`; the dashboard's Backtest Lab section displays the summary report, normalized equity chart, and drawdown chart only when the metadata hashes match the artifact files. Use `notebooks/backtest_methodology_report.ipynb` as a lightweight artifact inspection guide. These are manual research artifacts, not live-edge claims.

## Portfolio analyzer

B-130 adds a read-only analyzer section inside the Streamlit app:

- **Ticker mode:** enter one ticker and see its current state, score, flow, class, selection flag, and portfolio-weighted exposure as a one-position analysis.
- **Portfolio mode:** upload `.csv`, `.xlsx`, or `.xls` holdings. The file needs a ticker-like column: `ticker`, `symbol`, `holding`, or `asset`.
- Optional upload columns include `shares`, `quantity`, `qty`, `cost_basis`, `cost`, `market_value`, `value`, `weight`, `sector`, `account`, and `notes`.
- Weights can be decimals (`0.25`) or percents (`25%` or `25`). If no valid weights are present, analysis falls back to market value weights, then equal weights.
- Unknown tickers are reported as missing instead of crashing. Uploaded files are analyzed in memory only; the app does not save portfolios or connect to broker accounts.

## Custom universe builder

B-105 adds a read-only custom universe section inside the Streamlit app:

- **Paste tickers:** enter a comma, space, semicolon, or newline separated ticker list.
- **Upload file:** upload `.csv`, `.xlsx`, or `.xls` files with a ticker-like column: `ticker`, `symbol`, `holding`, or `asset`.
- Duplicate tickers are ignored after the first occurrence. Unknown tickers are reported as missing instead of crashing.
- Matched tickers are ranked by current `S_score` inside the custom list and retain their methodology state, class, flow score, class rank, selection flag, and veto flag.
- The builder is snapshot-only and in-memory: it does not fetch new OHLCV, alter `src/universe.py`, save watchlists, or write state-machine files.

## Mobile view

B-110 adds CSS and Streamlit markup hooks for narrower screens:

- Header metadata wraps instead of pushing content off screen.
- RRG class buttons and drill buttons wrap into usable rows on phone widths.
- Dense tables scroll horizontally rather than squeezing all columns into unreadable text.
- Alert rows, action summaries, status tiles, defensive cards, and drill metrics collapse into tighter mobile-friendly grids.

## Sector relative strength

B-111 adds a sector spaghetti chart after the RRG section. It uses the already-loaded OHLCV snapshot, compares each US sector ETF with SPY, normalizes every line to 100 at the start of the 12-month window, and sorts traces by latest relative strength.

## Drill-down chart ranges

B-112 adds a `CHART RANGE` control to the per-ticker drill-down. The selector clips the visible weekly price/30wMA, CMF, and OBV chart windows while keeping the full loaded ticker OHLCV available for rolling-indicator warmup.

- Supported ranges: `3M`, `6M`, `1Y`, `3Y`, and `MAX`.
- The range is anchored to the latest available date in the loaded data, not the system clock.
- `MAX` means all OHLCV already loaded for the current dashboard run; it does not request a longer provider window.

## Table hover previews

B-113 adds a CSS-only hover preview to each full matrix ticker row on desktop. The preview uses already-computed `rs_ratio`, `rs_momentum`, state, S-score, and F-score values to show a mini RRG grid and dot without fetching data or changing scoring.

## Quick start

### Windows (local)

```powershell
git clone https://github.com/<you>/sector-rotation-dashboard.git
cd sector-rotation-dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Or just double-click `run.bat` (creates venv + installs deps automatically on first run). If it fails, run `run-diagnostic.bat` for step-by-step output.

### Linux / macOS / Raspberry Pi

```bash
git clone https://github.com/<you>/sector-rotation-dashboard.git
cd sector-rotation-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For a 24/7 deployment on a Raspberry Pi with a public URL via Cloudflare Tunnel, see [`docs/DEPLOY_RASPBERRY_PI.md`](docs/DEPLOY_RASPBERRY_PI.md) and [`docs/DEPLOY_CLOUDFLARE_TUNNEL.md`](docs/DEPLOY_CLOUDFLARE_TUNNEL.md).

## Project layout

```
sector-rotation-dashboard/
├── README.md                       <- this file
├── LICENSE                         <- MIT
├── .gitignore
├── requirements.txt                <- pip dependencies
├── app.py                          <- Streamlit entry point
├── run.bat                         <- Windows one-click launcher
├── run-diagnostic.bat              <- Windows verbose launcher
├── src/
│   ├── universe.py                 <- 83+ tickers grouped by class
│   ├── data.py                     <- OHLCV ingestion: yfinance default, Massive optional
│   ├── indicators.py               <- Pillars 1-5 + breadth
│   ├── flow.py                     <- Pillar 7: CMF/OBV/MFI/RVOL + 5 stubs
│   ├── macro.py                    <- Pillar 6: Faber + yield curve
│   ├── portfolio.py                <- Read-only ticker/portfolio parsing and analysis
│   ├── custom_universe.py          <- Read-only custom universe parsing and ranking
│   ├── scoring.py                  <- Composite + state machine
│   └── visuals.py                  <- Plotly RRG/momentum/price charts
├── docs/
│   ├── sector-rotation-methodology.md     <- full methodology (~30 pages)
│   ├── sector-rotation-methodology.pdf    <- same content, polished PDF
│   ├── GITHUB_SETUP.md                    <- how to push this to GitHub
│   ├── DEPLOY_RASPBERRY_PI.md             <- Pi 4/5 24/7 deployment
│   └── DEPLOY_CLOUDFLARE_TUNNEL.md        <- expose via your domain
├── systemd/
│   └── sector-dashboard.service           <- Pi auto-start unit
└── config/
    └── cloudflared-config.yml.example     <- tunnel config template
```

## Pillar implementation status

| # | Pillar | Status | Notes |
|---|--------|--------|-------|
| 1 | Cross-sectional 12-1 momentum | **LIVE** | yfinance daily bars by default; Massive aggregate bars optional |
| 2 | Faber 10-month SMA | **LIVE** | monthly resample |
| 3 | Weinstein Stage 2 (30wMA + Mansfield RS) | **LIVE** | weekly resample |
| 4 | Antonacci dual momentum | **LIVE** | vs BIL T-bill ETF |
| 5 | RRG (RS-Ratio + RS-Momentum) | **LIVE** | approximation of JdK formulas |
| 6 | Business-cycle phase | **PROVIDER-READY** | Fallback: Faber 10mo on SPY + ^TNX/^IRX curve sign. With `FRED_API_KEY`: INDPRO, yield curves, NFCI, recession probability, unemployment, and HY spread. |
| 7 | Volume & institutional flow | **LIVE** for CMF, OBV, MFI, RVOL, distribution days, OBV/price divergence · **PROVIDER-READY** for ETF primary flow · **STUBBED** for block trades, dark pool, short interest, 13F |

## Wiring real institutional-flow feeds

Each provider-backed signal has a hook in `src/flow.py`. ETF primary flow now has a provider seam: leave `FLOW_STUB_MODE=true` or unset for neutral behavior, or set `FLOW_STUB_MODE=false` plus `MASSIVE_API_KEY` and `ETF_PRIMARY_FLOW_URL_<TICKER>` values in Streamlit secrets or environment variables.

The remaining provider seams have independent safety flags. Leave each unset/`true` for neutral behavior until that feed is fully configured:

- `MASSIVE_TRADES_STUB_MODE`
- `FINRA_ATS_STUB_MODE`
- `FINRA_SHORT_INTEREST_STUB_MODE`
- `SEC_13F_STUB_MODE`

- `etf_primary_flow_5d_pct()` → Massive-rendered issuer SHO/source URL per ticker
- `block_trade_upside_ratio()` → Massive `/v3/trades`; enable with `MASSIVE_TRADES_STUB_MODE=false`
- `dark_pool_pct()` → FINRA ATS weekly summary; enable with `FINRA_ATS_STUB_MODE=false`
- `short_interest_delta_15d()` → FINRA consolidated short interest; enable with `FINRA_SHORT_INTEREST_STUB_MODE=false`
- `thirteen_f_net_buys_q()` → configured SEC Form 13F data-set zip plus `SEC_13F_CUSIP_<TICKER>` mapping; enable with `SEC_13F_STUB_MODE=false`

## State transition alerts

`apply_state_machine()` writes `state.json` first, then sends optional transition alerts through Telegram and/or Slack. Leave alert secrets unset to disable network calls. To enable alerts, configure `TELEGRAM_BOT_TOKEN` plus `TELEGRAM_CHAT_ID`, and/or `SLACK_WEBHOOK_URL`, in Streamlit secrets or environment variables.

Dashboard deep links support `?ticker=XLK`; the app opens with that ticker selected in the per-ticker drill-down.

## Methodology references

- Jegadeesh & Titman (1993). *Returns to Buying Winners and Selling Losers.* JoF.
- Faber (2007/2013). *A Quantitative Approach to Tactical Asset Allocation.* SSRN 962461.
- Antonacci (2014). *Dual Momentum Investing.* McGraw-Hill.
- Weinstein (1988). *Secrets for Profiting in Bull and Bear Markets.* McGraw-Hill.
- de Kempenaer (2011–). *Relative Rotation Graphs.* relativerotationgraphs.com.
- Stovall (1996). *Sector Investing.* McGraw-Hill; Fidelity *Business Cycle Approach.*
- Chaikin (1981). *Chaikin Money Flow.* · Granville (1963). *OBV.* · O'Neil (1988). *CAN SLIM distribution days.*
- Lee & Swaminathan (2000). *Price Momentum and Trading Volume.* JoF.

Full bibliography in [`docs/sector-rotation-methodology.md`](docs/sector-rotation-methodology.md) §11.

## License

MIT — see [LICENSE](LICENSE).

**Disclaimer:** This software is for educational and research purposes only. It is not investment advice. Backtest results do not guarantee future performance.
