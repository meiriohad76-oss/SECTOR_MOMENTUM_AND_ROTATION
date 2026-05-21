from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_performance_audit_to_structured_logging():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        "from src.performance_audit import "
        "DashboardPerformanceAudit, classify_rerun, session_snapshot"
    ) in app_source
    assert "PERF_AUDIT = DashboardPerformanceAudit()" in app_source
    assert "_PERF_START_SNAPSHOT = session_snapshot(st.session_state)" in app_source
    assert "classify_rerun(st.session_state.get(\"performance_last_snapshot\"), _PERF_START_SNAPSHOT)" in app_source
    assert 'with PERF_AUDIT.section("load_data"):' in app_source
    assert 'with PERF_AUDIT.section("compute_signals"):' in app_source
    assert 'log_event(APP_LOGGER, "dashboard_performance_audit"' in app_source
    assert "rerun_kind=_PERF_RERUN.kind" in app_source
    assert "changed_keys=_PERF_RERUN.changed_keys" in app_source
    assert "sections_ms=PERF_AUDIT.durations_ms" in app_source
    assert "_PERF_FINAL_SNAPSHOT = session_snapshot(st.session_state)" in app_source
    assert "st.session_state.performance_last_snapshot = _PERF_FINAL_SNAPSHOT" in app_source


def test_app_stores_final_snapshot_after_render_time_mutations():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert app_source.index('_render_timed("render_footer", render_footer)') < app_source.index(
        "_PERF_FINAL_SNAPSHOT = session_snapshot(st.session_state)"
    )
    assert app_source.index("_PERF_FINAL_SNAPSHOT = session_snapshot(st.session_state)") < app_source.index(
        'log_event(APP_LOGGER, "dashboard_performance_audit"'
    )
    assert app_source.index('log_event(APP_LOGGER, "dashboard_performance_audit"') < app_source.index(
        "st.session_state.performance_last_snapshot = _PERF_FINAL_SNAPSHOT"
    )


def test_app_times_major_render_sections():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "def _render_timed(section_name: str, render_fn):" in app_source
    assert '_render_timed("render_header", render_header)' in app_source
    assert '_render_timed("render_header_controls", render_header_controls)' in app_source
    assert '_render_timed("render_bluf", render_bluf)' in app_source
    assert '_render_timed("render_drill", render_drill)' in app_source
    assert '_render_timed("render_footer", render_footer)' in app_source
