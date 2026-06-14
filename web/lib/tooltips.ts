/**
 * Rich tooltip content for all major indicators.
 * Each entry explains: (1) what the indicator does, (2) what's bullish, (3) what's bearish.
 */

export const STATE_TOOLTIP: Record<string, string> = {
  STAGE_2_BULLISH:
    "Stage 2 Uptrend (Weinstein). Confirmed uptrend — price above rising 30-week MA, momentum positive, RS outperforming benchmark, institutional flow supporting. " +
    "Bullish: All or most of the 7 pillars are aligned. This is the buy/hold zone — highest-conviction long entry in the model. " +
    "Watch for: any deterioration in CMF, RS-Ratio drop below 100, or momentum reversal as early-warning signs.",

  HOLD:
    "Hold — uptrend is intact but full bullish conviction is not reached. Price trend is positive but one or more pillars are lagging (e.g. RS flat, flow neutral, or momentum below top quartile). " +
    "Bullish lean: Maintain existing positions, do not add. Not ideal for new entries. " +
    "Watch for: upgrade to BULLISH if lagging pillars recover, or deterioration to WARNING if trend weakens.",

  WARNING:
    "Warning — active deterioration signal. Momentum is fading, distribution volume is rising, or RS is starting to underperform. Price may still be above the MA but trend quality is declining. " +
    "Bearish lean: Reduce position size, tighten stops. Do not add new exposure. " +
    "Action: Treat as a yellow flag — not yet a confirmed exit, but early risk management is warranted.",

  EXIT:
    "Exit — confirmed breakdown. Price breaking key moving average support, momentum turned negative, or multiple pillars simultaneously failing. The model has sufficient evidence of trend failure to act. " +
    "Bearish: Close or significantly reduce position. " +
    "Do not wait for Stage 4 confirmation — EXIT is the model's actionable sell signal.",

  BEARISH_STAGE_4:
    "Stage 4 Downtrend (Weinstein). Full bear state — price below a declining 30-week MA, momentum negative, RS consistently underperforming the benchmark, flow negative. " +
    "Bearish: Avoid all long exposure. This is the weakest end of the ranked universe. " +
    "No entry signal until Stage 1 basing begins and RS starts to recover.",

  STAGE_1_BASING:
    "Stage 1 Base (Weinstein). Consolidation/accumulation phase after a prior downtrend. Price has stopped falling but no confirmed uptrend yet. " +
    "Neutral: Not a buy signal. Waiting for Stage 2 breakout — price clearing base resistance on expanding volume with improving RS. " +
    "Watch for: strengthening Mansfield RS and CMF turning positive as the earliest signs of a pending breakout. Many bases fail and revert to Stage 4.",
};

export const PILLAR_TOOLTIP: Record<string, string> = {
  mom_12_1:
    "12-1 Price Momentum (22% weight — largest single pillar). Measures 12-month price return minus the most recent month. " +
    "The one-month skip avoids the short-term reversal effect (Jegadeesh & Titman 1993). " +
    "Bullish: Positive and in the top quartile of the universe (z-score > 0). Best setups are top decile. " +
    "Bearish: Negative or bottom quartile. Cross-sectional rank matters more than absolute value.",

  mansfield_rs:
    "Mansfield Relative Strength (Weinstein 1988, 12% weight). Compares 52-week price performance vs the S&P 500, normalized to zero. " +
    "Bullish: Above 0 and rising — outperforming the market. Strong setups show Mansfield RS > +1. " +
    "Bearish: Below 0 — underperforming the S&P 500. Stage 2 setups with negative Mansfield RS are lower conviction and more likely to fail.",

  rs_ratio:
    "RRG RS-Ratio (de Kempenaer 2004, 15% weight). Smoothed relative strength vs the benchmark, centered at 100. Part of the Relative Rotation Graph framework. " +
    "Bullish: Above 100 — outperforming the benchmark. Strongest when rising and paired with RS-Momentum > 100 (Leading quadrant). " +
    "Bearish: Below 100 — underperforming. When RS-Ratio < 100 and RS-Momentum < 100, instrument is in the Lagging quadrant (weakest).",

  rs_momentum:
    "RRG RS-Momentum (8% weight). Rate of change of the RS-Ratio — is relative strength improving or fading? Centered at 100. " +
    "Bullish: Above 100 — RS-Ratio is rising, gaining on the benchmark. Leading quadrant: both RS-Ratio and RS-Momentum > 100. Improving quadrant: RS-Ratio < 100 but RS-Momentum > 100 (early recovery). " +
    "Bearish: Below 100 — RS-Ratio is falling. Classic clockwise rotation: Leading → Weakening → Lagging → Improving.",

  breadth_50d:
    "Binary Trend & Breadth Filters (12% weight). Three independent gating checks applied simultaneously: " +
    "(1) Faber 10-month MA filter — price above 10-month moving average signals risk-on. " +
    "(2) Weinstein Stage 2 gate — price above rising 30-week MA. " +
    "(3) Antonacci absolute momentum — 12-month absolute return positive. " +
    "Bullish: All filters pass (score near +1). Each filter confirms the uptrend from a different angle. " +
    "Bearish: Any filter fails (score near 0 or negative). Acts as a veto — even strong momentum is penalised when trend filters fail.",

  cycle_tilt:
    "Business-Cycle Sector Tilt (Stovall 1996 / Fidelity, 8% weight). Adjusts composite score based on which sectors historically outperform in the current economic cycle phase (Early / Mid / Late / Recession). " +
    "Bullish tilt: Sector is historically favored in the current phase — e.g. Technology and Industrials in Mid cycle; Energy and Materials in Late cycle. " +
    "Bearish tilt: Sector historically weak in current phase — e.g. Consumer Staples in Early cycle. " +
    "Modifier only — amplifies or dampens the composite score but does not override price-based signals. Smallest single impact at 8% weight.",

  cmf21:
    "Chaikin Money Flow — 21-day (23% weight — highest-weighted pillar). Measures institutional buying vs selling pressure by tracking where price closes within the day's high-low range, weighted by volume. " +
    "Formula: sum(money-flow-multiplier × volume) ÷ total-21-day-volume. Multiplier = (close − low − (high − close)) ÷ (high − low). " +
    "Bullish: CMF > +0.05 — closes consistently near daily highs on high volume (accumulation). Strong signal: > +0.10. " +
    "Bearish: CMF < −0.05 — closes near daily lows on high volume (distribution). Strong signal: < −0.10. " +
    "Range: −1 to +1; sectors rarely exceed ±0.30 in practice.",
};

