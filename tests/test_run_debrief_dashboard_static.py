from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_surfaces_run_debrief_without_fetching_data_inside_section():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def render_debrief_lab():")
    end = app_source.index("def render_footer():")
    debrief_source = app_source[start:end]

    assert "from src.run_debrief import debrief_journal, summarize_debriefs, threshold_review_candidates" in app_source
    assert "def render_debrief_lab():" in app_source
    assert "DEFAULT_JOURNAL_PATH" in debrief_source
    assert "debrief_journal(DEFAULT_JOURNAL_PATH, ohlcv" in debrief_source
    assert "summarize_debriefs(records)" in debrief_source
    assert "threshold_review_candidates(records" in debrief_source
    assert "fetch_ohlcv(" not in debrief_source
    assert "st.warning(" in debrief_source


def test_debrief_lab_renders_after_backtest_before_full_table():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_backtest_lab()\nrender_debrief_lab()\nrender_full_table()" in app_source
