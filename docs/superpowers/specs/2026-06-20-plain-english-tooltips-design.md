# Plain-English Tooltips with Live Values — Design Spec

**Date:** 2026-06-20  
**Feature:** Rewrite all dashboard tooltips in plain language for retail investors, with actual current values interpolated at render time.  
**Target audience:** Retail investor — understands "buy/sell", "stock goes up/down", but not technical analysis jargon.

---

## Goal

Every tooltip in the Next.js dashboard should answer two questions for a non-expert:
1. **What is this?** — plain English, no academic citations, no formulas.
2. **What does this ticker's current value mean?** — actual number shown, threshold named, plain-language verdict ("this is a good sign / caution / red flag").

---

## Scope

### Files changed

| File | What changes |
|---|---|
| `web/lib/tooltips.ts` | Plain-English rewrites of all 4 dictionaries. Add `stateTooltip(state, sScore?, fScore?)` function. |
| `web/app/chart-primitives.tsx` | Rewrite `pillarReading()`. Expand `LightStatePill` to accept optional `sScore`/`fScore`. |
| `web/app/dashboard-screens-client.tsx` | Expand `StatusPill` to accept optional `sScore`/`fScore`. Update call sites that have row data. |

### Not in scope
- Tooltip engine (`TooltipRoot.tsx`) — no changes.
- Tooltip styling / positioning — no changes.
- Table column header tooltips (`State`, `S`, `F`, `RS Ratio`, `RS Momentum`) — these are generic (no specific ticker), rewrite text only, no value interpolation.
- `ActionRow` `StatusPill` — `decision.action` is a string like "BUY/SELL", not a state; no s_score available. Keep generic tooltip.

---

## Section 1 — `web/lib/tooltips.ts`

### 1a. Add `stateTooltip()` function

Replace direct usage of `STATE_TOOLTIP[state]` with a function that can interpolate live values:

```ts
export function stateTooltip(state: string, sScore?: number, fScore?: number): string
```

The function:
- Looks up the plain-English base text for the state
- If `sScore` is provided, appends: `"Score is [+X.XX] — [interpretation based on threshold]"`
- If `fScore` is provided, appends: `"Flow score is [+X.XX] — [buying/selling/neutral]"`
- Falls back to base text only if no scores provided (used by table headers, ActionRow)

`STATE_TOOLTIP` static dict remains exported for any legacy usage but is rewritten in plain English.

**Plain-English rewrites (same structure — what it is / what to do / what to watch):**

- **STAGE_2_BULLISH** — "BULLISH — this ETF is in a confirmed uptrend. The model sees strong buying pressure, rising momentum, and better performance than the broader market. This is the buy/hold zone — the strongest signal the model produces. Watch for: any drop in the flow score or momentum fading as an early warning sign."
- **HOLD** — "HOLD — the uptrend is intact but not firing on all cylinders. One or more signals are lagging (e.g. flow is neutral, or momentum is below average). Keep existing positions, but don't add new ones. Watch for: if the lagging signals recover, it upgrades to BULLISH. If they weaken, it may fall to WARNING."
- **WARNING** — "WARNING — this ETF is showing early signs of weakness. Momentum is fading, or selling pressure is building, even if price hasn't broken down yet. Consider reducing position size and tightening stops. Don't add new exposure here."
- **EXIT** — "EXIT — the model sees a confirmed breakdown. Multiple signals have failed at once: price has broken below key levels, momentum has turned negative, or buying pressure has dried up. This is the model's sell signal. Act on it rather than waiting for things to get worse."
- **BEARISH_STAGE_4** — "BEARISH — full downtrend. Price is falling, momentum is negative, and this ETF is consistently losing ground versus the market. Avoid entirely. No buy signal until basing begins and relative strength starts recovering."
- **STAGE_1_BASING** — "BASING — the prior downtrend has stalled and price is moving sideways. This is not a buy signal yet — it's a 'watch and wait' phase. A confirmed uptrend breakout (price clearing resistance on strong volume with improving momentum) would upgrade it to BULLISH. Many bases fail and go back to bearish."

### 1b. Rewrite `PILLAR_TOOLTIP` in plain English

Same structure (what it measures / bullish / bearish), no jargon:

