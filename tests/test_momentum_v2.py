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
    assert "SENTIMENT BOARD" in html_a
    assert "mv2-editorial" in html_b
    assert "The Sentiment Brief" in html_b
    assert "mv2-pillarstack" in html_c
    assert "The composite, dissected" in html_c
    assert "XLK" in html_c and "Technology sector" in html_c


def test_display_a_overview_matches_terminal_handoff_structure():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = render_display("A", rows, "2026-06-06 16:00 ET")

    for marker in (
        "SENTIMENT BOARD",
        "BLUF",
        "Risk regime",
        "Cycle phase",
        "Active warnings",
        "Breadth",
        "7-PILLAR HEATMAP",
        "TRANSITIONS",
        "WATCHLIST | MY POSITIONS",
        "v2 | TERMINAL | READ-ONLY | MEIRI",
    ):
        assert marker in html
    assert "TKR" in html and "NOTE" in html and "STATE" in html
    assert "7 PILLARS" in html and ">S<" in html and ">F<" in html and "MOM" in html
    assert "US SECTORS" in html
    assert "data-ticker=\"XLK\"" in html
    assert "data-drill-ticker=\"XLK\"" in html
    assert "Open XLK drill-down for Technology sector" in html
    assert "Technology sector" in html
    assert "Energy sector" in html


def test_display_a_deepdive_matches_terminal_handoff_structure_for_focus_ticker():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = render_display(
        "A",
        rows,
        "2026-06-06 16:00 ET",
        screen="deepdive",
        focus_ticker="XLF",
    )

    for marker in (
        "BACK TO OVERVIEW",
        "DEEP DIVE",
        "COMPOSITE FORWARD OUTLOOK",
        "STATE GATES",
        "Next state escalation",
        "WEEKLY PRICE vs 30-WEEK SMA",
        "OBV DIVERGENCE",
        "CHAIKIN MONEY FLOW",
        "PEERS | US SECTORS RANK",
        "v2 | TERMINAL | DEEP DIVE | MEIRI",
    ):
        assert marker in html
    assert "XLF is currently" in html
    assert "rank" in html
    assert "data-drill-ticker=\"XLF\"" in html
    assert "Financials sector" in html


def test_display_a_rotation_matches_terminal_handoff_structure():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = render_display("A", rows, "2026-06-06 16:00 ET", screen="rotation")

    for marker in (
        "ROTATION MAP",
        "US SECTORS",
        "US INDUSTRIES",
        "COUNTRIES",
        "FACTORS",
        "RELATIVE ROTATION GRAPH",
        "4-week motion trail",
        "12-1 CROSS-SECTIONAL MOMENTUM",
        "INSTITUTIONAL FLOW DETAIL | PILLAR 7",
        "MACRO | BUSINESS CYCLE",
        "v2 | TERMINAL | ROTATION | MEIRI",
    ):
        assert marker in html
    assert "RS-RATIO" in html
    assert "RS-MOMENTUM" in html
    assert "data-drill-ticker=\"XLK\"" in html
    assert "Technology sector" in html


def test_display_c_overview_deepdive_rotation_inventory_is_present():
    rows = build_view_rows(_sample_scored(), phase="MID")

    overview = render_display("C", rows, "2026-06-06 16:00 ET")
    deepdive = render_display("C", rows, "2026-06-06 16:00 ET", screen="deepdive", focus_ticker="XLK")
    rotation = render_display("C", rows, "2026-06-06 16:00 ET", screen="rotation")

    for marker in (
        "Momentum",
        "Heatmap",
        "Defensives rotating in. Semis lost leadership.",
        "The composite, dissected",
        "State changes",
        "Your positions",
        "Bullish cohort",
    ):
        assert marker in overview
    assert "data-drill-ticker=\"XLK\"" in overview

    for marker in (
        "The composite, built pillar by pillar",
        "The seven pillars",
        "Price + 30wMA",
        "State machine",
        "WATERFALL",
    ):
        assert marker in deepdive
    assert "Technology sector" in deepdive

    for marker in (
        "The rotation map",
        "Relative rotation | US Sectors",
        "The flow river",
        "Macro / business cycle",
        "Flow detail",
        "PILLAR STACK | ROTATION",
    ):
        assert marker in rotation
    assert "Flow river from outflows to inflows" in rotation


