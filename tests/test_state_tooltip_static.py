from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_pick_state_tooltip_uses_row_specific_explanation():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_picks = app_source[
        app_source.index("def render_picks():") : app_source.index("def render_rrg():")
    ]

    assert "state_tip = _state_tip_for_row(tkr, p)" in render_picks
    assert 'data-tip="{_esc(state_tip)}"' in render_picks
    assert 'STATE_TIPS.get(state, "")' not in render_picks


def test_stage_2_tooltip_copy_is_plain_english_and_value_driven():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    helper = app_source[
        app_source.index("def _state_tip_for_row(") : app_source.index("# =============================== system explainer")
    ]

    assert "Why bullish Stage 2 now:" in helper
    assert "Actual readings:" in helper
    assert "What it means:" in helper
    assert "Stage={stage}" in helper
    assert "RRG={rrg}" in helper
    assert "Breadth={breadth}" in helper
    assert "CMF={cmf}" in helper
    assert "Flow={flow}" in helper
    assert "5-session price return={return_5d}" in helper
    assert "sharp 5-session price loss of -4.00% or worse" in helper
    assert "Production state reconciliation changed the displayed state" in helper


def test_tooltip_style_supports_longer_explanations():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    tooltip_style = css[css.index("[data-tip]::after") : css.index("[data-tip]::before")]

    assert "font-size: 0.92rem;" in tooltip_style
    assert "line-height: 1.55;" in tooltip_style
    assert "width: min(420px, calc(100vw - 48px));" in tooltip_style
    assert "max-width: calc(100vw - 48px);" in tooltip_style
    assert "overflow-wrap: break-word;" in tooltip_style
