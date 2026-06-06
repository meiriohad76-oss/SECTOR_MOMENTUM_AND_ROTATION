from __future__ import annotations

import pytest

from src.momentum_v2 import (
    DISPLAY_LABELS,
    PILLAR_ORDER,
    SCREEN_LABELS,
    build_view_rows,
    contribution_sum,
    css,
    render_display,
)
from src.scoring import compute_composite


def _sample_scored():
    import pandas as pd

    indicators_df = pd.DataFrame(
        {
            "mom_12_1": [0.30, 0.05, -0.10],
            "faber": [1, 1, 0],
            "stage": [2, 2, 4],
            "mansfield_rs": [12.0, -2.0, -8.0],
            "antonacci": [1, 1, 0],
            "rs_ratio": [110.0, 95.0, 88.0],
            "rs_momentum": [108.0, 96.0, 91.0],
            "above_30wma": [True, True, False],
            "ma_slope_pos": [True, True, False],
            "rrg_quadrant": ["Leading", "Weakening", "Lagging"],
            "breadth_50d": [0.70, 0.45, 0.30],
            "obv_divergence": [False, True, True],
            "dist_days_25": [0, 4, 6],
        },
        index=["XLK", "XLF", "XLE"],
    )
    flow_df = pd.DataFrame(
        {
            "cmf21": [0.20, -0.02, -0.18],
            "etf_flow_5d_pct": [0.5, -0.4, -2.0],
            "block_up_ratio": [1.4, 0.9, 0.5],
        },
        index=indicators_df.index,
    )
    flow_z = pd.Series([2.0, -0.3, -2.0], index=indicators_df.index)
    return compute_composite(indicators_df, flow_df, flow_z, phase="MID")


def test_build_view_rows_exposes_all_seven_pillars_and_identity():
    rows = build_view_rows(_sample_scored(), phase="MID")
    xlk = next(row for row in rows if row.ticker == "XLK")

    assert tuple(xlk.pillars.keys()) == PILLAR_ORDER
    assert xlk.identity == "Technology sector"
    assert xlk.display_label == "XLK | Technology sector"
    assert xlk.reasons


def test_pillar_contributions_reconstruct_s_score_before_veto():
    rows = build_view_rows(_sample_scored(), phase="MID")

    for row in rows:
        assert contribution_sum(row) == pytest.approx(row.s_score)


def test_render_display_modes_emit_distinct_terminal_editorial_and_pillar_stack_markup():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html_a = render_display("A", rows, "2026-06-06 16:00 ET")
    html_b = render_display("B", rows, "2026-06-06 16:00 ET")
    html_c = render_display("C", rows, "2026-06-06 16:00 ET")

    assert "mv2-terminal" in html_a
    assert "Momentum terminal board" in html_a
    assert "mv2-editorial" in html_b
    assert "The Sentiment Brief" in html_b
    assert "mv2-pillarstack" in html_c
    assert "The composite, dissected" in html_c
    assert "XLK" in html_c and "Technology sector" in html_c


def test_render_display_supports_all_three_screens_for_each_display():
    rows = build_view_rows(_sample_scored(), phase="MID")

    expected = {
        "overview": "Overview",
        "rotation": "Flow river",
    }
    for display in DISPLAY_LABELS:
        for screen, marker in {
            **expected,
            "deepdive": "article" if display == "B" else "waterfall",
        }.items():
            html = render_display(
                display,
                rows,
                "2026-06-06 16:00 ET",
                screen=screen,
                focus_ticker="XLF",
            )
            assert marker in html
            assert f"momentum-v2-{display.lower()}-{screen}" in html or screen == "overview"


def test_css_contains_readability_and_bar_rules():
    stylesheet = css()

    assert ".mv2-row .t small" in stylesheet
    assert ".mv2-bar:before" in stylesheet
    assert ".mv2-waterfall" in stylesheet
    assert ".mv2-rrg" in stylesheet
    assert "color:var(--mv2-muted)" in stylesheet


def test_display_labels_cover_all_three_handoff_directions():
    assert set(DISPLAY_LABELS) == {"A", "B", "C"}


def test_screen_labels_cover_handoff_overview_deepdive_rotation():
    assert set(SCREEN_LABELS) == {"overview", "deepdive", "rotation"}
