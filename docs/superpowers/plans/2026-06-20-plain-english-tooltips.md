# Plain-English Tooltips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite all dashboard tooltips in plain English for retail investors, interpolating each ticker's actual live values so the tooltip says what the number means, not just what the indicator is.

**Architecture:** Three files change. `tooltips.ts` gets a new `stateTooltip()` function and plain-English rewrites of all 4 dictionaries. `chart-primitives.tsx` gets a rewritten `pillarReading()` (with actual value + threshold verdict) and an expanded `LightStatePill` that accepts s/f scores. `dashboard-screens-client.tsx` gets an expanded `StatusPill` and two call-site updates. No new files. No new unit tests (content-only change verified by TypeScript build + manual hover).

**Tech Stack:** Next.js 15, TypeScript, bespoke CSS. No UI library.

## Global Constraints

- No changes to `TooltipRoot.tsx`, `globals.css`, or tooltip engine.
- No changes to scoring, state machine, data fetching, or any Python files.
- TypeScript strict mode — all new function signatures must satisfy existing types.
- `npm --prefix web run build` must pass with zero type errors before each commit.
- Plain English only — no academic citations, no raw formulas, no jargon.
- Every tooltip that has access to a ticker's row data must show the actual current value.

---

### Task 1: Rewrite tooltips.ts — plain-English content + stateTooltip() function

**Files:**
- Modify: `web/lib/tooltips.ts` (full rewrite)

**Interfaces:**
- Produces: `stateTooltip(state: string, sScore?: number, fScore?: number): string` — consumed by Tasks 2 and 3.
- Produces: `STATE_TOOLTIP`, `PILLAR_TOOLTIP`, `SCORE_TOOLTIP`, `RRG_QUADRANT_TOOLTIP` — same names/shapes as before, plain-English content.

- [ ] **Step 1: Replace the full content of `web/lib/tooltips.ts`**

