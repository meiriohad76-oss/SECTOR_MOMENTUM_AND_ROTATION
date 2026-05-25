# B-024 Header Controls Design

## Goal

Move refresh and theme controls from the bottom of the Streamlit page into the visible header area while preserving real Streamlit button behavior.

## Current Context

The app renders the visual header as raw HTML, then renders working Streamlit refresh/theme buttons after the footer. The CSS already defines a compact `.icon-btn` visual pattern, but raw HTML cannot call `st.rerun()` or clear cached data by itself.

## Approach

Use native Streamlit buttons, placed immediately after `render_header()`, and style that Streamlit button container as a fixed top-right control group. The controls remain real Streamlit widgets, so refresh can clear `_load_data`, and theme can mutate `st.session_state.theme`. This avoids introducing `streamlit-elements` or a custom JavaScript component for a two-button control.

## User Experience

- Refresh and theme controls appear at the top-right of the viewport near the header.
- The buttons use compact icon labels and tooltips.
- The previous bottom-of-page controls are removed.
- The header metadata continues to show the current theme in the footer and the current update timestamp in the header.
- The fixed controls stay reachable while scrolling through the long dashboard.

## Boundaries

This slice does not add a custom component, animated fetching state, theme palettes beyond dark/light, or a sidebar preferences panel. Those remain later backlog work.

## Testing

Unit tests cover the pure control-state helper:

- toggling dark to light and light to dark
- defaulting missing/invalid theme state back to dark before toggling
- clearing a cache-like object and reporting that refresh happened

App-level smoke verifies Streamlit still serves HTTP 200 after the controls move.