- **cmf21** — "Money Flow (highest weight — 23%). Tracks whether big money is flowing into or out of this ETF. It does this by watching where the price closes each day relative to the day's high and low, weighted by trading volume. Think of it as: are buyers in control at the end of each day, and are they backing it up with volume? Bullish: reading above +0.05 means consistent closing near daily highs on heavy volume — a sign institutional buyers are accumulating. Above +0.10 is a strong signal. Bearish: below −0.05 means closing near daily lows on heavy volume — sellers are in control (distribution). Scale runs from −1 to +1; readings beyond ±0.30 are rare."
- **mom_12_1** — "Price Momentum (22% weight). Measures how much this ETF has gained or lost over the past 12 months, skipping the most recent month. The skip avoids a short-term 'rubber band' effect where strong recent moves briefly reverse. The key question isn't the raw number — it's how this ETF ranks versus everything else in the model. Bullish: positive return and ranked in the top 25% of the universe. Bearish: negative return or ranked in the bottom 25%. Rank within the universe matters more than the absolute percentage."
- **mansfield_rs** — "Relative Strength vs the Market (12% weight). Compares this ETF's 12-month performance against the S&P 500, centered at zero. A simple question: is this ETF beating the market or lagging behind? Bullish: above 0 and rising — outperforming the S&P 500. A reading above +1 is a strong setup. Bearish: below 0 — underperforming the market. Bullish setups with negative relative strength are lower quality and more likely to fail."
- **rs_ratio** — "Relative Strength Trend (15% weight). A smoothed, longer-term view of whether this ETF is outperforming or underperforming the market benchmark, centered at 100. Unlike the Mansfield measure, this one captures the trend of relative strength, not just a snapshot. Bullish: above 100 — outperforming. Strongest when it's rising and paired with improving RS momentum. Bearish: below 100 — underperforming. When both this and RS momentum are below 100, the ETF is in its weakest phase (Lagging quadrant)."
- **rs_momentum** — "Relative Strength Acceleration (8% weight). Measures whether this ETF's relative strength is getting better or getting worse right now. Think of it as the speed dial for the RS Trend reading above. Bullish: above 100 — relative strength is improving. This can be an early recovery signal even before the ETF starts outperforming overall. Bearish: below 100 — relative strength is deteriorating. ETFs tend to rotate through four phases: Leading → Weakening → Lagging → Improving, then back to Leading."
- **breadth_50d** — "Trend Filters (12% weight). Three independent checks that must all agree before the model considers a setup valid: (1) Is price above its 10-month average? (2) Is price above its 30-week moving average and rising? (3) Has this ETF gained in absolute terms over the past 12 months? These act as a safety gate. Bullish: all three pass — the trend is confirmed from multiple angles. Bearish: any filter fails — even strong momentum gets penalized if the underlying trend isn't confirmed. Think of these as 'is the road clear to drive?'"
- **cycle_tilt** — "Business Cycle Adjustment (8% weight). Different sectors tend to outperform at different stages of the economic cycle — early recovery, mid-cycle expansion, late cycle, and recession. This pillar nudges the score up or down based on which sectors historically do well in the current economic phase. Bullish tilt: this ETF's sector tends to outperform in the current phase (e.g. Technology and Industrials in a mid-cycle expansion). Bearish tilt: historically weak in the current phase. This is a modifier — it amplifies or dampens the overall score but never overrides price-based signals on its own."

### 1c. Rewrite `SCORE_TOOLTIP` in plain English

- **s_score** — "Composite Score (S). The model's overall verdict, combining all 7 signals into one number. Positive means more bullish signals than bearish; negative means the opposite. A score above +1.0 is a strong setup; below −1.0 is a weak one. Used to rank every ETF in the universe and drive buy/hold/sell decisions. A positive score alone isn't a buy signal — the ETF also needs to be in a BULLISH or HOLD state."
- **f_score** — "Flow Score (F). A sub-score focused purely on money flow signals — whether institutional money is moving in or out. Combines the main money flow reading (CMF), volume trend, a 14-day buying pressure index, and how many recent days showed heavy selling on falling price. Bullish: above 0 — net buying pressure. Bearish: below 0 — distribution pattern. Useful as an early warning: when the flow score deteriorates while price is still high, it often precedes a state downgrade."
- **cmf21** — "Money Flow (21-day). Net buying vs selling pressure as a fraction of total volume. Above 0 means buyers are closing price near daily highs on volume. Below 0 means sellers are closing price near daily lows."
- **momentum_pct** — "12-Month Momentum. How much this ETF has gained over the past year, skipping the most recent month. The raw percentage matters less than how it ranks against the rest of the universe — top 25% is the target zone."
- **rs_ratio** — "Relative Strength Trend. Smoothed measure of whether this ETF is outperforming (above 100) or underperforming (below 100) the benchmark. Best when it's above 100 and rising."
- **rs_momentum** — "Relative Strength Acceleration. Is the relative strength getting better (above 100) or worse (below 100) right now? Above 100 and rising = gaining on the market. Below 100 and falling = losing ground."

### 1d. Rewrite `RRG_QUADRANT_TOOLTIP` in plain English

- **Leading** — "Leading — this ETF is outperforming the market AND that outperformance is accelerating. The strongest quadrant. Best zone for new positions. Rotation eventually moves toward Weakening as momentum peaks, so watch for the RS momentum reading to start fading."
- **Weakening** — "Weakening — still outperforming the market overall, but losing steam. The rate of outperformance is slowing. Suitable for holding existing positions with tighter risk management; not ideal for new entries. Likely rotating toward Lagging unless momentum recovers."
- **Lagging** — "Lagging — underperforming the market and falling further behind. The weakest quadrant. Avoid new positions. May eventually rotate to Improving once the rate of decline starts to slow."
- **Improving** — "Improving — still underperforming the market overall, but momentum is turning positive — relative strength is starting to recover. Not yet a buy, but worth watching. Confirmation comes when it crosses into the Leading quadrant."

---

## Section 2 — `web/app/chart-primitives.tsx`

### 2a. Rewrite `pillarReading()` — plain English + threshold context