def test_display_b_overview_deepdive_rotation_inventory_is_present():
    rows = build_view_rows(_sample_scored(), phase="MID")

    overview = render_display("B", rows, "2026-06-06 16:00 ET")
    deepdive = render_display("B", rows, "2026-06-06 16:00 ET", screen="deepdive", focus_ticker="XLK")
    rotation = render_display("B", rows, "2026-06-06 16:00 ET", screen="rotation")

    for marker in (
        "The Sentiment Brief",
        "LIVE",
        "Semis lost leadership.",
        "Defensives are bidding.",
        "By the numbers",
        "This week's transitions",
        "Your positions",
        "Bullish cohort",
        "On watch",
        "Read before you trade.",
    ):
        assert marker in overview

    for marker in (
        "DEEP-DIVE",
        "price says fine",
        "COMPOSITE S",
        "The seven pillars, explained",
        "Exit trigger table",
        "WEEKLY PRICE vs 30wMA",
    ):
        assert marker in deepdive

    for marker in (
        "THE ROTATION MAP",
        "Where the money is going",
        "FIGURE 1 | RELATIVE ROTATION",
        "Cross-sectional leaderboard",
        "The phase",
        "If the regime flips",
        "THE SENTIMENT BRIEF | THE MAP",
    ):
        assert marker in rotation


def test_render_display_supports_all_three_screens_for_each_display():
    rows = build_view_rows(_sample_scored(), phase="MID")

    for display in DISPLAY_LABELS:
        for screen, marker in {
            "overview": {"A": "Overview", "B": "Overview", "C": "Heatmap"}[display],
            "rotation": {"A": "ROTATION MAP", "B": "THE ROTATION MAP", "C": "Flow river"}[display],
            "deepdive": {"A": "COMPOSITE FORWARD OUTLOOK", "B": "article", "C": "The composite, built pillar by pillar"}[display],
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


def test_deepdive_defaults_to_whole_universe_not_xlk():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = render_display("C", rows, "2026-06-06 16:00 ET", screen="deepdive")

    assert "Universe deep dive" in html
    assert "Not a single-ticker report" in html
    assert "XLK | Technology sector" in html
    assert "XLF | Financials sector" in html
    assert "XLE | Energy sector" in html


def test_deepdive_uses_ticker_report_only_when_focus_is_explicit():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = render_display("B", rows, "2026-06-06 16:00 ET", screen="deepdive", focus_ticker="XLF")

    assert "Universe deep dive" not in html
    assert "XLF: price says fine" in html


def test_css_contains_readability_and_bar_rules():
    stylesheet = css()

    assert ".mv2-row .t small" in stylesheet
    assert ".mv2-bar:before" in stylesheet
    assert ".mv2-a-body" in stylesheet
    assert ".mv2-a-header-row" in stylesheet
    assert ".mv2-a2-lead-grid" in stylesheet
    assert ".mv2-a3-grid" in stylesheet
    assert ".mv2-c-top" in stylesheet
    assert ".mv2-c-flow-river" in stylesheet
    assert ".mv2-waterfall" in stylesheet
    assert ".mv2-rrg" in stylesheet
    assert "color:var(--mv2-muted)" in stylesheet


def test_display_labels_cover_all_three_handoff_directions():
    assert set(DISPLAY_LABELS) == {"A", "B", "C"}


def test_screen_labels_cover_handoff_overview_deepdive_rotation():
    assert set(SCREEN_LABELS) == {"overview", "deepdive", "rotation"}
