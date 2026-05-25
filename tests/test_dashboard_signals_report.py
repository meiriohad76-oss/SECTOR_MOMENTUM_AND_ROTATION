from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scripts import generate_dashboard_signals_report as report


def _snapshot() -> report.XleSnapshot:
    return report.XleSnapshot(
        as_of="2026-05-22",
        state="STAGE_2_BULLISH",
        s_score=1.10,
        f_score=0.43,
        rank_in_class=2,
        selected=True,
        veto=False,
        stage=2,
        price=93.50,
        ma30w=87.25,
        above_30wma=True,
        ma_slope_pos=True,
        mansfield_rs=12.7,
        rrg_quadrant="Leading",
        breadth_50d=0.68,
        cmf21=0.254,
        etf_flow_5d_pct=0.0,
        block_up_ratio=1.0,
        mom_12_1=0.392,
        asset_class="US Sectors",
        faber=1,
        antonacci=1,
        rs_ratio=108.2,
        rs_momentum=103.4,
        obv_slope=0.018,
        mfi14=64.2,
        rvol=1.18,
        dist_days_25=1,
        obv_divergence=False,
        dark_pool_pct=0.40,
        si_delta_15d=0.0,
        thirteen_f_q=0.0,
        top_n_target=4,
        s_score_after_veto=1.10,
        cycle_tilt=1.0,
        ma30w_slope_5w=0.31,
    )


def test_report_uses_approved_pdf_path():
    assert report.REPORT_PATH == Path("docs/dashboard_signals_and_xle_stage2_report.pdf")


def test_report_script_adds_repo_root_to_python_path_before_src_imports():
    source = Path(report.__file__).read_text(encoding="utf-8")

    root_path_insert = source.index("sys.path.insert(0, str(APP_ROOT))")
    first_src_import = source.index("from src.data import close_price, to_weekly")

    assert root_path_insert < first_src_import


def test_stage2_checklist_explains_all_xle_bullish_gates():
    rows = report.build_stage2_checklist(_snapshot())
    labels = [row.label for row in rows]

    assert "Price is above the 30-week moving average" in labels
    assert "30-week moving average is rising" in labels
    assert "Mansfield relative strength is positive" in labels
    assert "RRG quadrant is Leading" in labels
    assert "Breadth is at least 60%" in labels
    assert "CMF21 is above +0.05" in labels
    assert "ETF flow is non-negative" in labels
    assert "Hard flow veto is not active" in labels
    assert all(row.passed for row in rows)


def test_signal_detail_rows_include_formulas_values_and_horizons():
    rows = report.build_signal_detail_rows(_snapshot())
    by_measure = {row.measure: row for row in rows}

    assert "12-1 momentum" in by_measure
    assert by_measure["12-1 momentum"].formula == "close[-21] / close[-252] - 1"
    assert by_measure["12-1 momentum"].xle_value == "+39.2%"
    assert by_measure["12-1 momentum"].horizon == "4-26 weeks"

    assert "RRG quadrant" in by_measure
    assert by_measure["RRG quadrant"].xle_value == "Leading"
    assert by_measure["RRG quadrant"].status == "Bullish"

    assert "CMF21" in by_measure
    assert by_measure["CMF21"].threshold == "> +0.05 confirms accumulation"
    assert by_measure["CMF21"].xle_value == "+0.254"


def test_xle_calculation_rows_show_current_value_threshold_and_explanation():
    rows = report.build_xle_calculation_rows(_snapshot())
    by_label = {row.label: row for row in rows}

    assert by_label["Price vs 30wMA"].formula == "price / 30wMA - 1"
    assert by_label["Price vs 30wMA"].current_value == "+7.2%"
    assert by_label["Price vs 30wMA"].threshold == "> 0%"
    assert by_label["Price vs 30wMA"].passed is True
    assert "above its long-term trend" in by_label["Price vs 30wMA"].explanation

    assert by_label["Class rank"].current_value == "2 of top 4"
    assert by_label["Class rank"].passed is True


def test_score_contribution_rows_sum_to_fixture_s_score():
    rows = report.build_score_contribution_rows(_snapshot())

    assert {row.component for row in rows} >= {
        "12-1 momentum z",
        "Mansfield RS z",
        "RRG RS-Ratio z",
        "RRG momentum z",
        "Binary filters",
        "Cycle tilt",
        "Provider flow z",
    }
    assert round(sum(row.contribution for row in rows), 3) == 1.100


def test_report_readability_uses_larger_fonts_and_sparse_dense_pages():
    assert report.FONTS["tiny"].size >= 21
    assert report.FONTS["small"].size >= 23
    assert report.FONTS["body"].size >= 28
    assert report.SIGNAL_ROWS_PER_PAGE <= 4
    assert report.CALCULATION_ROWS_PER_PAGE <= 5
    assert report.SCORE_ROWS_PER_PAGE <= 4
    assert report.FLOW_ROWS_PER_PAGE <= 5


def test_report_builds_extra_pages_for_readable_dense_sections():
    inputs = report.ReportInputs(
        generated_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        macro_phase="MID",
        macro_note="Benchmark above 10mo SMA; yield-curve data unavailable.",
        xle=_snapshot(),
        price_history=[],
    )

    pages = report.build_pdf_pages(inputs)

    assert len(pages) >= 13


def test_report_readability_keeps_bars_out_of_text_lanes():
    box = (report.MARGIN, 166, report.PAGE_SIZE[0] - report.MARGIN, 900)

    score_bar_x, score_bar_w = report._score_bar_geometry(box)
    flow_label_x, flow_value_x, flow_bar_x, flow_bar_w = report._flow_component_geometry(box)

    assert score_bar_x >= box[0] + 420
    assert score_bar_w >= 500
    assert flow_value_x - flow_label_x >= 240
    assert flow_bar_x - flow_value_x >= 150
    assert flow_bar_w >= 550


def test_report_renderer_writes_a_real_pdf(tmp_path):
    inputs = report.ReportInputs(
        generated_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        macro_phase="MID",
        macro_note="Benchmark above 10mo SMA; yield-curve data unavailable.",
        xle=_snapshot(),
        price_history=[
            report.PricePoint("2025-01-03", 80.0, 78.0),
            report.PricePoint("2025-04-04", 84.0, 79.0),
            report.PricePoint("2025-07-04", 82.0, 80.0),
            report.PricePoint("2025-10-03", 88.0, 82.0),
            report.PricePoint("2026-01-02", 91.0, 84.0),
            report.PricePoint("2026-05-22", 93.5, 87.25),
        ],
    )
    output_path = tmp_path / "dashboard_signals.pdf"

    report.render_pdf(inputs, output_path)

    payload = output_path.read_bytes()
    assert payload.startswith(b"%PDF")
    assert len(payload) > 90_000