Each branch returns a sentence with: actual value shown → whether it's above/below the key threshold → plain-English verdict → contribution to S score.

Example rewrites:

**cmf21:**
Current: `"CMF flow is 0.14 and F-score is 0.32; flow can confirm or veto price strength."`  
New: `"XLK's money flow reading is +0.14 — above the +0.05 threshold where buying is considered active. More daily closes are happening near the top of the day's price range on high volume, which is what institutional buying looks like. Contributes +0.08 to the overall score (bullish support)."`

**mom_12_1:**
Current: `"XLK momentum input is 0.43; this pillar contributes 0.09 to S."`  
New: `"XLK's 12-month momentum is +43.6% — ranked in the top portion of the universe. Strong past performance relative to peers is a positive signal for continued outperformance. Contributes +0.09 to the overall score (bullish support)."`

**rs_ratio:**
Current: `"RRG ratio is 102.3; above 100 means relative strength is ahead of the benchmark."`  
New: `"XLK's relative strength trend is 102.3 — above 100, meaning it's been outperforming the market benchmark. The further above 100, the stronger the outperformance. Contributes +0.06 to the overall score (bullish support)."`

**rs_momentum:**
Current: `"RRG momentum is 97.1 and quadrant is Weakening; this captures acceleration or fading leadership."`  
New: `"XLK's relative strength momentum is 97.1 — just below 100, meaning the outperformance is slowing slightly. Quadrant: Weakening (outperforming but losing steam). Contributes −0.02 to the overall score (slight bearish drag)."`

**mansfield_rs:**
Current: `"Relative strength input is 0.82; positive values support Stage 2 evidence."`  
New: `"XLK's 12-month performance vs the S&P 500 is +0.82 — positive means it's beaten the market this year. A reading above 0 supports the bullish case; above +1.0 is a strong setup. Contributes +0.05 to the overall score (bullish support)."`

**breadth_50d:**
Current: `"Trend-filter input is 0.75; higher readings mean more confirmation from breadth and trend gates."`  
New: `"XLK's trend filter score is 0.75 out of 1.0 — meaning most of the three trend checks pass (price above 10-month average, above 30-week moving average, positive 12-month return). The closer to 1.0, the more the trend is confirmed. Contributes +0.04 to the overall score (bullish support)."`

**cycle_tilt:**
Current: `"Cycle tilt input is 0.42; macro context adjusts how much the setup is favored."`  
New: `"XLK's business cycle adjustment is +0.42 — the current economic phase (mid-cycle) has historically been favorable for Technology ETFs. This amplifies the bullish signals slightly. Contributes +0.03 to the overall score (bullish support)."`

### 2b. Expand `LightStatePill`

```tsx
// Before
function LightStatePill({ state }: { state: string })

// After
function LightStatePill({ state, sScore, fScore }: { state: string; sScore?: number; fScore?: number })
```

Tooltip generation:
```tsx
const tooltip = stateTooltip(state, sScore, fScore);
```

**Call site update** (line 346 in PillarHeatmap row):
```tsx
// Before
<LightStatePill state={row.state} />

// After
<LightStatePill state={row.state} sScore={row.s_score} fScore={row.f_score} />
```

---

## Section 3 — `web/app/dashboard-screens-client.tsx`

### 3a. Expand `StatusPill`

```tsx
// Before
function StatusPill({ status, light = false }: { status: string; light?: boolean })

// After
function StatusPill({ status, light = false, sScore, fScore }: { status: string; light?: boolean; sScore?: number; fScore?: number })
```

Tooltip generation:
```tsx
const tooltip = stateTooltip(status, sScore, fScore);
```

### 3b. Call site updates

| Line | Context | Update |
|---|---|---|
| 199 | `SnapshotCard` — has `row` | `<StatusPill status={row.state} sScore={row.s_score} fScore={row.f_score} />` |
| 213 | `ActionRow` — no row data | Leave as-is (`status={decision.action}`, generic tooltip) |
| 895 | FullTable row — has `row` | `<StatusPill status={row.state} sScore={row.s_score} fScore={row.f_score} />` |

### 3c. Card `<dt>` score tooltips (lines 201–204)

These labels (`S`, `F`, `RS-R`, `RS-M`) have the actual value visible in the `<dd>` right next to them. The tooltip rewrites from `SCORE_TOOLTIP` (Section 1c) are sufficient — no value interpolation needed here since the number is already visible.

---

## Testing

- **Manual:** hover state pills (heatmap, cards, FullTable), pillar bar segments, RRG dots, flow river bars, score column headers — verify plain-English text and actual values appear correctly.
- **No new unit tests required** — content changes only; no logic changes that affect scoring, state, or data flow.
- **TypeScript compilation:** `npm --prefix web run build` must pass with no type errors.

---

## Implementation order

1. Rewrite `tooltips.ts` — add `stateTooltip()`, rewrite all 4 dictionaries.
2. Update `chart-primitives.tsx` — `pillarReading()` rewrite, `LightStatePill` expansion.
3. Update `dashboard-screens-client.tsx` — `StatusPill` expansion, call site updates.
4. Build and verify.
