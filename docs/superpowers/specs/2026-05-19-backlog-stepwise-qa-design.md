# Backlog Stepwise QA Design

## Goal

Implement the backlog incrementally, with one ticket completed, tested, reviewed, and committed before the next ticket starts.

## First Ticket Order

1. `B-142` adds a pytest safety net around pure modules.
2. `B-010` wires ETF primary-flow data after the safety net exists.

This order keeps provider work grounded in deterministic tests. It also avoids importing `app.py` in early tests because the Streamlit app performs data loading and state-machine writes at module import time.

## Architecture

The first ticket introduces a test harness without changing dashboard behavior. Tests target pure modules under `src/`, use deterministic OHLCV fixtures, and patch filesystem or network boundaries when needed.

The second ticket adds a provider seam for ETF primary flow in `src/flow.py`. The implementation will compute a five-day primary-flow percentage from provider records and will return the current neutral stub value when provider data is unavailable, credentials are missing, or stub mode remains enabled.

## Ticket 1: Pytest Safety Net

Files to create:

- `tests/conftest.py`
- `tests/test_data.py`
- `tests/test_indicators.py`
- `tests/test_flow.py`
- `tests/test_scoring.py`

Files to modify:

- `requirements.txt`
- Optionally `docs/BACKLOG.md` after verification, to mark `B-142` progress.

Test coverage:

- Daily-to-weekly and daily-to-monthly resampling.
- Adjusted-close fallback behavior.
- yfinance download flattening with a mocked downloader.
- Indicator short-history guard behavior and full-indicator output shape.
- Flow metrics and flow-composite stability.
- State-machine gate ordering and transition persistence with `STATE_FILE` patched to a temporary path.

## Ticket 2: ETF Primary-Flow Provider

Files likely to modify:

- `src/flow.py`
- `requirements.txt` only if a new dependency is required.
- `docs/BACKLOG.md` after verification.
- Additional tests in `tests/test_flow.py`.

Provider behavior:

- Keep `STUB_MODE = True` as the production default unless the user explicitly asks to enable live provider mode.
- Add a small, testable provider boundary that accepts fetched records and computes five-day flow as a percent of assets.
- Read credentials from environment variables or Streamlit secrets only at the boundary, never in pure calculation helpers.
- Fail closed to neutral flow rather than crashing the dashboard when provider data is incomplete.

## QA Gates Per Ticket

Each ticket must pass these gates before the next ticket starts:

1. Targeted pytest command for the changed module.
2. Full pytest suite.
3. Python compile check for `app.py` and `src`.
4. Git diff review.
5. Subagent review for spec compliance and code quality.
6. Commit with a ticket-specific message.

## Out of Scope

- Cloudflare Access verification, because it requires live account access.
- Backtest harness work, because it depends on a larger design and likely new dependencies.
- Full `app.py` refactor, except for changes directly required by the chosen ticket.
- Turning off `STUB_MODE` by default.
