# Layered Sector Rotation Methodology

**A multi-timeframe, evidence-based framework for identifying bullish sectors and alerting on bearish reversals across US sectors, international markets, and style factors.**

Prepared: 2026-05-16
Author: built from the canonical academic + practitioner sector-rotation literature
Intended use: methodology spec for automation (Python/cron/alerting)

---

## 1. Executive summary

There is no single "proven" methodology — there are seven pillars that *each* have peer-reviewed or 30+ years of out-of-sample evidence behind them. Used together, they are highly redundant and that redundancy is the source of their robustness.

The pillars are:

| # | Pillar | Source | What it tells you |
|---|--------|--------|-------------------|
| 1 | **Cross-sectional momentum (12-1)** | Jegadeesh & Titman 1993; Moskowitz & Grinblatt 1999 | Which sectors have been outperforming peers over the past 12 months (excluding the last month to skip short-term reversal) |
| 2 | **Time-series momentum / Faber 10-month SMA** | Faber 2007; Moskowitz, Ooi & Pedersen 2012 | Whether each sector is in its *own* uptrend (binary risk-on/off) |
| 3 | **Weinstein Stage Analysis** | Weinstein 1988 | Whether the sector is in **Stage 2** (advance) vs Stage 1/3/4 — uses 30-week MA + Mansfield RS |
| 4 | **Antonacci Dual Momentum** | Antonacci 2014 | Combines absolute (vs T-bill) + relative (vs peers) momentum — the absolute filter is the catastrophic-loss circuit-breaker |
| 5 | **Relative Rotation Graphs (RRG)** | de Kempenaer 2004/2011 | Where each sector is in the rotation cycle: Leading → Weakening → Lagging → Improving |
| 6 | **Business-cycle / macro overlay** | Stovall 1996; Fidelity Business Cycle | Macro regime (early/mid/late/recession) defines which sector *baskets* should structurally lead |
| 7 | **Volume & institutional money flow** | Wyckoff 1931; Granville (OBV) 1963; Chaikin (CMF) 1981; Bollinger 2002 | Whether large/smart money is *actually* accumulating (institutional flow, block trades, OBV trend, ETF creations) or distributing |

The methodology layers these pillars across **three timeframes** (monthly, weekly, daily). Bullish signals require confirmation in **at least 2 of 3 timeframes** AND a positive flow reading on Pillar 7 — flow is the **veto** that rejects price-only signals not backed by real money. Bearish signals trip a **state machine** that escalates from WARNING → EXIT → BEARISH.

---