```typescript
/**
 * Plain-English tooltip content for all major indicators.
 * Target audience: retail investor — knows buy/sell but not technical analysis.
 * Each entry: (1) what it measures in plain terms, (2) what's bullish, (3) what's bearish.
 */

export const STATE_TOOLTIP: Record<string, string> = {
  STAGE_2_BULLISH:
    "BULLISH — this ETF is in a confirmed uptrend. The model sees strong buying pressure, rising momentum, and better performance than the broader market. " +
    "This is the buy/hold zone — the strongest signal the model produces. " +
    "Watch for: any drop in the flow score or momentum fading as an early warning sign.",

  HOLD:
    "HOLD — the uptrend is intact but not firing on all cylinders. One or more signals are lagging (e.g. flow is neutral, or momentum is below average). " +
    "Keep existing positions, but don't add new ones. " +
    "Watch for: if the lagging signals recover, it upgrades to BULLISH. If they weaken, it may fall to WARNING.",

  WARNING:
    "WARNING — this ETF is showing early signs of weakness. Momentum is fading, or selling pressure is building, even if price hasn't broken down yet. " +
    "Consider reducing position size and tightening stops. Don't add new exposure here.",

  EXIT:
    "EXIT — the model sees a confirmed breakdown. Multiple signals have failed at once: price has broken below key levels, momentum has turned negative, or buying pressure has dried up. " +
    "This is the model's sell signal. Act on it rather than waiting for things to get worse.",

  BEARISH_STAGE_4:
    "BEARISH — full downtrend. Price is falling, momentum is negative, and this ETF is consistently losing ground versus the market. " +
    "Avoid entirely. No buy signal until basing begins and relative strength starts recovering.",

  STAGE_1_BASING:
    "BASING — the prior downtrend has stalled and price is moving sideways. This is not a buy signal yet — it's a watch and wait phase. " +
    "A confirmed uptrend breakout (price clearing resistance on strong volume with improving momentum) would upgrade it to BULLISH. " +
    "Many bases fail and go back to bearish.",
};

/**
 * stateTooltip — builds a plain-English tooltip for a state pill,
 * optionally appending the ticker's actual composite score and flow score
 * with plain-language interpretation of each value.
 */
export function stateTooltip(state: string, sScore?: number, fScore?: number): string {
  const base = STATE_TOOLTIP[state] ?? `State: ${state.replaceAll("_", " ")}`;
  const parts: string[] = [base];

  if (sScore !== undefined && sScore !== null && Number.isFinite(sScore)) {
    const sign = sScore >= 0 ? "+" : "";
    const interp =
      sScore >= 1.5 ? "a strong bullish setup" :
      sScore >= 0.5 ? "a moderate bullish setup" :
      sScore >= 0   ? "a weak bullish setup" :
      sScore >= -0.5 ? "a weak bearish setup" :
      sScore >= -1.5 ? "a moderate bearish setup" :
                       "a strong bearish setup";
    parts.push(`Composite score: ${sign}${sScore.toFixed(2)} — ${interp}.`);
  }

  if (fScore !== undefined && fScore !== null && Number.isFinite(fScore)) {
    const sign = fScore >= 0 ? "+" : "";
    const flowVerdict =
      fScore >= 0.1  ? "institutional buying is active" :
      fScore >= 0    ? "flow is neutral to slightly positive" :
      fScore >= -0.1 ? "flow is neutral to slightly negative" :
                       "distribution (selling pressure) is present";
    parts.push(`Flow score: ${sign}${fScore.toFixed(2)} — ${flowVerdict}.`);
  }

  return parts.join(" ");
}

export const PILLAR_TOOLTIP: Record<string, string> = {
  cmf21:
    "Money Flow (highest weight — 23%). Tracks whether big money is flowing into or out of this ETF. " +
    "It watches where the price closes each day relative to the day's high and low, weighted by trading volume. " +
    "Think of it as: are buyers in control at the end of each day, and are they backing it up with volume? " +
    "Bullish: above +0.05 means consistent closing near daily highs on heavy volume — a sign of accumulation. Above +0.10 is a strong signal. " +
    "Bearish: below −0.05 means closing near daily lows on heavy volume — sellers are in control. Scale runs from −1 to +1.",

  mom_12_1:
    "Price Momentum (22% weight). Measures how much this ETF has gained or lost over the past 12 months, skipping the most recent month. " +
    "The skip avoids a short-term reversal effect where strong recent moves briefly snap back. " +
    "The key question isn't the raw number — it's how this ETF ranks versus everything else in the model. " +
    "Bullish: positive return and ranked in the top 25% of the universe. " +
    "Bearish: negative return or ranked in the bottom 25%. Rank within the universe matters more than the absolute percentage.",

  mansfield_rs:
    "Relative Strength vs the Market (12% weight). Compares this ETF's 12-month performance against the S&P 500, centered at zero. " +
    "A simple question: is this ETF beating the market or lagging behind? " +
    "Bullish: above 0 and rising — outperforming the S&P 500. A reading above +1 is a strong setup. " +
    "Bearish: below 0 — underperforming the market. Bullish setups with negative relative strength are lower quality and more likely to fail.",

  rs_ratio:
    "Relative Strength Trend (15% weight). A smoothed, longer-term view of whether this ETF is outperforming or underperforming the market benchmark, centered at 100. " +
    "Unlike a simple comparison, this captures the trend of relative strength, not just a snapshot. " +
    "Bullish: above 100 — outperforming. Strongest when it's rising and paired with improving RS momentum. " +
    "Bearish: below 100 — underperforming. When both this and RS momentum are below 100, the ETF is in its weakest phase.",

  rs_momentum:
    "Relative Strength Acceleration (8% weight). Measures whether this ETF's relative strength is getting better or getting worse right now. " +
    "Think of it as the speed dial for the RS Trend reading. " +
    "Bullish: above 100 — relative strength is improving. This can be an early recovery signal even before the ETF starts outperforming overall. " +
    "Bearish: below 100 — relative strength is deteriorating. ETFs tend to rotate through four phases: Leading → Weakening → Lagging → Improving.",

  breadth_50d:
    "Trend Filters (12% weight). Three independent checks that must all agree before the model considers a setup valid: " +
    "(1) Is price above its 10-month average? " +
    "(2) Is price above its 30-week moving average and rising? " +
    "(3) Has this ETF gained in absolute terms over the past 12 months? " +
    "These act as a safety gate. Bullish: all three pass — the trend is confirmed from multiple angles. " +
    "Bearish: any filter fails — even strong momentum gets penalized if the underlying trend isn't confirmed.",

  cycle_tilt:
    "Business Cycle Adjustment (8% weight). Different sectors tend to outperform at different stages of the economic cycle — early recovery, mid-cycle expansion, late cycle, and recession. " +
    "This pillar nudges the score up or down based on which sectors historically do well in the current economic phase. " +
    "Bullish tilt: this ETF's sector tends to outperform in the current phase (e.g. Technology in mid-cycle expansion). " +
    "Bearish tilt: historically weak in the current phase. This is a modifier — it amplifies or dampens the overall score but never overrides price-based signals on its own.",
};

export const SCORE_TOOLTIP: Record<string, string> = {
  s_score:
    "Composite Score (S). The model's overall verdict, combining all 7 signals into one number. " +
    "Positive means more bullish signals than bearish; negative means the opposite. " +
    "Above +1.0 is a strong setup; below −1.0 is weak. " +
    "Used to rank every ETF in the universe and drive buy/hold/sell decisions. " +
    "A positive score alone isn't a buy signal — the ETF also needs to be in a BULLISH or HOLD state.",

  f_score:
    "Flow Score (F). A sub-score focused purely on money flow signals — whether institutional money is moving in or out. " +
    "Combines the main money flow reading (CMF), volume trend, a 14-day buying pressure index, and how many recent days showed heavy selling. " +
    "Bullish: above 0 — net buying pressure. Bearish: below 0 — distribution pattern. " +
    "Useful as an early warning: when the flow score deteriorates while price is still high, it often precedes a state downgrade.",

  cmf21:
    "Money Flow (21-day). Net buying vs selling pressure as a fraction of total volume. " +
    "Above 0 means buyers are closing price near daily highs on volume. Below 0 means sellers are closing price near daily lows.",

  momentum_pct:
    "12-Month Momentum. How much this ETF has gained over the past year, skipping the most recent month. " +
    "The raw percentage matters less than how it ranks against the rest of the universe — top 25% is the target zone.",

  rs_ratio:
    "Relative Strength Trend. Smoothed measure of whether this ETF is outperforming (above 100) or underperforming (below 100) the benchmark. " +
    "Best when it's above 100 and rising.",

  rs_momentum:
    "Relative Strength Acceleration. Is relative strength getting better (above 100) or worse (below 100) right now? " +
    "Above 100 and rising = gaining on the market. Below 100 and falling = losing ground.",
};

export const RRG_QUADRANT_TOOLTIP: Record<string, string> = {
  Leading:
    "Leading — this ETF is outperforming the market AND that outperformance is accelerating. " +
    "The strongest quadrant. Best zone for new positions. " +
    "Rotation eventually moves toward Weakening as momentum peaks, so watch for the RS momentum reading to start fading.",

  Weakening:
    "Weakening — still outperforming the market overall, but losing steam. The rate of outperformance is slowing. " +
    "Suitable for holding existing positions with tighter risk management; not ideal for new entries. " +
    "Likely rotating toward Lagging unless momentum recovers.",

  Lagging:
    "Lagging — underperforming the market and falling further behind. The weakest quadrant. " +
    "Avoid new positions. May eventually rotate to Improving once the rate of decline starts to slow.",

  Improving:
    "Improving — still underperforming the market overall, but momentum is turning positive — relative strength is starting to recover. " +
    "Not yet a buy, but worth watching. Confirmation comes when it crosses into the Leading quadrant.",
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
npm --prefix web run build
```

