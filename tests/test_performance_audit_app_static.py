from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_performance_audit_to_structured_logging():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        "from src.performance_audit import "
        "DashboardPerformanceAudit, classify_rerun, session_snapshot, should_reuse_dashboard_compute"
    ) in app_source
    assert "PERF_AUDIT = DashboardPerformanceAudit()" in app_source
    assert "_PERF_START_SNAPSHOT = session_snapshot(st.session_state)" in app_source
    assert "classify_rerun(st.session_state.get(\"performance_last_snapshot\"), _PERF_START_SNAPSHOT)" in app_source
    assert (
        "_REUSED_COMPUTE_SNAPSHOT = should_reuse_dashboard_compute("
        "_PERF_RERUN, st.session_state.get(\"dashboard_compute_snapshot\")"
    ) in app_source
    assert '"created_at": _COMPUTE_SNAPSHOT_CREATED_AT' in app_source
    assert 'with PERF_AUDIT.section("load_data"):' in app_source
    assert 'with PERF_AUDIT.section("compute_signals"):' in app_source
    assert "st.session_state.dashboard_compute_snapshot = {" in app_source
    assert 'log_event(APP_LOGGER, "dashboard_performance_audit"' in app_source
    assert "rerun_kind=_PERF_RERUN.kind" in app_source
    assert "changed_keys=_PERF_RERUN.changed_keys" in app_source
    assert "sections_ms=PERF_AUDIT.durations_ms" in app_source
    assert "reused_compute_snapshot=_REUSED_COMPUTE_SNAPSHOT" in app_source
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


def test_app_reuses_compute_snapshot_before_expensive_sections():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert app_source.index("_REUSED_COMPUTE_SNAPSHOT = should_reuse_dashboard_compute(") < app_source.index(
        'with PERF_AUDIT.section("load_data"):'
    )
    assert 'if _REUSED_COMPUTE_SNAPSHOT:' in app_source
    assert 'compute_snapshot = st.session_state["dashboard_compute_snapshot"]' in app_source
    assert 'ohlcv_result = compute_snapshot["ohlcv_result"]' in app_source
    assert 'ohlcv = compute_snapshot["ohlcv"]' in app_source
    assert '_fred_data = compute_snapshot["fred_data"]' in app_source
    assert 'regime = compute_snapshot["regime"]' in app_source
    assert 'scored = compute_snapshot["scored"]' in app_source
    assert app_source.index("datetime.now().timestamp()") < app_source.index(
        "st.session_state.dashboard_compute_snapshot = {"
    )


def test_visual_only_reuse_skips_stateful_recording():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    record_index = app_source.index("_record_dashboard_run(scored, bluf, regime")
    reuse_guard_index = app_source.index("if not _REUSED_COMPUTE_SNAPSHOT:")

    assert reuse_guard_index < record_index
    assert "scored = apply_state_machine(scored)" in app_source
    assert app_source.index("scored = apply_state_machine(scored)") < app_source.index(
        "st.session_state.dashboard_compute_snapshot = {"
    )


def test_visual_only_reuse_refreshes_read_only_transition_rows():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert app_source.index("transitions = recent_transitions(n=14)") < app_source.index(
        "if not _REUSED_COMPUTE_SNAPSHOT:"
    )


def test_visual_controls_use_precompute_bridge_actions():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    header_section = app_source[
        app_source.index("def render_header_controls():") : app_source.index("def render_bluf():")
    ]

    assert "st.iframe(" in header_section
    assert "floating_control_bridge_html(" in header_section
    assert "apply_control_bridge_query_actions(" in app_source
    assert "refresh_market_data(_load_data)" in app_source
    assert "on_click=refresh_market_data" not in header_section
    assert "on_click=toggle_theme" not in header_section
    assert "st.rerun()" not in header_section
