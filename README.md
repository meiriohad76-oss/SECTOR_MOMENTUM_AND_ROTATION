# Sector Rotation Dashboard

A Streamlit dashboard that monitors **67+ ETFs across US sectors, US industries, international markets, and style factors** using a 7-pillar layered methodology to identify bullish sectors and alert on bearish reversals.

> The methodology layers six peer-reviewed price pillars (cross-sectional momentum, Faber 10mo SMA, Weinstein Stage 2, Antonacci dual momentum, RRG, business cycle) with a seventh **institutional flow** pillar (CMF, OBV, MFI, RVOL, distribution days, block-trade tape, ETF creations, 13F, short interest).
>
> Full whitepaper: [`docs/sector-rotation-methodology.pdf`](docs/sector-rotation-methodology.pdf) · [`docs/sector-rotation-methodology.md`](docs/sector-rotation-methodology.md)

---

## What you get

- A **read-only portfolio / single-stock analyzer** that accepts one ticker or a CSV/XLS/XLSX holdings file and maps the input to the current methodology snapshot.
- A **single-page Streamlit app** (`app.py`) with two sections:
  - **Top:** 7-pillar heatmap — every ticker scored on every pillar, color-coded, with composite score and current state (`STAGE_2_BULLISH` / `HOLD` / `WARNING` / `EXIT` / `BEARISH_STAGE_4` / `STAGE_1_BASING`).
  - **Below:** drill-down tabs — RRG quadrant chart, cross-sectional momentum bar, institutional flow detail, state-machine transition log, per-ticker deep dive with price/CMF/OBV charts.
- A **persistent state machine** (`state.json`) so bearish transitions trigger only once and stay visible across sessions.
- A **bearish alert system** with three severity levels (WARNING → EXIT → BEARISH) plus three flow-only early warnings (distribution day, dark-pool sell, OBV/price divergence).
- **No paid feeds required for v1** — runs entirely on free Yahoo Finance data. Institutional-flow stubs ship pre-wired so you can drop in iShares SHO, Massive, FINRA, or SEC EDGAR feeds when ready.

## Backtest harness

B-011 adds a pure pandas/numpy backtest accounting core in `src/backtest.py`. The core is deterministic and covered by offline pytest cases for weight timing, drift, turnover, cost scenarios, benchmarks, acceptance gates, and no-lookahead historical methodology target construction.

The historical target builder accepts preloaded OHLCV, slices each rebalance snapshot through the rebalance date, scores it with pure `src/` modules, converts selected tickers into equal target weights, and records per-ticker states via `decide_state()` without calling `apply_state_machine()` or writing `state.json`. Provider-backed ETF flow is forced neutral in this historical path until as-of provider snapshots exist, so the builder stays OHLCV-only and avoids current-data leakage.

Manual yfinance smoke run:

```powershell
python scripts/run_backtest.py
```

The runner writes `docs/backtest_report.md` when market data downloads successfully. Treat that report as manual evidence, not a replacement for the deterministic test suite.

## Portfolio analyzer

B-130 adds a read-only analyzer section inside the Streamlit app:

- **Ticker mode:** enter one ticker and see its current state, score, flow, class, selection flag, and portfolio-weighted exposure as a one-position analysis.
- **Portfolio mode:** upload `.csv`, `.xlsx`, or `.xls` holdings. The file needs a ticker-like column: `ticker`, `symbol`, `holding`, or `asset`.
- Optional upload columns include `shares`, `quantity`, `qty`, `cost_basis`, `cost`, `market_value`, `value`, `weight`, `sector`, `account`, and `notes`.
- Weights can be decimals (`0.25`) or percents (`25%` or `25`). If no valid weights are present, analysis falls back to market value weights, then equal weights.
- Unknown tickers are reported as missing instead of crashing. Uploaded files are analyzed in memory only; the app does not save portfolios or connect to broker accounts.

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
│   ├── universe.py                 <- 67+ tickers grouped by class
│   ├── data.py                     <- yfinance ingestion (daily/weekly/monthly resample)
│   ├── indicators.py               <- Pillars 1-5 + breadth
│   ├── flow.py                     <- Pillar 7: CMF/OBV/MFI/RVOL + 5 stubs
│   ├── macro.py                    <- Pillar 6: Faber + yield curve
│   ├── portfolio.py                <- Read-only ticker/portfolio parsing and analysis
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
| 1 | Cross-sectional 12-1 momentum | **LIVE** | yfinance daily bars |
| 2 | Faber 10-month SMA | **LIVE** | monthly resample |
| 3 | Weinstein Stage 2 (30wMA + Mansfield RS) | **LIVE** | weekly resample |
| 4 | Antonacci dual momentum | **LIVE** | vs BIL T-bill ETF |
| 5 | RRG (RS-Ratio + RS-Momentum) | **LIVE** | approximation of JdK formulas |
| 6 | Business-cycle phase | **PARTIAL** | Faber 10mo on SPY + ^TNX/^IRX curve sign; full ISM PMI requires FRED API key |
| 7 | Volume & institutional flow | **LIVE** for CMF, OBV, MFI, RVOL, distribution days, OBV/price divergence · **PROVIDER-READY** for ETF primary flow · **STUBBED** for block trades, dark pool, short interest, 13F |

## Wiring real institutional-flow feeds

Each provider-backed signal has a hook in `src/flow.py`. ETF primary flow now has a provider seam: leave `FLOW_STUB_MODE=true` or unset for neutral behavior, or set `FLOW_STUB_MODE=false` plus `MASSIVE_API_KEY` and `ETF_PRIMARY_FLOW_URL_<TICKER>` values in Streamlit secrets or environment variables.

The remaining provider seams have independent safety flags. Leave each unset/`true` for neutral behavior until that feed is fully configured:

- `MASSIVE_TRADES_STUB_MODE`
- `FINRA_ATS_STUB_MODE`
- `FINRA_SHORT_INTEREST_STUB_MODE`
- `SEC_13F_STUB_MODE`

- `etf_primary_flow_5d_pct()` → Massive-rendered issuer SHO/source URL per ticker
- `block_trade_upside_ratio()` → Massive `/v3/trades`
- `dark_pool_pct()` → FINRA ATS Transparency (free, T+1)
- `short_interest_delta_15d()` → FINRA Reg SHO bi-monthly (free)
- `thirteen_f_net_buys_q()` → SEC EDGAR Form 13F-HR quarterly (free, T+45)

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