Expected: build completes with no type errors. (The exported names and shapes are unchanged; stateTooltip is additive.)

- [ ] **Step 3: Commit**

```powershell
git add web/lib/tooltips.ts
git commit -m "feat: plain-English tooltip content + stateTooltip() function"
```

---

### Task 2: Rewrite pillarReading() + expand LightStatePill in chart-primitives.tsx

**Files:**
- Modify: `web/app/chart-primitives.tsx`

**Interfaces:**
- Consumes: `stateTooltip(state, sScore?, fScore?)` from `web/lib/tooltips.ts` (Task 1).
- Modifies internal `pillarReading(row, pillar)` — same signature, richer return value.
- Modifies `LightStatePill` — adds optional `sScore?: number`, `fScore?: number` props.

- [ ] **Step 1: Update the import line at the top of `web/app/chart-primitives.tsx`**

Find:
```typescript
import { PILLAR_TOOLTIP, RRG_QUADRANT_TOOLTIP, SCORE_TOOLTIP, STATE_TOOLTIP } from "../lib/tooltips";
```

Replace with:
```typescript
import { PILLAR_TOOLTIP, RRG_QUADRANT_TOOLTIP, SCORE_TOOLTIP, stateTooltip } from "../lib/tooltips";
```

(`STATE_TOOLTIP` is no longer used directly — `stateTooltip()` handles the lookup internally.)

