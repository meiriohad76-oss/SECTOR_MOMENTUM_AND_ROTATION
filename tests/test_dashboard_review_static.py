from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_review_replaces_repeated_drill_buttons_with_selectors():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    selector_block = app_source[
        app_source.index("def _render_drill_selector(") : app_source.index("def _macro_tile_html(")
    ]

    assert "def _render_drill_selector(" in app_source
    assert "def _go_to_selected_drill(" in app_source
    assert "DRILL_SELECTOR_PLACEHOLDER" in app_source
    assert "if selected == DRILL_SELECTOR_PLACEHOLDER:" in app_source
    assert "[DRILL_SELECTOR_PLACEHOLDER, *drill_tickers]" in app_source
    assert "def _ticker_display_name(" in app_source
    assert "TICKER_DISPLAY_NAMES" in app_source
    assert "DRILL-DOWN FROM PICKS" in app_source
    assert "DRILL-DOWN FROM RECENT TRANSITIONS" in app_source
    assert "DRILL-DOWN FROM RRG" in app_source
    assert "DRILL-DOWN FROM CUSTOM UNIVERSE" in app_source
    assert "_render_drill_buttons(" not in app_source
    assert 'st.button(f"DRILL {ticker}"' not in app_source
    assert "DRILL BUTTONS" not in app_source
    assert "on_change=_go_to_selected_drill" in app_source
    assert "selected = st.selectbox(" not in selector_block
    assert "if selected and selected != st.session_state.drill_ticker:" not in selector_block


def test_drill_selectors_confirm_selection_and_offer_report_jump():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    selector_block = app_source[
        app_source.index("def _render_drill_selector(") : app_source.index("def _macro_tile_html(")
    ]
    go_to_block = app_source[
        app_source.index("def _go_to_drill(") : app_source.index("def _go_to_selected_drill(")
    ]

    assert 'st.session_state["drill_focus_ticker"] = selected_ticker' in go_to_block
    assert 'st.query_params["focus"] = "drill"' in go_to_block
    assert "drill-selection-confirm" in selector_block
    assert 'href="#drill"' in selector_block
    assert "Open complete report" in selector_block


def test_dashboard_review_transitions_have_directional_badges():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "STATE_STRENGTH_RANK" in app_source
    assert "def _transition_sentiment(" in app_source
    assert "transition-badge {sentiment_class}" in app_source
    assert "transition-positive" in app_source
    assert "transition-negative" in app_source


def test_dashboard_review_picks_are_sorted_by_composite_strength():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'sort_values(["S_score", "F_score", "mom_12_1"], ascending=[False, False, False])' in app_source
    assert "SORTED BY S SCORE" in app_source
    assert "pick-rank" in app_source


def test_dashboard_review_css_uses_readable_contrast_and_type():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "--fg-dim: #d7dde7;" in css
    assert "--muted: #b3bdca;" in css
    assert "font-size: 16px;" in css
    assert ".section-head h2 {\n  margin: 0;\n  font-family: var(--font-mono);\n  font-size: 0.92rem;" in css
    assert ".tile-label {\n  font-family: var(--font-prose);\n  font-size: 0.82rem;" in css
    assert ".alert-row {\n  display: grid;\n  grid-template-columns: 24px 86px 120px 1fr auto 30px;" in css
    assert ".pick-metrics {\n  display: grid;\n  grid-template-columns: 1fr 1fr;\n  gap: 8px 14px;\n  font-family: var(--font-mono);\n  font-size: 0.92rem;" in css
    assert 'div[data-testid="stButton"] > button' in css
    assert ".drill-selector-slot" in css
    assert ".quad-card .qtick" in css
    assert "color: var(--ticker-label);" in css
    assert "text-shadow: var(--ticker-label-shadow);" in css
    assert "overflow-wrap: anywhere;" in css
    assert "max-width: min(520px, calc(100vw - 40px));" in css


def test_dashboard_review_source_has_no_mojibake_markers():
    checked_paths = [
        ROOT / "app.py",
        ROOT / "src" / "macro_tiles.py",
        ROOT / "static" / "style.css",
    ]
    bad_markers = ("\u00c2", "\u00c3", "\u00e2", "\ufffd")

    for path in checked_paths:
        source = path.read_text(encoding="utf-8")
        assert not any(marker in source for marker in bad_markers), path


def test_dashboard_review_app_uses_current_streamlit_width_api():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "use_container_width=" not in app_source
    assert 'width="stretch"' in app_source
