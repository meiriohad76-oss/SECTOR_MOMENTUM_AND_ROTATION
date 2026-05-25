from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_mobile_responsive_app_hooks_wrap_native_button_columns():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert '<div class="drill-buttons-slot"></div>' in app_source
    assert '<div class="rrg-class-controls-slot"></div>' in app_source
    assert app_source.index('<div class="rrg-class-controls-slot"></div>') < app_source.index(
        "cols = st.columns(len(cls_list))"
    )


def test_mobile_responsive_css_covers_phone_layouts():
    css_source = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "@media (max-width: 760px)" in css_source
    assert ".header {" in css_source
    assert ".header .meta {" in css_source
    assert ".section-head {" in css_source
    assert ".alert-row { grid-template-columns: 16px 64px 1fr; }" in css_source
    assert ".full-table { overflow-x: auto; -webkit-overflow-scrolling: touch; }" in css_source
    assert ".full-table table { min-width: 860px; }" in css_source
    assert '.drill-buttons-slot + div[data-testid="stHorizontalBlock"]' in css_source
    assert '.rrg-class-controls-slot + div[data-testid="stHorizontalBlock"]' in css_source
    assert "@media (max-width: 520px)" in css_source
    assert ".drill-metrics { grid-template-columns: 1fr; }" in css_source
    assert ".portfolio-actions .pa-row { grid-template-columns: 1fr; }" in css_source
    assert ".macro-tile .tile-value { white-space: normal; }" in css_source


def test_mobile_table_scroll_rule_wins_after_tooltip_overflow_reset():
    css_source = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    tooltip_reset = "overflow: visible !important;"
    mobile_scroll = ".full-table { overflow-x: auto !important; -webkit-overflow-scrolling: touch; }"

    assert tooltip_reset in css_source
    assert mobile_scroll in css_source
    assert css_source.rindex(mobile_scroll) > css_source.rindex(tooltip_reset)
