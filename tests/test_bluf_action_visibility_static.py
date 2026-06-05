from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_bluf_action_model_keeps_every_action_ticker():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    build_bluf = app_source[
        app_source.index("def _build_bluf(") : app_source.index("def _browser_qa_transitions(")
    ]

    assert ".head(4).iterrows()" not in build_bluf
    assert "for tkr, r in sub_sorted.iterrows():" in build_bluf


def test_bluf_full_mode_exposes_complete_action_lists_with_selectors():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_bluf = app_source[
        app_source.index("def render_bluf():") : app_source.index("def _provider_status_list_html(")
    ]

    assert "action-count" in render_bluf
    assert 'for it in a["tickers"]' in render_bluf
    assert "display_items =" not in render_bluf
    assert "action-more" not in render_bluf
    assert "_render_drill_selector(" in render_bluf
    assert 'f"bluf_{a[\'kind\']}_drill"' in render_bluf
    assert 'f"DRILL-DOWN FROM {a[\'label\']}"' in render_bluf


def test_bluf_action_list_scrolls_instead_of_hiding_extra_tickers():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".action-count" in css
    assert "max-height: 260px;" in css
    assert "overflow-y: auto !important;" in css
    assert "contain: layout paint;" in css


def test_tooltip_overflow_reset_does_not_disable_bluf_action_scroll():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    overflow_reset = css[
        css.index("/* ---------- Tooltip clipping fix ---------- */") : css.index(
            "/* Streamlit container resets"
        )
    ]

    assert ".action-list," not in overflow_reset
    assert ".action-list {" in css