## 2. Architecture — the three-layer stack

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — MONTHLY (macro regime, slow)                              │
│   • Faber 10-month SMA on benchmark → risk-on / risk-off            │
│   • ISM PMI direction + yield curve → cycle phase                   │
│   • Output: RISK_ON / RISK_OFF + CYCLE_PHASE                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ filters universe
┌──────────────────────────────▼──────────────────────────────────────┐
│ LAYER 2 — WEEKLY (sector selection, intermediate)                   │
│   • 12-1 cross-sectional momentum rank                              │
│   • RRG quadrant (RS-Ratio, RS-Momentum)                            │
│   • Weinstein stage (P > 30wMA, slope > 0, Mansfield RS > 0)        │
│   • Antonacci absolute filter (12mo return > T-bill total return)   │
│   • INSTITUTIONAL FLOW: OBV slope, CMF(21), ETF AUM change,         │
│     13F net buys, short-interest direction                          │
│   • Output: composite score → ranked list of BULLISH sectors        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ feeds tactical layer
┌──────────────────────────────▼──────────────────────────────────────┐
│ LAYER 3 — DAILY (entry / exit triggers, fast)                       │
│   • Donchian / 50-day breakout for entries                          │
│   • Sector breadth (% constituents > 50dMA)                         │
│   • VOLUME PACE: RVOL, unusual-volume scan, MFI(14),                │
│     block-trade tape, dark-pool % of consolidated volume            │
│   • State-machine alerting on regime changes                        │
│   • Output: BUY / HOLD / WARNING / EXIT / BEARISH actions           │
└─────────────────────────────────────────────────────────────────────┘
```

A sector is **fully bullish** only when LAYER 1 = RISK_ON, LAYER 2 ranks it top-quintile, and LAYER 3 confirms with breakout + breadth. A bearish alert can fire from *any* layer — see Section 6.

---

## 3. Universe

### 3.1 US sectors (11 SPDRs)
`XLK XLF XLE XLV XLI XLY XLP XLU XLB XLRE XLC`

### 3.2 US industries (drill-down, optional Phase 2)
`SOXX IGV IHI IHF KRE KIE ITB XHB XRT XOP OIH KWEB FDN ITA JETS SMH IBB XBI GDX`

### 3.3 International / country & region
`VEU VWO EFA EEM EWJ EWG EWU INDA MCHI FXI EWZ EWA EWC EWW KSA EZA EIDO EWY EWT EWS`

### 3.4 Style factors (US)
`MTUM QUAL USMV VLUE SIZE IWF IWD IJR IJH IWB`

### 3.5 Thematic exposures
`ARKK HACK MOO URA LIT TAN ICLN BOTZ`

### 3.6 Crypto exposures
`BITO IBIT ETHE`

### 3.7 Defensive / absolute-momentum bench
`BIL` (T-bill proxy, for Antonacci absolute filter) · `TLT IEF GLD UUP DBC` (risk-off candidates)

### 3.8 Benchmark
`SPY` for US, `ACWI` for global, `URTH` for developed-world cross-sector comparison

---

## 4. Indicator formulas

All inputs are weekly bars (Friday close) unless noted; daily bars only for Layer 3 triggers. Use **adjusted close** (total return) so dividends flow through.

### 4.1 Cross-sectional momentum (Jegadeesh-Titman 12-1)
```
M1_i = ( P_i[t-21] / P_i[t-252] ) - 1
```
where `t` is today (daily bars) and 252 trading days ≈ 12 months, skip 21 days (1 month) to remove short-term reversal. Compute for each ticker `i` in the universe. Rank cross-sectionally; the top decile is the "winner" basket.

### 4.2 Time-series momentum (Faber 10-month SMA)
```
SMA10_i = mean( monthly_close_i[t-9 .. t] )
TS_signal_i = 1 if monthly_close_i[t] > SMA10_i else 0
```
Apply on monthly bars. This is the binary "is this asset itself in an uptrend" filter.

### 4.3 Weinstein Stage 2 (weekly)
Inputs on weekly bars:
```
SMA30w = mean( weekly_close[t-29 .. t] )
slope = ( SMA30w[t] - SMA30w[t-5] ) / 5      # positive slope over last 5 weeks
mansfield_RS = ( (P_i[t] / P_bench[t]) / (P_i[t-52]/P_bench[t-52]) - 1 ) * 100
```
Stage 2 (bullish) is true when:
```
P_i[t] > SMA30w  AND  slope > 0  AND  mansfield_RS > 0
```
Stage 4 (bearish) is true when:
```
P_i[t] < SMA30w  AND  slope < 0  AND  mansfield_RS < 0
```

### 4.4 Antonacci dual-momentum filter
```
abs_mom_i = total_return_i[252 trading days] - total_return_BIL[252 trading days]
A_pass_i  = 1 if abs_mom_i > 0 else 0
```
A sector cannot be a buy unless `A_pass_i = 1`. This is the catastrophic-loss circuit-breaker.

### 4.5 RRG — RS-Ratio and RS-Momentum
de Kempenaer's exact formulas are proprietary, but a widely-published approximation is:
```
RS_raw_i      = 100 * P_i / P_bench
RS_ratio_i    = 100 + ( RS_raw_i - SMA(RS_raw_i, 63) ) / stdev(RS_raw_i, 252) * 10
RS_momentum_i = 100 + ( RS_ratio_i - SMA(RS_ratio_i, 5) ) / stdev(RS_ratio_i, 21) * 10
```
Plot RS-Ratio on X, RS-Momentum on Y, axes cross at 100. Quadrants:
```
Leading   = RS_ratio > 100 AND RS_momentum > 100
Weakening = RS_ratio > 100 AND RS_momentum < 100
Lagging   = RS_ratio < 100 AND RS_momentum < 100
Improving = RS_ratio < 100 AND RS_momentum > 100
```

### 4.6 Sector breadth (daily)
For each sector ETF, compute the percentage of its top-N holdings (or sector-index constituents) above their 50-day SMA:
```
B50_sector = mean( 1 if P_j > SMA50_j else 0 for j in constituents )
```
- Bullish:  `B50 >= 60%`
- Neutral:  `40% <= B50 < 60%`
- Bearish:  `B50 < 40%`

If constituent-level data is unavailable, substitute the McClellan-style oscillator on the sector ETF itself.

### 4.7 Institutional money flow & volume — the "smart money" pillar
**This is the layer that tells you whether real institutional capital is moving in or out of a sector — not just whether price is moving.** Price can rise on light volume (suspect) or on heavy institutional sponsorship (confirmed). The metrics below are the canonical ones with peer-reviewed or industry-standard backing.

#### 4.7.1 On-Balance Volume (OBV) — Granville 1963
The earliest accumulation/distribution indicator. Adds the day's volume to a running total on up days, subtracts on down days.
```
OBV[t] = OBV[t-1] + sign(close[t] - close[t-1]) * volume[t]
OBV_slope_20 = linreg_slope( OBV[t-19 .. t] )   # 20-day regression slope
```
**Bullish:** OBV is making new highs *with* or *ahead of* price.
**Bearish (divergence):** Price makes a new high but OBV does not.

#### 4.7.2 Chaikin Money Flow (CMF, 21-period) — Chaikin 1981
The single best volume-weighted accumulation/distribution measure for an ETF. Combines where each bar closes within its range with the volume on that bar.
```
MFM = ((close - low) - (high - close)) / (high - low)       # money-flow multiplier, range [-1, +1]
MFV = MFM * volume                                          # money-flow volume
CMF21 = sum( MFV[t-20 .. t] ) / sum( volume[t-20 .. t] )
```
**Reading:**
- `CMF21 > +0.10` → strong accumulation (institutional buying pressure)
- `+0.05 to +0.10` → mild accumulation
- `-0.05 to +0.05` → neutral
- `-0.05 to -0.10` → mild distribution
- `CMF21 < -0.10` → strong distribution (institutional selling)

#### 4.7.3 Money Flow Index (MFI, 14-period) — "volume-weighted RSI"
```
typical_price = (high + low + close) / 3
raw_money_flow = typical_price * volume
positive_mf  = sum of raw_money_flow on days where typical_price > yesterday's
negative_mf  = sum of raw_money_flow on days where typical_price < yesterday's
money_ratio  = positive_mf / negative_mf       # over the 14-day window
MFI = 100 - (100 / (1 + money_ratio))
```
- `MFI > 80` overbought (often near distribution tops)
- `MFI < 20` oversold (often near accumulation bottoms)
- **MFI/price divergence** is one of the cleanest reversal signals there is.

#### 4.7.4 Relative Volume (RVOL) — unusual volume detector
The "tape is telling you something" indicator.
```
RVOL[t] = volume[t] / mean( volume[t-20 .. t-1] )
```
- `RVOL ≥ 1.5` → unusual (something happened)
- `RVOL ≥ 2.0` → highly unusual (news, earnings, institutional sweep)
- `RVOL ≥ 3.0` → block-print suspect; investigate the tape

#### 4.7.5 Block trades & dark-pool flow — institutional footprints
A "block" is a single print of ≥ 10,000 shares or ≥ $200,000 notional (NYSE Rule 127 / FINRA Rule 6240). Most institutional executions are split across many lit prints and printed off-exchange ("dark"); the dark-pool share is reported via FINRA ATS data.
```
block_count[t]      = count of single prints ≥ 10,000 shares
block_notional[t]   = sum of notional value of those prints
dark_pool_pct[t]    = off_exchange_volume[t] / consolidated_volume[t]    # 0..1
upside_block_ratio  = block_notional_on_uptick / block_notional_on_downtick   # > 1 = bullish
```
**Bullish reading:**
- `dark_pool_pct ≥ 45%` *with* `upside_block_ratio > 1.5` for ≥ 3 sessions → silent institutional accumulation
- Sustained `block_count` above 20-day average

**Bearish reading:**
- `upside_block_ratio < 0.7` while price is flat or rising → distribution into strength
- A surge in block trades on a *down* day at the end of a Stage 2 advance is a classic Stage 3 distribution signal

Data sources: FINRA OTC Transparency (free, T+1), Cboe BZX/EDGX, NYSE TAQ (paid), or aggregators like FlowAlgo, Quiver Quant, Cheddar Flow.

#### 4.7.6 Trade velocity / pace — speed of institutional execution
"Velocity" measures how fast institutions are accumulating relative to the recent baseline.
```
trade_count[t]     = number of executions
notional_velocity  = ( dollar_volume[t] / trade_count[t] ) / sma( dollar_volume / trade_count, 20 )
```
A rising **average trade size** (`notional / count`) combined with rising volume signals that the average market participant is getting larger — i.e., funds, not retail. Conversely, falling trade size on rising volume often signals retail capitulation or distribution.

#### 4.7.7 ETF primary-market flows — creations & redemptions
For sector ETFs (XLK, SOXX, etc.) this is the cleanest possible institutional-flow signal because it requires an authorized participant to deliver baskets of underlying shares.
```
shares_outstanding_change[t] = SHO[t] - SHO[t-1]            # from issuer daily file
estimated_net_flow[t]        = shares_outstanding_change[t] * NAV[t]
nf_5d_pct = sum( estimated_net_flow[t-4 .. t] ) / AUM[t]    # net flow last 5d as % of AUM
```
- `nf_5d_pct > +1.5%` → strong primary inflow (real money entering the sector basket)
- `nf_5d_pct < -1.5%` → strong primary outflow (money exiting)

Issuer daily holdings/SHO files are free: iShares, SSGA, Invesco, Vanguard publish them.

#### 4.7.8 13F institutional positioning (quarterly, lagged)
SEC 13F filings (45-day lag) reveal which sectors hedge funds and institutions added to. Aggregate across the largest 100 active managers:
```
hf_net_buys_sector_q = Σ ( current_q_shares - prior_q_shares ) × avg_price   for each sector
```
- Sectors with positive Q-over-Q net buys from a majority of top managers (≥ 60% of the 100) have a structural tailwind for the next 1–2 quarters.
- The data is lagged but the *direction* persists; useful as a slow-moving confirmation of the cross-sectional momentum signal.

Sources: SEC EDGAR (free), WhaleWisdom, 13F.info, Bloomberg.

#### 4.7.9 Short interest & days-to-cover
Bi-monthly FINRA Reg SHO data. Rising short interest in a Stage-2 advancing sector is fuel for a short-squeeze; falling short interest while price rises is "real" buying.
```
SI_ratio[t]     = short_interest[t] / shares_outstanding[t]
days_to_cover   = short_interest[t] / 20d_avg_daily_volume
SI_delta_15d    = SI_ratio[t] - SI_ratio[t-15]   # change over the half-month
```
- `SI_delta_15d < 0` while price rising → genuine demand absorbing supply
- `SI_delta_15d > 0` while price falling → distribution + bearish positioning
- `days_to_cover > 5` in a rising sector → squeeze potential

#### 4.7.10 Composite "institutional flow" score per sector
Aggregate the above into a single z-scored composite that can be used in the master ranking:
```
F_i = 0.30 * z(CMF21_i)                  # primary accumulation/distribution
    + 0.20 * z(OBV_slope_20_i)           # volume-trend confirmation
    + 0.20 * z(nf_5d_pct_i)              # ETF primary flow (or 13F if no ETF flow)
    + 0.10 * z(upside_block_ratio_i)     # block-trade direction
    + 0.10 * z(notional_velocity_i)      # trade-size velocity
    + 0.10 * (-1) * z(SI_delta_15d_i)    # short-interest improvement (sign-flipped)
