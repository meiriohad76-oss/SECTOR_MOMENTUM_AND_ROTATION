from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_dashboard_scoring_into_run_journal():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "APP_VERSION =" in app_source
    assert "append_dashboard_run" in app_source
    assert "DEFAULT_JOURNAL_PATH" in app_source
    assert "def _record_dashboard_run(" in app_source
    assert "_record_dashboard_run(scored, bluf, regime, transitions, ohlcv)" in app_source
    assert app_source.index("bluf = _build_bluf(scored)") < app_source.index(
        "_record_dashboard_run(scored, bluf, regime, transitions, ohlcv)"
    )