- [ ] **Step 2: Rewrite `pillarReading()` with plain English and actual value context**

Find the entire `pillarReading` function:
```typescript
function pillarReading(row: SnapshotRow, pillar: PillarContribution): string {
  if (pillar.key === "mom_12_1") return `${row.ticker} momentum input is ${fmt(pillar.raw, 2)}; this pillar contributes ${fmt(pillar.contribution, 2)} to S.`;
  if (pillar.key === "mansfield_rs") return `Relative strength input is ${fmt(pillar.raw, 2)}; positive values support Stage 2 evidence, negative values weaken it.`;
  if (pillar.key === "rs_ratio") return `RRG ratio is ${fmt(row.rs_ratio, 1)}; above 100 means relative strength is ahead of the benchmark.`;
  if (pillar.key === "rs_momentum") return `RRG momentum is ${fmt(row.rs_momentum, 1)} and quadrant is ${row.quadrant}; this captures acceleration or fading leadership.`;
  if (pillar.key === "breadth_50d") return `Trend-filter input is ${fmt(pillar.raw, 2)}; higher readings mean more confirmation from breadth and trend gates.`;
  if (pillar.key === "cycle_tilt") return `Cycle tilt input is ${fmt(pillar.raw, 2)}; macro context adjusts how much the setup is favored.`;
  return `CMF flow is ${fmt(row.cmf21, 2)} and F-score is ${fmt(row.f_score, 2)}; flow can confirm or veto price strength.`;
}
```

