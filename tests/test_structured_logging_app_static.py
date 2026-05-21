from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_configures_structured_logging_for_run_journal_events():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.structured_logging import configure_structured_logging, log_event" in app_source
    assert "APP_LOGGER = configure_structured_logging()" in app_source
    assert 'log_event(APP_LOGGER, "dashboard_run_recorded"' in app_source
    assert 'log_event(APP_LOGGER, "dashboard_run_journal_error"' in app_source
    assert "run_id=result.run_id" in app_source
    assert "error=result.error" in app_source
