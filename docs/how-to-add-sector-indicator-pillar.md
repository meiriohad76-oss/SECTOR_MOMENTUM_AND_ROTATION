# How To Add A Sector, Indicator, Or Pillar

This guide is the safe path for extending the dashboard methodology without breaking the signal contract. Treat `docs/sector-rotation-methodology.md` as the research source of truth, `src/` as the executable implementation, and tests as the guardrail before any dashboard or Pi deploy.

The rule of thumb is simple: change the smallest surface that owns the concept, add a failing test first, then update every operator-facing document that describes the live methodology.

## Add A Sector Or Universe Class

Use this path when adding a new ETF, stock list, factor basket, or a new ranked class.

1. Start in `src/universe.py`.
   - Add the explicit ticker list near the related universe constant.
   - Add the class to `UNIVERSE_BY_CLASS`.
   - Include the tickers in `SCORED_TICKERS` when they should be scored by the methodology. The current risk-off `DEFENSIVES` list is scored and classified as `Defensive`, but it is intentionally outside `UNIVERSE_BY_CLASS` and `TOP_N`.
   - Keep pure data-only symbols in `ALL_TICKERS` through `BENCH` or an explicit data-loader list instead of adding them to `SCORED_TICKERS`.
   - Add or update the class target in `TOP_N`.

2. Write or update `tests/test_universe.py`.
   - Assert the exact ticker tuple.
   - Assert `class_of(ticker)` returns the new class.
   - Assert the class has a positive `TOP_N` target.
   - Assert `ALL_TICKERS` has no duplicates.

3. Reconcile the written methodology.
   - Update `docs/sector-rotation-methodology.md` section 3 with the class and ticker list.
   - Update the section 5 top-N table when the ranked target changes.
   - Update `docs/PRODUCT_DESIGN.md` and `README.md` when visible universe counts or class labels change.
   - Update `docs/BACKLOG.md` with the implemented behavior and residual risk.

4. Keep the dashboard read-only.
   - Do not add a provider fetch path just because a ticker is new.
   - do not write state.json from tests or backtests.
   - Let the existing dashboard data loader fetch the expanded `ALL_TICKERS` payload.

Focused verification:

```powershell
python -m pytest tests/test_universe.py -q
```

## Add An Indicator

Use this path when adding a new calculation that feeds a score, tile, warning, chart, or research artifact.

1. Pick the owner module.
   - Use `src/indicators.py` for OHLCV-derived momentum, trend, stage, RRG, breadth, and other price-volume calculations.
   - Use `src/flow.py` for Pillar 7 flow signals, provider-backed institutional data, and neutral fail-closed stubs.
   - Use `src/macro.py` and `src/fred_data.py` for macro regime inputs.
   - Use `src/visuals.py` only for chart-ready transformations or Plotly figures.

2. Write the failing test first.
   - Use short synthetic frames so edge cases are obvious.
   - Cover the normal calculation and the short-history path.
   - short-history inputs return neutral or missing values instead of crashing.
   - Keep provider tests hermetic by patching HTTP/session boundaries.

3. Implement the helper as a pure calculation when possible.
   - do not fetch provider data from scoring helpers.
   - keep provider-backed signals opt-in and fail-closed until secrets and source URLs are configured.
   - Keep live provider settings in environment variables or Streamlit secrets, never in committed docs or tests.
   - Return explicit neutral values for unavailable optional feeds so the dashboard remains usable.

4. Wire the indicator only after the pure tests pass.
   - Update `src/scoring.py` if the indicator changes a composite input or hard veto.
   - Update `app.py` only for visible labels, tooltips, tiles, tables, or charts.
   - Update `src/component_docs.py` when the visible component inputs or QA coverage change.
   - Update the methodology docs with the formula, signal meaning, and known failure modes.

Focused verification:

```powershell
python -m pytest tests/test_indicators.py tests/test_flow.py tests/test_scoring.py -q
```

## Add Or Change A Pillar

Use this path when a methodology pillar changes weight, formula, veto behavior, state-machine logic, or research interpretation.

1. Update the research contract first.
   - Edit `docs/sector-rotation-methodology.md` with the formula, weight, horizon, evidence, and caveat.
   - Keep the language clear that this is educational research software, not investment advice.
   - If the pillar changes visible UX expectations, update `docs/PRODUCT_DESIGN.md`.

2. Add tests around the expected behavior.
   - `tests/test_scoring.py` should cover composite weights, hard vetoes, class ranking, and state decisions.
   - `tests/test_indicators.py`, `tests/test_flow.py`, or `tests/test_macro.py` should cover the raw signal.
   - Backtest changes belong in `tests/test_backtest.py` and must avoid lookahead.

3. Implement in the smallest executable layer.
   - Use `src/scoring.py` for composite scoring and state assignment.
   - Use `src/indicators.py`, `src/flow.py`, or `src/macro.py` for raw pillar inputs.
   - Use `app.py` for labels, tooltips, and matrix columns after the scoring contract is green.
   - Update `src/component_docs.py` so the component inventory still lists the correct inputs and QA.

4. Protect historical and live safety boundaries.
   - Backtests must not call `apply_state_machine()` or write `state.json`.
   - Historical methodology snapshots must use as-of data only.
   - Provider-backed signals stay neutral in historical paths unless an as-of dataset exists.
   - Live state changes stay in the dashboard state-machine path, not in tutorials, scripts, or tests.

Focused verification:

```powershell
python -m pytest tests/test_indicators.py tests/test_flow.py tests/test_scoring.py tests/test_backtest.py -q
```

## Required Final Verification

Before committing any sector, indicator, or pillar change, run the same local gate used for backlog tickets:

```powershell
python -m pytest tests/test_universe.py -q
python -m pytest tests/test_indicators.py tests/test_flow.py tests/test_scoring.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

For Pi deployment, pull the pushed branch on `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION`, run the focused test pack, run full pytest, and verify the Streamlit service returns HTTP 200 on `http://127.0.0.1:8501/?ticker=XLK`.
