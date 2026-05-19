# B-130 Portfolio / Single-Stock Analyzer Design

## Goal

Let a user run the existing sector-rotation methodology against either one ticker or a personal portfolio upload, without changing the live dashboard state or saving uploaded holdings by default.

## Context

The app already computes a current `scored` DataFrame from `src.indicators`, `src.flow`, `src.macro`, and `src.scoring`. The per-ticker drill-down and full matrix use that DataFrame as the source of truth. B-130 should reuse that scored snapshot instead of inventing a second scoring path.

The first implementation slice should be pure Python and offline-testable. UI and live data work can follow after the input contract is stable.

## Approaches Considered

### Approach A: UI-first upload widget

Add Streamlit controls directly in `app.py`, parse uploaded files inside the render function, and display a quick table.

Trade-off: fastest visible demo, but it mixes parsing, validation, analysis, and UI. It is harder to test and easier to drift away from the methodology modules.

### Approach B: Pure core first, UI second

Create `src/portfolio.py` with typed holdings parsing and scored-DataFrame analysis helpers. Cover CSV, Excel, single ticker, malformed files, unknown tickers, and portfolio-weight behavior with pytest. Add the Streamlit section after the core passes.

Trade-off: one extra module before UI appears, but the behavior is deterministic, reusable, and easy to QA. This is the recommended path.

### Approach C: Broker import first

Start with broker exports or broker APIs and normalize real account files.

Trade-off: useful later, but too much provider-specific surface before the core analyzer exists.

## Recommended Design

Use Approach B.

`src/portfolio.py` owns input normalization and read-only portfolio analysis:

- `HoldingInput` stores normalized ticker, optional shares, cost basis, market value, weight, sector, account, and notes.
- `parse_single_ticker()` turns a user-entered symbol into one holding with weight `1.0`.
- `parse_holdings_csv()` accepts CSV text or bytes and returns normalized holdings plus validation errors.
- `parse_holdings_excel()` accepts Excel bytes and returns normalized holdings plus validation errors.
- `analyze_holdings()` joins normalized holdings to the current `scored` DataFrame and returns per-holding rows, missing tickers, and summary metrics.

The first ticket implements only parsing and validation. It does not fetch data, import Streamlit, write `state.json`, or add UI.

## Data Contract

Portfolio uploads need at least one ticker column. Accepted ticker headers are `ticker`, `symbol`, `holding`, or `asset`. Optional headers are `shares`, `quantity`, `qty`, `cost_basis`, `cost`, `market_value`, `value`, `weight`, `sector`, `account`, and `notes`.

Ticker normalization strips whitespace, uppercases, and preserves dots or dashes used by symbols such as `BRK.B` and `BRK-B`. Blank ticker rows are rejected with row-level validation errors.

Weights are optional. If upload weights are present, percent forms such as `25%` become `0.25`; numeric values above `1.0` are treated as percents, so `25` also becomes `0.25`. If no weights are provided, the analyzer can later infer weights from market value or equal-weight the holdings.

## Error Handling

Parsing functions return a result object with `holdings` and `errors`; they do not throw for normal user mistakes such as missing ticker columns, blank rows, bad numeric cells, or empty files. Unexpected programmer errors should still surface normally in tests.

## Test Strategy

Every implementation ticket starts with a failing test. The first ticket verifies:

- Single ticker normalization.
- CSV parsing with common column aliases.
- Percent and numeric weight normalization.
- Blank ticker row errors.
- Missing ticker-column errors.
- Excel parsing once the dependency is declared.

Later tickets verify:

- Unknown tickers reported without crashing.
- Analyzer uses the existing scored DataFrame columns and does not call `apply_state_machine()`.
- Portfolio summary groups state and sector exposure correctly.
- Streamlit UI smoke path can run with a fixture file.

## Out Of Scope For First Ticket

- Broker API connections.
- Persisted portfolios.
- New scoring methodology.
- Historical backtests of personal trades.
- Dashboard visual polish beyond the later B-130 UI section.
