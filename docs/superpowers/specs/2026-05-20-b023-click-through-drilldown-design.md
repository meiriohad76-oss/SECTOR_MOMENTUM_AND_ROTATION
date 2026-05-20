# B-023 Click-Through Drill-Down Design

## Goal

Make dashboard navigation from alerts, picks, and RRG context land on the per-ticker drill-down with the chosen ticker selected, while keeping the implementation deterministic and testable in Streamlit.

## Current Context

The drill-down already reads `st.session_state.drill_ticker`. Alerts and pick cards are rendered as raw HTML through `st.markdown`, which cannot safely mutate Streamlit session state on click. Plotly click callbacks are also not available in this app without adding another component dependency.

## Approach

Build a small navigation helper module that owns ticker normalization, selected-ticker validation, and query-param state. Wire the app to read `?ticker=XLK` at startup and to update that query param whenever a user selects a drill target. Render native Streamlit buttons near the existing alert, pick, and RRG surfaces so each click can call the helper and rerun the page.

## User Experience

- Alert rows still show the existing visual row. A compact native `DRILL` button appears for each recent transition.
- Pick cards keep the existing card layout. A matching grid of `DRILL <ticker>` native buttons appears below the cards.
- RRG quadrant side cards keep listing tickers. Each ticker also gets a native `DRILL` button grouped under its quadrant.
- External alert links can use `?ticker=XLK` to open the dashboard with `XLK` pre-selected.

## Boundaries

This slice does not add a custom JavaScript Streamlit component, Plotly click event capture, or full-card HTML click handling. Those remain future polish once the basic navigation contract is stable.

## Data Flow

1. App starts and initializes `drill_ticker`.
2. Query param `ticker` is read and normalized against the scored ticker universe.
3. If valid, `drill_ticker` is updated.
4. User clicks a native drill button.
5. Helper writes `st.session_state.drill_ticker`, updates `?ticker=...`, and reruns.
6. Drill-down, portfolio single-ticker default, and alert links all use the same selected ticker.

## Testing

Unit tests cover the helper without importing Streamlit:

- normalizes query-param values such as strings and one-item lists
- rejects unknown or malformed tickers
- chooses a sensible default if no valid query ticker exists
- updates a fake session-state mapping and fake query-param adapter when a valid drill ticker is selected

Existing app tests remain deterministic and do not require a browser.

## Deferred Work

- Custom component for whole-card click handling.
- Plotly selected-point/click event integration for RRG dots.
- Smooth scroll-to-drill behavior after a native drill button click.