```
`F_i` is the **Pillar 7 institutional flow score** and enters the master composite in §5.

#### 4.7.11 Hard veto rule
Even with a perfect price-based score, a sector cannot be added if `F_i < -0.5σ` (i.e., it's in the bottom ~30% of the universe on flow). This prevents buying "price-only" rallies that aren't backed by real money — a signature failure mode of pure-momentum systems.

### 4.8 Business-cycle phase (monthly)
Use a deterministic mapping:
```
phase = EARLY     if ISM_PMI > 50 and rising and yield_curve > 0
        MID       if ISM_PMI > 50 and slowing and yield_curve > 0
        LATE      if ISM_PMI > 50 and yield_curve < 0
        RECESSION if ISM_PMI < 50 (2 consecutive months)
```
ISM PMI from FRED (series `MANEMP` or use Markit PMI as fallback), yield curve = 10Y - 2Y from FRED (`T10Y2Y`).

Map phase → favored US sectors (Fidelity Business Cycle table):
- **Early**:   XLY, XLF, XLRE, XLI, XLK, XLB
- **Mid**:     XLK, XLC, XLI (sector dispersion is lowest in this phase)
- **Late**:    XLE, XLB, XLP, XLV
- **Recession**: XLP, XLU, XLV

The macro overlay does *not* override sector signals — it adjusts the composite weight (Section 5) by +10% for in-phase sectors and -10% for out-of-phase sectors.

---

## 5. Composite scoring (Layer 2 output)

Per ticker, per week (Friday close):

```
z(x)       = cross-sectional z-score of x across the active universe
filters_i  = TS_signal_i + Stage2_i + A_pass_i   # 0..3

