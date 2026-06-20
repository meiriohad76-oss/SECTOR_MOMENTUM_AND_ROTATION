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
      sScore >= 1.5  ? "a strong bullish setup" :
      sScore >= 0.5  ? "a moderate bullish setup" :
      sScore >= 0    ? "a weak bullish setup" :
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
