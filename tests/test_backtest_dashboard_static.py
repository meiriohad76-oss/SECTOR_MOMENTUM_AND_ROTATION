from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_surfaces_backtest_artifacts_without_running_backtest():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'BACKTEST_REPORT_PATH = APP_ROOT / "docs" / "backtest_report.md"' in app_source
    assert 'BACKTEST_EQUITY_PATH = APP_ROOT / "docs" / "backtest_equity.csv"' in app_source
    assert 'BACKTEST_METADATA_PATH = APP_ROOT / "docs" / "backtest_metadata.json"' in app_source
    assert "def render_backtest_lab():" in app_source
    assert "def _load_backtest_metadata():" in app_source
    assert "def _artifact_hash_matches(" in app_source
    assert "python scripts/run_backtest.py" in app_source
    assert "pd.read_csv(BACKTEST_EQUITY_PATH" in app_source
    assert "st.line_chart(" in app_source
    assert "run_backtest.main(" not in app_source


def test_backtest_lab_renders_before_full_table():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_portfolio_analyzer()\nrender_backtest_lab()\nrender_full_table()" in app_source
