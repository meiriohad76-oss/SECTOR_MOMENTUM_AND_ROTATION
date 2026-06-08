from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_loading_state_replaces_streamlit_spinners():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_loading_state(" in app_source
    assert "loading_placeholder = st.empty()" in app_source
    assert "loading_placeholder.empty()" in app_source
    assert 'aria-busy="true"' in app_source
    assert 'role="status" aria-label="Data refresh progress"' in app_source
    assert "Refresh request accepted" in app_source
    assert "Downloading and extracting market OHLCV" in app_source
    assert "Market OHLCV loaded" in app_source
    assert "Loading FRED macro/regime data" in app_source
    assert "Computing indicators and scoring" in app_source
    assert "Persisting state transitions" in app_source
    assert "Refresh complete" in app_source
    assert "_provider_result_summary(ohlcv_result)" in app_source
    assert "--skeleton-index:{slot}" in app_source
    assert "st.spinner(" not in app_source


def test_empty_picks_render_defensive_basket():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "defensive_basket_rows(scored)" in app_source
    assert "No picks meet the gates" in app_source
    assert "TLT / GLD / BIL" in app_source
    assert '_render_drill_selector("defensive_drill"' in app_source


def test_empty_and_loading_css_exists():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".empty-state" in css
    assert ".defensive-card" in css
    assert ".loading-state" in css
    assert ".refresh-progress" in css
    assert ".refresh-progress-track" in css
    assert ".refresh-progress-row" in css
    assert "transition: width 180ms ease;" in css
    assert ".skeleton-card" in css
    assert ".skeleton-line" in css
    assert ".skeleton-card::after" in css
    assert "@keyframes loading-shimmer" in css
    assert "animation: loading-shimmer" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
