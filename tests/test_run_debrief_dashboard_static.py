from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_surfaces_run_debrief_without_fetching_data_inside_section():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def render_debrief_lab():")
    end = app_source.index("def render_footer():")
    debrief_source = app_source[start:end]

    assert "summarize_debriefs_by_macro_condition" in app_source
    assert "def render_debrief_lab():" in app_source
    assert "DEFAULT_JOURNAL_PATH" in debrief_source
    assert "debrief_journal(DEFAULT_JOURNAL_PATH, ohlcv" in debrief_source
    assert "debrief_outcome_rows(records)" in debrief_source
    assert "build_debrief_markdown_report(" in debrief_source
    assert "st.download_button(" in debrief_source
    assert "summarize_debriefs(records)" in debrief_source
    assert "summarize_debriefs_by_macro_condition(records" in debrief_source
    assert "threshold_review_candidates(records" in debrief_source
    assert "fetch_ohlcv(" not in debrief_source
    assert "st.warning(" in debrief_source


def test_debrief_lab_renders_after_backtest_before_full_table():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    render_order = [
        '_render_timed("render_backtest_lab", render_backtest_lab)',
        '_render_timed("render_debrief_lab", render_debrief_lab)',
        '_render_timed("render_full_table", render_full_table)',
    ]
    positions = [app_source.index(call) for call in render_order]

    assert positions == sorted(positions)
