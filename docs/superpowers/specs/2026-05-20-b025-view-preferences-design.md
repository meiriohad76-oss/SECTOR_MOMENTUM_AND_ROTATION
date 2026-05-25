# B-025 View Preferences Design

## Goal

Add TweaksPanel-style view preferences to the Streamlit dashboard: BLUF display mode, density, and pick-card sparkline style.

## Current Context

The app currently renders one full BLUF section, one comfortable-density layout, and filled sparklines on every pick card. The sidebar is hidden and previous tickets now use small native Streamlit controls near the header. The existing raw HTML surfaces cannot own state, so preferences should use native Streamlit widgets.

## Approach

Add a compact `VIEW OPTIONS` expander near the top of the page, after the header controls. Store preferences in `st.session_state` with pure helper defaults and validation. Keep the first slice intentionally native:

- `BLUF`: `Verdict`, `Compact`, `Hidden`
- `Density`: `Comfortable`, `Compact`
- `Sparkline`: `Filled`, `Line`, `Off`

## Behavior

- `Verdict` BLUF keeps the current full section with action cards.
- `Compact` BLUF shows a smaller summary strip with counts and one-line context, without action cards.
- `Hidden` BLUF removes the BLUF section for users who want the dashboard to start closer to status/alerts.
- `Compact` density reduces section spacing, card padding, sparkline height, and BLUF padding through a class on the app shell.
- `Filled` sparklines keep the existing area fill.
- `Line` sparklines render only the line and endpoint.
- `Off` sparklines remove the SVG from pick cards.

## Boundaries

This slice does not add custom floating React controls, saved user profiles, per-user persistence outside Streamlit session state, or new color palettes. Those remain future preference tickets.

## Testing

Unit tests cover:

- preference defaults and invalid-value normalization
- BLUF visibility/mode helper behavior
- density CSS class helper behavior
- sparkline style helper behavior
- `svg_sparkline()` output for filled, line-only, and off modes
- static app/CSS wiring for the new preference panel