Replace with:
```typescript
function pillarReading(row: SnapshotRow, pillar: PillarContribution): string {
  const sign = pillar.contribution >= 0 ? "+" : "";
  const supportLabel = pillar.contribution >= 0 ? "bullish support" : "bearish drag";
  const contrib = `Contributes ${sign}${fmt(pillar.contribution, 2)} to the overall score (${supportLabel}).`;

  if (pillar.key === "cmf21") {
    const val = typeof row.cmf21 === "number" && Number.isFinite(row.cmf21) ? row.cmf21 : pillar.raw * 0.25;
    const valSign = val >= 0 ? "+" : "";
    const verdict =
      val >= 0.10 ? "strong buying pressure — institutions are accumulating" :
      val >= 0.05 ? "mild buying pressure — more closes near daily highs on volume" :
      val >= -0.05 ? "neutral — no clear buying or selling dominance" :
      val >= -0.10 ? "mild selling pressure — more closes near daily lows on volume" :
                     "strong selling pressure — distribution pattern";
    return `${row.ticker}'s money flow reading is ${valSign}${fmt(val, 2)} (thresholds: above +0.05 = buying active, below −0.05 = selling active). ${verdict.charAt(0).toUpperCase() + verdict.slice(1)}. ${contrib}`;
  }

  if (pillar.key === "mom_12_1") {
    const pctVal = pillar.raw * 100;
    const pctSign = pctVal >= 0 ? "+" : "";
    const verdict =
      pctVal >= 20 ? "very strong momentum — top performers in the universe" :
      pctVal >= 5  ? "positive momentum — trending higher" :
      pctVal >= 0  ? "slightly positive — marginal uptrend" :
      pctVal >= -10 ? "negative momentum — downtrend under way" :
                      "strongly negative — significant downtrend";
    return `${row.ticker}'s 12-month momentum is ${pctSign}${fmt(pctVal, 1)}%. ${verdict.charAt(0).toUpperCase() + verdict.slice(1)}. The model ranks this against all other ETFs — relative rank matters more than the raw number. ${contrib}`;
  }

  if (pillar.key === "mansfield_rs") {
    const val = pillar.raw * 100;
    const valSign = val >= 0 ? "+" : "";
    const verdict =
      val >= 1  ? "strongly outperforming the S&P 500" :
      val >= 0  ? "outperforming the S&P 500" :
      val >= -1 ? "underperforming the S&P 500" :
                  "significantly underperforming the S&P 500";
    return `${row.ticker}'s relative strength vs the market is ${valSign}${fmt(val, 2)} (above 0 = beating the S&P 500; above +1 = strong setup). ${verdict.charAt(0).toUpperCase() + verdict.slice(1)}. ${contrib}`;
  }

  if (pillar.key === "rs_ratio") {
    const val = typeof row.rs_ratio === "number" && Number.isFinite(row.rs_ratio) ? row.rs_ratio : 100;
    const verdict =
      val >= 102 ? "clearly outperforming the benchmark" :
      val >= 100 ? "slightly ahead of the benchmark" :
      val >= 98  ? "slightly behind the benchmark" :
                   "clearly underperforming the benchmark";
    return `${row.ticker}'s relative strength trend is ${fmt(val, 1)} (above 100 = outperforming, below 100 = underperforming). ${verdict.charAt(0).toUpperCase() + verdict.slice(1)}. ${contrib}`;
  }

  if (pillar.key === "rs_momentum") {
    const val = typeof row.rs_momentum === "number" && Number.isFinite(row.rs_momentum) ? row.rs_momentum : 100;
    const verdict =
      val >= 102 ? "relative strength is accelerating — gaining on the market" :
      val >= 100 ? "relative strength is slightly improving" :
      val >= 98  ? "relative strength is slightly fading" :
                   "relative strength is decelerating — losing ground";
    return `${row.ticker}'s relative strength momentum is ${fmt(val, 1)}, quadrant: ${row.quadrant} (above 100 = improving, below 100 = fading). ${verdict.charAt(0).toUpperCase() + verdict.slice(1)}. ${contrib}`;
  }

  if (pillar.key === "breadth_50d") {
    const val = pillar.raw;
    const valSign = val >= 0 ? "+" : "";
    const verdict =
      val >= 0.5  ? "all trend checks are passing — strong confirmation" :
      val >= 0    ? "most trend checks pass — moderate confirmation" :
      val >= -0.5 ? "some trend checks failing — weakening trend" :
                    "most trend checks failing — downtrend confirmed";
    return `${row.ticker}'s trend filter score is ${valSign}${fmt(val, 2)} (checks: price above 10-month average, above 30-week moving average, positive 12-month return). ${verdict.charAt(0).toUpperCase() + verdict.slice(1)}. ${contrib}`;
  }

  if (pillar.key === "cycle_tilt") {
    const val = pillar.raw;
    const valSign = val >= 0 ? "+" : "";
    const verdict =
      val >= 0.3  ? "strongly favored in the current economic phase" :
      val >= 0    ? "moderately favored in the current economic phase" :
      val >= -0.3 ? "slightly disfavored in the current economic phase" :
                    "historically weak in the current economic phase";
    return `${row.ticker}'s business cycle adjustment is ${valSign}${fmt(val, 2)} — ${verdict}. This modifier amplifies or reduces the score based on which sectors tend to outperform in the current cycle. ${contrib}`;
  }

  return `${row.ticker}'s reading is ${fmt(pillar.raw, 2)}. ${contrib}`;
}
```

- [ ] **Step 3: Expand `LightStatePill` to accept optional score props**

Find:
```typescript
function LightStatePill({ state }: { state: string }) {
  const tooltip = STATE_TOOLTIP[state] ?? `State: ${state.replaceAll("_", " ")}`;
  return <span className={`light-state-pill ${stateTone(state)}`} data-tooltip={tooltip} style={{ cursor: "help" }}>{compactStateLabel(state)}</span>;
}
```

Replace with:
```typescript
function LightStatePill({ state, sScore, fScore }: { state: string; sScore?: number; fScore?: number }) {
  const tooltip = stateTooltip(state, sScore, fScore);
  return <span className={`light-state-pill ${stateTone(state)}`} data-tooltip={tooltip} style={{ cursor: "help" }}>{compactStateLabel(state)}</span>;
}
```

- [ ] **Step 4: Update the LightStatePill call site in PillarHeatmap to pass scores**

Find (inside the PillarHeatmap row render, around line 346):
```typescript
<LightStatePill state={row.state} />
```

Replace with:
```typescript
<LightStatePill state={row.state} sScore={row.s_score} fScore={row.f_score} />
```

- [ ] **Step 5: Verify TypeScript compiles**

```powershell
npm --prefix web run build
```

Expected: zero type errors. The `LightStatePill` props are additive (optional); the removed `STATE_TOOLTIP` import is now unused so no breakage.

- [ ] **Step 6: Commit**

```powershell
git add web/app/chart-primitives.tsx
git commit -m "feat: plain-English pillar tooltips with live values + LightStatePill scores"
```

---

### Task 3: Expand StatusPill + update call sites in dashboard-screens-client.tsx

**Files:**
- Modify: `web/app/dashboard-screens-client.tsx`

**Interfaces:**
- Consumes: `stateTooltip(state, sScore?, fScore?)` from `web/lib/tooltips.ts` (Task 1).
- Modifies `StatusPill` — adds optional `sScore?: number`, `fScore?: number` props.
- Updates 2 call sites that have row data (SnapshotCard line ~199, FullTable row line ~895).
- Leaves ActionRow call site unchanged (no row data available there).

- [ ] **Step 1: Update the import line at the top of `web/app/dashboard-screens-client.tsx`**

Find:
```typescript
import { STATE_TOOLTIP, SCORE_TOOLTIP } from "../lib/tooltips";
```

Replace with:
```typescript
import { SCORE_TOOLTIP, stateTooltip } from "../lib/tooltips";
```

- [ ] **Step 2: Expand `StatusPill` to accept optional score props**

Find:
```typescript
function StatusPill({ status, light = false }: { status: string; light?: boolean }) {
  const bg = stateColor(status, light);
  const label = stateShortLabel(status) || status || "unknown";
  const tooltip = STATE_TOOLTIP[status] ?? `State: ${status.replaceAll("_", " ")}`;
  return (
    <span
      className="state-pill mono"
      style={{ background: bg, color: "#fff", padding: "2px 9px", borderRadius: "11px",
               fontSize: "0.72rem", fontWeight: 600, letterSpacing: "0.03em",
               display: "inline-block", lineHeight: 1.4, cursor: "help" }}
      data-tooltip={tooltip}
    >
      {label}
    </span>
  );
}
```

Replace with:
```typescript
function StatusPill({ status, light = false, sScore, fScore }: { status: string; light?: boolean; sScore?: number; fScore?: number }) {
  const bg = stateColor(status, light);
  const label = stateShortLabel(status) || status || "unknown";
  const tooltip = stateTooltip(status, sScore, fScore);
  return (
    <span
      className="state-pill mono"
      style={{ background: bg, color: "#fff", padding: "2px 9px", borderRadius: "11px",
               fontSize: "0.72rem", fontWeight: 600, letterSpacing: "0.03em",
               display: "inline-block", lineHeight: 1.4, cursor: "help" }}
      data-tooltip={tooltip}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 3: Update StatusPill call site in SnapshotCard (has row data)**

Find (inside the SnapshotCard component, where `StatusPill` is rendered next to the score dl):
```typescript
      <StatusPill status={row.state} />
      <dl>
        <div><dt data-tooltip={SCORE_TOOLTIP.s_score} style={{ cursor: "help" }}>S</dt><dd>{fmt(row.s_score)}</dd></div>
```

Replace with:
```typescript
      <StatusPill status={row.state} sScore={row.s_score} fScore={row.f_score} />
      <dl>
        <div><dt data-tooltip={SCORE_TOOLTIP.s_score} style={{ cursor: "help" }}>S</dt><dd>{fmt(row.s_score)}</dd></div>
```

- [ ] **Step 4: Update StatusPill call site in FullTable row (has row data)**

Find (inside the FullTable tbody row render):
```typescript
                  <td><StatusPill status={row.state} /></td>
```

Replace with:
```typescript
                  <td><StatusPill status={row.state} sScore={row.s_score} fScore={row.f_score} /></td>
```

- [ ] **Step 5: Verify TypeScript compiles with zero errors**

```powershell
npm --prefix web run build
```

Expected: build passes cleanly. All 3 tasks are now in effect.

- [ ] **Step 6: Manual smoke — hover tooltips in browser**

Start the dev server and check 5 tooltip types:

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npm run dev
```

Open `http://localhost:3100/?presentation=c` and hover:
1. Any state pill (BULLISH / WARN / EXIT) — should show state description + "Composite score: +X.XX" + "Flow score: +X.XX"
2. Any pillar bar segment — should show plain-English pillar description + ticker's actual value + verdict + contribution
3. RRG dot — should show quadrant plain-English description + RS-Ratio + RS-Momentum values
4. Card `S` label — should show plain-English composite score description
5. FullTable `State` column pill — same as #1 with live scores

- [ ] **Step 7: Commit**

```powershell
git add web/app/dashboard-screens-client.tsx
git commit -m "feat: plain-English state pills with live S/F scores in StatusPill"
```

- [ ] **Step 8: Push**

```powershell
git push origin main
```
