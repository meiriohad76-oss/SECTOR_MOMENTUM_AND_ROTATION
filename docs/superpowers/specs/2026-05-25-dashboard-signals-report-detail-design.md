# Dashboard Signals Report Detail Design

## Goal

Upgrade `docs/dashboard_signals_and_xle_stage2_report.pdf` from a high-level overview into a detailed, novice-friendly analyst report with signal formulas, current XLE values, thresholds, calculations, and additional visuals.

## Scope

The report remains a generated PDF artifact created by `scripts/generate_dashboard_signals_report.py`. It should use the same cached dashboard data source, avoid live API calls, and fail closed to the existing fallback path if cache data is unavailable.

## Report Content

The revised PDF must include:

- A deeper explanation of the seven pillars: momentum, trend filters, Weinstein Stage, dual momentum, RRG rotation, business-cycle tilt, and institutional flow.
- For each major signal: what it measures, the formula or input, XLE's current value, the meaningful threshold, the interpretation, and the expected horizon.
- A detailed XLE calculation table showing why `STAGE_2_BULLISH` was assigned.
- Composite score explanation showing the methodology weights, raw values, z-scores where available, and weighted contribution.
- Flow detail covering CMF21, OBV slope, MFI14, RVOL, distribution days, ETF flow, block activity, dark pool proxy, short interest, and 13F proxy when available.
- More visuals: price vs 30-week moving average, score gauges, score contribution bars, flow component bars, and stage lifecycle.
- A plain-English caution section that explains that the output is decision support, not a guaranteed prediction or financial advice.

## Implementation Boundaries

Keep the implementation in:

- `scripts/generate_dashboard_signals_report.py`
- `tests/test_dashboard_signals_report.py`
- `requirements.txt`
- `docs/dashboard_signals_and_xle_stage2_report.pdf`

Do not change core scoring behavior. The report may reproduce calculation details for explanation, but it must not alter `src/scoring.py`, `src/indicators.py`, or `src/flow.py`.

## Testing

Tests must cover:

- The direct script execution import-path guard.
- Stage 2 checklist gates and pass/fail values.
- Signal detail rows containing XLE values and formulas.
- XLE calculation rows containing formula, current value, threshold, and explanation.
- Score contribution rows summing to the fixture S-score.
- Rendering a larger valid PDF.

## Acceptance

The regenerated PDF should be materially larger and more detailed than the first version, with clear numeric XLE evidence and calculation trails that a novice can follow.
