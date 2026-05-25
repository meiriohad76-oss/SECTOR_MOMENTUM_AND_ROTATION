# B-026 Empty And Loading States Design

## Goal

Replace the bare no-picks row and Streamlit spinner text with calm dashboard-native states: a defensive basket when no picks pass the gates, and inline skeleton cards while data is fetched and scored.

## Current Context

`render_picks()` currently shows one alert-style row when `scored[scored["selected"]]` is empty. Data loading uses `st.spinner()` around market-data fetch and indicator computation, even though `PRODUCT_DESIGN.md` calls for inline skeleton bars and no full-page spinner.

## Approach

Add a small pure helper module for UI state data:

- `DEFENSIVE_BASKET = ("TLT", "GLD", "BIL")`
- defensive basket row building from the existing scored snapshot
- skeleton slot generation for deterministic loading markup

Keep actual Streamlit rendering in `app.py`, and style the new states in `static/style.css`.

## Empty State Behavior

When no selected picks meet the methodology gates:

- Keep the `Picks` section in place with `0 active`.
- Replace the one-line alert row with a focused empty-state panel.
- Explain that no momentum picks currently pass all gates.
- Show a defensive basket of `TLT`, `GLD`, and `BIL`.
- Use scored data when available for each defensive ticker: current state, `S_score`, and `F_score`.
- Mark missing defensive data as `DATA PENDING` instead of failing rendering.
- Preserve drill-down buttons for defensive tickers that exist in the scored snapshot.

## Loading State Behavior

During first-page market-data load and indicator computation:

- Render a temporary inline skeleton section through a Streamlit placeholder.
- Use skeleton card blocks where picks/status cards will appear.
- Do not use `st.spinner()`.
- Clear the placeholder before rendering the live dashboard.

The skeleton is intentionally static and subtle. It is a progress affordance, not an animation-heavy loading screen.

## Boundaries

This ticket does not add async fetching, custom frontend components, retry controls, cached stale-data banners, or provider error recovery. Those belong to future reliability/performance tickets.

## Testing

Tests cover:

- defensive basket ordering and labels
- missing defensive ticker fallback
- skeleton slot validation
- static app wiring that removes `st.spinner()` and uses the loading placeholder
- CSS selectors for empty and loading states

