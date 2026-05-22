# FRED Data Opportunities

Date checked: 2026-05-22
Runtime checked: AHADPI5, `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION`

The FRED key is configured on AHADPI5 and the current B-022 macro overlay fetched all 7 configured series successfully:

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

## Series To Recheck Before Using

The live scan did not return usable data for these IDs in the current environment:

- `RESBALNS`
- `NAPM`
- `GOLDAMGBD228NLBM`

Do not wire these into the app without a fresh lookup via `fred/series/search`.

## Recommended Implementation Order

1. Add a read-only FRED macro context expansion with grouped tiles and no scoring changes.
2. Log the expanded macro snapshot into the B-153 run journal so the debrief engine can compare macro conditions with later outcomes.
3. Add B-011 backtest variants that test whether any new macro features improve decisions.
4. Only promote validated features into scoring or veto logic after backtest evidence beats the current methodology.
