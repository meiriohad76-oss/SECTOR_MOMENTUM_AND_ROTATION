from __future__ import annotations

import pytest

from src.momentum_v2 import (
    DISPLAY_A_SORT_DIRECTIONS,
    DISPLAY_A_SORT_FIELDS,
    DISPLAY_LABELS,
    PILLAR_ORDER,
    SCREEN_LABELS,
    _c_flow_river_svg,
    _c_momentum_bars,
    _flow_river_html,
    _momentum_rows,
    _state_pill,
    _terminal_momentum_bars,
    build_view_rows,
    contribution_sum,
    css,
    render_display,
    sort_display_a_rows,
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


def test_build_view_rows_uses_pullback_aware_state_label():
    scored = _sample_scored()
    scored.loc["XLK", "state"] = "STAGE_2_BULLISH"
    scored.loc["XLK", "pullback_risk"] = True
    scored.loc["XLK", "pullback_risk_reason"] = "5-session return -3.70% is at/below -3.50%"
    scored.loc["XLK", "state_display_label"] = "Stage 2, Pullback Risk"

    rows = build_view_rows(scored, phase="MID")
    xlk = next(row for row in rows if row.ticker == "XLK")
    html = render_display("C", rows, "2026-06-06 16:00 ET", screen="deepdive", focus_ticker="XLK")

    assert xlk.state == "STAGE_2_BULLISH"
    assert xlk.state_label == "Stage 2, Pullback Risk"
    assert xlk.pullback_risk is True
    assert "Stage 2, Pullback Risk" in html
    assert "pullback risk is active" in " ".join(xlk.reasons)


def test_momentum_bar_and_flow_helpers_render_empty_universe_messages():
    assert "No momentum rows available" in _momentum_rows([])
    assert "No momentum rows available" in _terminal_momentum_bars([])
    assert "No momentum rows available" in _c_momentum_bars([])
    assert "No flow rows" in _flow_river_html([])


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


def test_warning_state_pill_uses_readable_dark_text_on_yellow_background():
    assert 'style="background:#C68A1E;color:#171006">WARN</span>' in _state_pill("WARNING")


def test_display_a_transition_identity_does_not_wrap_inside_narrow_ticker_column():
    stylesheet = css()
    rows = build_view_rows(_sample_scored(), phase="MID")
    html = render_display("A", rows, "2026-06-06 16:00 ET")

    assert "grid-template-columns:10px minmax(124px, .65fr) minmax(0, 1.35fr) auto" in stylesheet
    assert ".mv2-a-transition .mv2-a-id small" in stylesheet
    assert "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" in stylesheet
    assert '<div class="mv2-a-id"><b>XLK</b><small>Technology sector</small></div>' in html
    assert "| state" not in html


def test_display_a_heatmap_supports_sorting_by_visible_headers():
    rows = build_view_rows(_sample_scored(), phase="MID")

    assert {"ticker", "identity", "state", "pillar_sum", "s_score", "f_score", "momentum_pct", "trend_90d"} == set(
        DISPLAY_A_SORT_FIELDS
    )
    assert DISPLAY_A_SORT_DIRECTIONS == {"desc": "High to low", "asc": "Low to high"}
    assert [row.ticker for row in sort_display_a_rows(rows, "ticker", "asc")] == ["XLE", "XLF", "XLK"]
    assert [row.ticker for row in sort_display_a_rows(rows, "f_score", "desc")] == ["XLK", "XLF", "XLE"]
    assert [row.ticker for row in sort_display_a_rows(rows, "momentum_pct", "asc")] == ["XLE", "XLF", "XLK"]

    html = render_display(
        "A",
        rows,
        "2026-06-06 16:00 ET",
        display_a_sort_field="f_score",
        display_a_sort_direction="asc",
    )

    assert "sorted by F within class | Low to high" in html
    assert 'class="mv2-a-sort active num"' in html
    assert 'data-mv2-sort="f_score"' in html
    assert "?mv2_sort=ticker&mv2_dir=desc" in html


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
    assert "Rotation universe inventory" in html
    assert "small dot = four-week trail start" in html
    assert "CMF | F score | flow pillar | breadth | provider data when configured" in html
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
        "lost flow support",
        "leads sponsorship",
        "The composite, dissected",
        "State queue",
        "Highest-impact rows",
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
    assert "NET OUTFLOWS" in rotation
    assert "NET INFLOWS" in rotation
    assert "Technology sector pressure into" in rotation or "Energy sector pressure into" in rotation
    assert "small dot = four-week trail start" in rotation


def test_display_c_flow_river_is_derived_from_current_rows_not_handoff_fixture():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = _c_flow_river_svg(rows)

    assert "Flow river from outflows to inflows" in html
    assert "XLK | Technology sector" in html
    assert "XLE | Energy sector" in html
    assert "SMH" not in html
    assert "GDX" not in html
    assert "Fixture QA" not in html
    assert "handoff" not in html.lower()


def test_display_b_overview_deepdive_rotation_inventory_is_present():
    rows = build_view_rows(_sample_scored(), phase="MID")

    overview = render_display("B", rows, "2026-06-06 16:00 ET")
    deepdive = render_display("B", rows, "2026-06-06 16:00 ET", screen="deepdive", focus_ticker="XLK")
    rotation = render_display("B", rows, "2026-06-06 16:00 ET", screen="rotation")

    for marker in (
        "The Sentiment Brief",
        "LIVE",
        "lost flow support",
        "leads sponsorship",
        "By the numbers",
        "Current risk stories",
        "Your positions",
        "Bullish cohort",
        "On watch",
        "Read before you trade.",
    ):
        assert marker in overview

    for marker in (
        "DEEP-DIVE",
        "trend confirms",
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
        "Where the flow went",
        "Current support basket",
        "If the regime weakens",
        "THE SENTIMENT BRIEF | THE MAP",
    ):
        assert marker in rotation
    assert "current rotation" in rotation
    assert "The current rotation story." in rotation


def test_rotation_screens_use_current_rows_for_flow_and_editorial_copy():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = "\n".join(
        render_display(display, rows, "2026-06-06 16:00 ET", screen="rotation")
        for display in ("A", "B", "C")
    )

    assert "XLK | Technology sector" in html
    assert "XLF | Financials sector" in html
    assert "XLE | Energy sector" in html
    assert "Strongest F scores" in html
    assert "Weakest F scores" in html
    assert "NET OUTFLOWS" in html and "NET INFLOWS" in html
    assert "provider feeds when configured" in html


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
    assert "XLF: trend confirms" in html


def test_momentum_v2_renderer_does_not_emit_handoff_sample_market_data():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = "\n".join(
        [
            render_display("B", rows, "2026-06-06 16:00 ET"),
            render_display("B", rows, "2026-06-06 16:00 ET", screen="deepdive", focus_ticker="XLK"),
            render_display("B", rows, "2026-06-06 16:00 ET", screen="rotation"),
            render_display("C", rows, "2026-06-06 16:00 ET"),
            render_display("C", rows, "2026-06-06 16:00 ET", screen="rotation"),
        ]
    )

    stale_samples = (
        "Semis lost leadership",
        "Defensives are bidding",
        "No. 247",
        "2s10s curve",
        "Recession prob",
        "+0.18 flat",
        "TLT +0.42",
        "GLD +0.84",
        "price says fine",
        "Flow says go",
        "Tech / Semis",
        "Energy / Oil",
        "LIVE FLOW",
        "CACHE 60min",
        "last 14 days",
        "connected | synced",
        "3 min read",
        "This week's transitions",
    )
    for sample in stale_samples:
        assert sample not in html


def test_momentum_v2_renderer_does_not_emit_prototype_or_fixture_language():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = "\n".join(
        render_display(display, rows, "2026-06-06 16:00 ET", screen=screen, focus_ticker="XLK")
        for display in ("A", "B", "C")
        for screen in ("overview", "deepdive", "rotation")
    )

    for forbidden in ("handoff", "mockup", "fixture", "sample market", "fixed handoff"):
        assert forbidden not in html.lower()


def test_momentum_v2_renderer_exposes_data_source_provenance():
    rows = build_view_rows(_sample_scored(), phase="MID")

    html = render_display(
        "C",
        rows,
        "2026-06-06 16:00 ET",
        data_provenance={
            "market_ohlcv": "configured massive; providers massive:3; paths massive_live:3",
            "fred_macro": "FRED classifier live; 20 series; phase MID",
            "provider_flow": "2 live/configured, 4 neutral-stubbed, 0 warning",
            "computed": "rows from scored dataframe",
        },
    )

    assert "momentum-v2-provenance" in html
    assert "Market OHLCV" in html
    assert "configured massive" in html
    assert "FRED classifier live" in html
    assert "Provider flow" in html
    assert "rows from scored dataframe" in html


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
    assert ".mv2-provenance" in stylesheet
    assert ".mv2-waterfall" in stylesheet
    assert ".mv2-rrg" in stylesheet
    assert "color:var(--mv2-muted)" in stylesheet


def test_display_labels_cover_all_three_handoff_directions():
    assert set(DISPLAY_LABELS) == {"A", "B", "C"}


def test_screen_labels_cover_handoff_overview_deepdive_rotation():
    assert set(SCREEN_LABELS) == {"overview", "deepdive", "rotation"}
