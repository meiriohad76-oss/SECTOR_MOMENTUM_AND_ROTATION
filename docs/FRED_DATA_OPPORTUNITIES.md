# FRED Data Opportunities

Date checked: 2026-05-22
Runtime checked: AHADPI5, `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION`

The FRED key is configured on AHADPI5. The original B-022 macro classifier fetched all 7 classifier series successfully:

- `BAMLH0A0HYM2` - high-yield OAS
- `INDPRO` - industrial production
- `NFCI` - Chicago Fed financial conditions
- `RECPROUSM156N` - smoothed recession probability
- `T10Y2Y` - 10Y minus 2Y Treasury spread
- `T10Y3M` - 10Y minus 3M Treasury spread
- `UNRATE` - unemployment rate

The current live macro classifier returned:

```text
FRED_PHASE=MID
FRED_NOTE=INDPRO YoY +1.4%; curve +0.49
```

B-154 expands the same cached FRED fetch list to include the grouped read-only context series below, then stores a JSON-safe `fred_macro_snapshot` in the local run journal for later debrief/backtest analysis.

B-155 uses that journaled snapshot in the debrief engine to bucket matured recommendation outcomes by FRED macro condition. This remains analysis-only and does not change scoring, alerts, state transitions, or provider fetches.

B-156 adds opt-in B-011 macro backtest variants. `python scripts/run_backtest.py --macro-variants` fetches historical FRED observations when the key is configured, aligns each series to rebalance dates without lookahead, and compares defensive exposure filters against the baseline methodology.

## Useful API Capabilities

- `fred/series/observations`: fetch the observation history for specific known series IDs.
- `fred/series/search`: discover series by search text and tags.
- `fred/series/updates`: monitor series updated on the FRED server in the last two weeks.
- `fred/releases/dates`: build an economic release calendar. FRED notes that release dates are published by data sources and do not necessarily equal FRED/ALFRED availability time.

## Best Next Data Additions

These series were live-sampled successfully from AHADPI5. They should be added first as read-only context and debrief features, then considered for scoring only after B-011/B-153 backtests show value.

### Rates, Curve, And Inflation Expectations

- `DFF` - Federal Funds Effective Rate
- `SOFR` - Secured Overnight Financing Rate
- `DGS2` - 2-year Treasury yield
- `DGS10` - 10-year Treasury yield
- `DGS30` - 30-year Treasury yield
- `DTB3` - 3-month Treasury bill rate
- `T10YIE` - 10-year breakeven inflation
- `T5YIFR` - 5-year, 5-year forward inflation expectation

Use: rate-regime tiles, curve steepening/flattening context, and inflation-expectation pressure for sector rotation debriefs.

### Inflation And Price Pressure

- `CPIAUCSL` - CPI all items
- `CPILFESL` - core CPI
- `PCEPI` - PCE price index
- `PCEPILFE` - core PCE
- `PPIACO` - producer price index, all commodities
- `MICH` - University of Michigan inflation expectation

Use: inflation regime context, real-rate pressure, and sector playbook annotations.

### Liquidity And Balance Sheet

- `WALCL` - Fed total assets
- `RRPONTSYD` - overnight reverse repo
- `M2SL` - M2 money supply
- `BOGMBASE` - monetary base

Use: liquidity backdrop and risk-appetite debrief overlays. Do not turn these into hard gates until historical testing proves they improve outcomes.

### Growth, Labor, Housing, And Consumer

- `GDPC1` - real GDP
- `A191RL1Q225SBEA` - real GDP annualized growth rate
- `CFNAI` - Chicago Fed National Activity Index
- `PAYEMS` - nonfarm payrolls
- `ICSA` - initial claims
- `RSAFS` - advance retail sales
- `HOUST` - housing starts
- `PERMIT` - housing permits
- `UMCSENT` - University of Michigan consumer sentiment

Use: richer cycle classification and debrief explanations for why sector leadership changed.

### Credit And Stress

- `BAMLC0A0CM` - US corporate OAS
- `BAMLH0A0HYM2` - high-yield OAS, already used
- `NFCI` - financial conditions, already used
- `ANFCI` - adjusted financial conditions
- `STLFSI4` - St. Louis Fed Financial Stress Index
- `VIXCLS` - VIX close

Use: risk-off confirmation, credit-stress dashboard tiles, and alert/debrief context.

### Commodity Pressure

- `DCOILWTICO` - WTI crude oil
- `DHHNGSP` - Henry Hub natural gas

Use: energy/inflation context and sector debrief overlays.

### FX And Dollar Pressure

- `DTWEXBGS` - nominal broad U.S. dollar index

Use: liquidity and global-risk context, replacing the old `UUP` ETF proxy in the Market state header.

## Series To Recheck Before Using

The live scan did not return usable data for these IDs in the current environment:

- `RESBALNS`
- `NAPM`
- `GOLDAMGBD228NLBM`

Do not wire these into the app without a fresh lookup via `fred/series/search`.

## Recommended Implementation Order

1. Add a read-only FRED macro context expansion with grouped tiles and no scoring changes. Implemented in B-154.
2. Log the expanded macro snapshot into the B-153 run journal so the debrief engine can compare macro conditions with later outcomes. Implemented in B-154.
3. Summarize matured B-153 debrief outcomes by journaled FRED macro condition. Implemented in B-155.
4. Add B-011 backtest variants that test whether any new macro features improve decisions. Implemented in B-156.
5. Run the full real historical FRED + market macro-variant report and review the actual results. Implemented in B-157; the corrected 2026-05-22 AHADPI5 run used cache-bypassed Massive OHLCV, conservative FRED availability lags, a walk-forward OOS split, and produced no `candidate` rule.
6. Only promote validated FRED features into scoring, veto logic, alerts, or recommendations after a future evidence run beats the current methodology. Tracked as B-158 and currently blocked by the B-157 result.
7. Mirror the same evidence-first process for Massive historical OHLCV and timestamped provider data before changing Massive-derived criteria. Tracked as B-159 and B-160.