S_i = 0.22 * z(M1_i)                 # 12-1 momentum
    + 0.12 * z(mansfield_RS_i)       # Weinstein RS
    + 0.15 * z(RS_ratio_i)           # RRG horizontal
    + 0.08 * z(RS_momentum_i)        # RRG vertical
    + 0.12 * (filters_i / 3)         # binary trend filters (TS, Stage2, Antonacci)
    + 0.08 * cycle_tilt_i            # +1 / 0 / -1 from business-cycle map
    + 0.23 * z(F_i)                  # *** institutional flow composite (§4.7.10) ***

# Hard veto: drop any sector where F_i < -0.5σ even if S_i is high
# (price-only rallies without flow are rejected)

# Hold top N
N_us_sectors    = 4   (out of 11)
N_industries    = 3   (out of 19)
N_countries     = 3   (out of ~20)
N_factors       = 1-2 (out of 10)
N_themes        = 3   (out of 8)
N_crypto        = 1   (out of 3)
```
**Why flow gets ~23% of the weight** — it's an independent confirmation of the price-based pillars. When price and flow agree, signal quality is much higher; when they disagree, the trade is almost always wrong. Empirically (Lee & Swaminathan 2000; Chordia & Swaminathan 2000) volume-confirmed momentum substantially outperforms pure-price momentum on a risk-adjusted basis.

Rebalance weekly (Friday close → execute Monday open). The 12-1 momentum literature is unanimous that monthly rebalancing is fine; weekly is the *fastest* rebalance that still respects the academic evidence. Daily rebalancing destroys the edge in transaction costs.

---

## 6. Bearish alert state machine (the part you specifically asked about)

Each held position has a state. The state advances on the worst signal across timeframes; it can only *retreat* (improve) after 4 consecutive weekly closes of improvement.

| State | Entry condition (any one trips advance) | Action | Alert priority |
|-------|-----------------------------------------|--------|----------------|
| **STAGE_2_BULLISH** | All Stage-2 conditions + RRG Leading + B50 ≥ 60% + CMF21 > +0.05 + nf_5d_pct > 0 | Buy / Add | n/a |
| **HOLD** | Stage-2 intact, CMF21 still > 0, no flow divergence | Hold | none |
| **WARNING** | RRG drops to Weakening ≥ 2 wks, OR breadth B50 < 50%, OR M1 rank out of top-tercile, OR **CMF21 < 0 for 2 wks**, OR **price/OBV bearish divergence**, OR **upside_block_ratio < 1.0 for 3+ sessions** | Tighten stop to 30wMA, no new adds | LOW (info) |
| **EXIT** | Weekly close below 30wMA, OR Mansfield RS turns negative, OR Antonacci `A_pass = 0`, OR RRG enters Lagging, OR **CMF21 < -0.10**, OR **nf_5d_pct < -1.5% (sustained ETF redemptions)**, OR **block tape flips: upside_block_ratio < 0.7 for 5 sessions** | Sell on Monday open, send alert | HIGH (action) |
| **BEARISH / STAGE_4** | EXIT condition + 30wMA slope negative + RRG Lagging ≥ 3 wks + **CMF21 < -0.10 confirmed for 3 wks** | Avoid; short candidate | HIGH (action) |
| **STAGE_1_BASING** | Came from BEARISH; price reclaimed 30wMA but slope still flat **AND CMF21 turns positive** | Watch for re-entry | LOW (info) |

**Flow-only early-warning alerts** (fire even before state advances):
- **DISTRIBUTION_DAY**: large up-volume day (RVOL ≥ 1.5) closing in the lower 25% of its range — classic O'Neil distribution signal. 4+ in 25 sessions historically precedes Stage-3 tops.
- **DARK_POOL_SELL**: dark_pool_pct > 50% with price flat or down for 3+ days — silent institutional exit.
- **OBV_NEGATIVE_DIVERGENCE**: price makes a new 20-day high but OBV does not — early Stage 3 warning.

### 6.1 Alert delivery
Three escalation levels:
- **LOW** — daily digest email at 8am ET (states changed yesterday)
- **HIGH** — immediate push (Pushover / Telegram / Slack webhook) on EXIT or BEARISH entry
- **MACRO** — separate channel when Faber 10-month SMA flips on the SPY benchmark (whole-portfolio risk-off)

### 6.2 Cooldown
- A position that exited cannot be re-bought for 4 weeks unless it goes BEARISH → STAGE_1 → STAGE_2 sequence. This prevents whipsaws.

---

## 7. Data, libraries, scheduling

### 7.1 Data sources
| Need | Free option | Paid option |
|------|-------------|-------------|
| Daily/weekly OHLC ETF | `yfinance` (Yahoo) | Polygon, Tiingo, EOD Historical Data |
| Macro (PMI, yield curve, CPI) | `fredapi` (FRED) — free | Bloomberg, Refinitiv |
| Sector constituents | iShares / SSGA holdings CSVs (free) | FactSet, S&P Capital IQ |
| ETF SHO / primary flow | Issuer daily holdings files (iShares, SSGA) — free | Bloomberg, ICI |
| Short interest | FINRA Reg SHO bi-monthly (free) | S3 Partners, Markit |
| 13F institutional holdings | SEC EDGAR (free, T+45) | WhaleWisdom, 13F.info, Bloomberg |
| Block trades / lit prints | NYSE TAQ delayed (free), Polygon trade-tape | Refinitiv MarketPsych, NYSE TAQ realtime |
| Dark pool % / ATS volume | FINRA ATS Transparency (free, T+1) | FlowAlgo, Cheddar Flow, Quiver Quant |
| Unusual options activity (proxy for flow) | CBOE delayed feeds | Unusual Whales, BlackBoxStocks |
| Backtest engine | `vectorbt`, `bt`, `zipline-reloaded` | `Backtrader` is free too |

### 7.2 Python stack
```
python ≥ 3.11
pandas, numpy, scipy
yfinance, fredapi, pandas-datareader
pandas-ta or ta-lib for indicators (CMF, MFI, OBV all included)
sec-edgar-downloader  # 13F filings
finra-data            # short interest, ATS dark pool volumes
requests + lxml       # iShares/SSGA SHO daily CSV ingestion
matplotlib + plotly for RRG visualization
vectorbt (or bt) for backtests
apscheduler (or cron + systemd) for scheduling
requests for webhook alerts
sqlite (or DuckDB) for the state-machine persistence
```

### 7.3 Job schedule (cron, US Eastern)
| Job | Frequency | Time |
|-----|-----------|------|
| `update_prices.py` | daily | 18:00 ET (after close + reconciliation) |
| `compute_daily_triggers.py` | daily | 18:15 ET |
| `compute_weekly_signals.py` | weekly | Fri 18:30 ET |
| `compute_monthly_macro.py` | monthly | 1st business day, 09:00 ET |
| `state_machine_advance.py` | daily | 18:20 ET |
| `send_alerts.py` | daily + on-trigger | 07:55 ET digest; immediate on HIGH |

### 7.4 Repository layout
```
sector-rotation/
├── data/
│   ├── ohlc_daily.duckdb       # price history
│   ├── fred.duckdb             # macro
│   └── state.json              # state machine snapshot
├── src/
│   ├── universe.py             # the tickers in §3
│   ├── indicators.py           # formulas in §4
│   ├── scoring.py              # composite in §5
│   ├── state_machine.py        # transitions in §6
│   ├── alerts.py               # webhook senders
│   └── backtest.py             # vectorbt harness
├── jobs/                       # cron entry points
├── notebooks/                  # research / RRG plots
└── tests/
```

---

## 8. Backtest plan (before going live)

1. **Data range**: 2003–today (so it spans the 2008 GFC, 2011 EU crisis, 2020 COVID, 2022 bear). Use longest possible for ETFs that exist; substitute index total-return for older history (e.g., MSCI EAFE for EFA).
2. **Walk-forward**: Train universe weights on 2003–2014, lock parameters, then run 2015–today as out-of-sample. Do **not** tune on the out-of-sample window.
3. **Benchmark**: 60/40 SPY/AGG and equal-weight 11-sector portfolio.
4. **Metrics to log**: CAGR, Sharpe, Sortino, max drawdown, Calmar, hit-rate by signal, turnover, average holding period, transaction-cost sensitivity (3, 5, 10 bps per side).
5. **Stress checks**:
   - Run with the 2-month and 6-month lookbacks instead of 12-1 — does CAGR collapse? (If yes, you've overfit to 12-1.)
   - Remove the Antonacci absolute filter — does max drawdown blow out? (Antonacci's own data says yes — it should ~halve drawdown.)
   - Shuffle the universe (random sectors): does CAGR fall to benchmark? (Sanity check that the signal is doing work.)
6. **Acceptance criteria** to deploy live:
   - Out-of-sample Sharpe ≥ 0.7 (60/40 historical is ~0.4)
   - Max drawdown ≤ 75% of equal-weight benchmark drawdown
   - Turnover ≤ 300% annual (otherwise costs eat returns)
   - State machine transitions ≤ 4 per ticker per year on average

---

## 9. Pitfalls & known weaknesses

1. **Momentum crashes** (Daniel & Moskowitz 2016): pure 12-1 momentum has rare but brutal reversal months. The Antonacci absolute filter + Weinstein 30wMA exit *mostly* prevents these. Backtest must include 2009-Apr (the canonical momentum-crash month).
2. **"Myth of sector rotation"** (Molchanov & Stangl 2018): the deterministic business-cycle → sector map underperforms once you account for forward-looking phase identification. **Conclusion**: the macro overlay should only nudge the composite, not drive it.
3. **RRG is a visualization, not a system**: the RS-Ratio/RS-Momentum formulas above are an approximation; the proprietary version differs. Don't claim RRG-branded backtests if you publish.
4. **Data-mined factor zoo**: limit yourself to the five canonical factors (momentum, value, quality, low-vol, size) — anything else is suspect.
5. **Survivorship bias** in ETF universe: a few sector / country ETFs have closed (e.g., GREK relisted multiple times). Use a delisted-aware data provider for honest backtests.
6. **Bear-market false positives**: the state machine will whipsaw in a choppy market. The 4-week cooldown (§6.2) and "2-of-3 timeframes" rule (§2) are designed for this — don't relax them.

---

## 10. Build phases (suggested 9-week plan)

| Week | Deliverable |
|------|-------------|
| 1 | Data pipeline: yfinance ingest + FRED macro + DuckDB schema |
| 2 | Indicators module: §4.1–4.6 + 4.8 with unit tests against known values |
| 3 | Institutional-flow module (§4.7): CMF, OBV, MFI, RVOL; iShares SHO ingestion |
| 4 | Block-trade & dark-pool feed (FINRA ATS + Polygon tape, or paid feed); 13F + short interest ingestion |
| 5 | Scoring module (§5) + ranking output as CSV + RRG notebook |
| 6 | State machine (§6) with state persistence + flow-veto + distribution-day alerts |
| 7 | Alerting (webhook to your preferred channel) + cron jobs |
| 8 | Backtest (§8) — full walk-forward, with/without flow pillar |
| 9 | Paper-trade dashboard (Streamlit or simple HTML); go-live decision gate |

---

## 11. References

**Academic:**
- Jegadeesh, N. & Titman, S. (1993). *Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency.* Journal of Finance.
- Moskowitz, T. & Grinblatt, M. (1999). *Do Industries Explain Momentum?* Journal of Finance.
- Moskowitz, T., Ooi, Y. & Pedersen, L. (2012). *Time Series Momentum.* Journal of Financial Economics.
- Asness, C., Moskowitz, T. & Pedersen, L. (2013). *Value and Momentum Everywhere.* Journal of Finance.
- Daniel, K. & Moskowitz, T. (2016). *Momentum Crashes.* Journal of Financial Economics.
- Molchanov, A. & Stangl, J. (2018, 2024). *The Myth of Sector Rotation.* AUT working paper / IJFE.

**Practitioner:**
- Weinstein, S. (1988). *Secrets for Profiting in Bull and Bear Markets.* McGraw-Hill.
- Faber, M. (2007, updated 2013). *A Quantitative Approach to Tactical Asset Allocation.* SSRN 962461.
- Antonacci, G. (2014). *Dual Momentum Investing.* McGraw-Hill.
- de Kempenaer, J. (2011–present). RRG documentation at relativerotationgraphs.com.
- Stovall, S. (1996). *Sector Investing.* McGraw-Hill.
- Fidelity Investments. *The Business Cycle Approach to Equity Sector Investing.* (PDF white paper.)

**Volume & institutional flow:**
- Wyckoff, R. (1931). *The Richard D. Wyckoff Method of Trading and Investing in Stocks.* (Accumulation/distribution schematic.)
- Granville, J. (1963). *Granville's New Key to Stock Market Profits.* (Origin of On-Balance Volume.)
- Chaikin, M. (1981, 1986). *Chaikin Money Flow / Chaikin Oscillator.* (Volume-weighted A/D.)
- O'Neil, W. (1988). *How to Make Money in Stocks — CAN SLIM.* (Distribution-day theory, institutional sponsorship.)
- Lee, C. M. C. & Swaminathan, B. (2000). *Price Momentum and Trading Volume.* Journal of Finance. (Volume-confirmed momentum.)
- Chordia, T. & Swaminathan, B. (2000). *Trading Volume and Cross-Autocorrelations in Stock Returns.* Journal of Finance.
- FINRA (ongoing). Regulation SHO short-interest data; ATS Transparency reports for dark-pool volumes.
- SEC. Form 13F quarterly institutional holdings filings (EDGAR).