export const SCORE_TOOLTIP: Record<string, string> = {
  s_score:
    "Composite Setup Score (S). Weighted sum across all 7 pillars: institutional flow 23%, price momentum 22%, RS-Ratio 15%, Mansfield RS 12%, trend filter 12%, business-cycle tilt 8%, RS-Momentum 8%. " +
    "Bullish: S > 0 (more pillar weight on the bullish side). Strong setup: S > 1.5. " +
    "Bearish: S < 0. Weak: S < −1.5. " +
    "Used to rank all instruments and drive state-machine transitions. Positive S alone does not trigger a buy — state must also be BULLISH.",

  f_score:
    "Flow Score (F). Sub-composite of the institutional money flow pillar. Combines CMF(21), OBV slope, Money Flow Index (14-day), and distribution day count. " +
    "Bullish: F > 0 — net buying pressure; closes near daily highs on volume, OBV rising, MFI above 50. " +
    "Bearish: F < 0 — distribution pattern; closes near lows on volume, OBV falling, MFI below 50. " +
    "Leading indicator: F deteriorating while price is still high is an early warning sign before state transitions.",

  cmf21:
    "Chaikin Money Flow — 21-day window. Net buying vs selling pressure as a fraction of total volume. " +
    "Bullish: > +0.05 (accumulation — closing near highs on volume). Strong: > +0.10. " +
    "Bearish: < −0.05 (distribution — closing near lows on volume). Strong: < −0.10. " +
    "Range: −1 to +1.",

  momentum_pct:
    "12-1 Price Momentum. 12-month return minus the most recent month (skip-month removes short-term reversal bias). " +
    "Bullish: Positive and high-ranked in the universe. Top quartile is the target zone. " +
    "Bearish: Negative or low-ranked. Cross-sectional rank within the universe matters more than the absolute number.",

  rs_ratio:
    "RRG RS-Ratio. Relative strength vs benchmark, smoothed and centered at 100. " +
    "Bullish: > 100 (outperforming). Best when rising. " +
    "Bearish: < 100 (underperforming). Below 100 and falling = Lagging quadrant.",

  rs_momentum:
    "RRG RS-Momentum. Rate of change of RS-Ratio. Centered at 100. " +
    "Bullish: > 100 (RS-Ratio is improving). " +
    "Bearish: < 100 (RS-Ratio is deteriorating). " +
    "Quadrants — Leading: both > 100. Weakening: Ratio > 100, Mom < 100. Lagging: both < 100. Improving: Ratio < 100, Mom > 100.",
};

export const RRG_QUADRANT_TOOLTIP: Record<string, string> = {
  Leading:
    "Leading quadrant: RS-Ratio > 100 AND RS-Momentum > 100. " +
    "Currently outperforming the benchmark and that outperformance is accelerating. " +
    "Strongest signal — best zone for new longs. Classic rotation eventually moves toward Weakening as momentum peaks.",

  Weakening:
    "Weakening quadrant: RS-Ratio > 100 but RS-Momentum < 100. " +
    "Still outperforming the benchmark overall, but the rate of outperformance is slowing. " +
    "Caution: likely rotating toward Lagging. Suitable for holding with tighter risk management; not ideal for new entries.",

  Lagging:
    "Lagging quadrant: RS-Ratio < 100 AND RS-Momentum < 100. " +
    "Underperforming the benchmark and losing more ground. Weakest quadrant. " +
    "Avoid. May eventually rotate to Improving once RS-Momentum bottoms and turns up.",

  Improving:
    "Improving quadrant: RS-Ratio < 100 but RS-Momentum > 100. " +
    "Still underperforming overall, but the rate of change is turning positive — relative strength is recovering. " +
    "Early-stage signal: not yet a buy, but worth monitoring. Confirmation comes when RS-Ratio crosses above 100 (transition to Leading).",
};
