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
    assert "_REUSED_COMPUTE_SNAPSHOT = should_reuse_dashboard_compute(" in app_source
    assert "_PERF_RERUN," in app_source
    assert "refresh_pending=_REFRESH_REQUEST_PENDING" in app_source
    assert '"created_at": _COMPUTE_SNAPSHOT_CREATED_AT' in app_source
    assert 'with PERF_AUDIT.section("load_data"):' in app_source
    assert 'with PERF_AUDIT.section("compute_signals"):' in app_source
    assert "st.session_state.dashboard_compute_snapshot = {" in app_source
    assert 'log_event(APP_LOGGER, "dashboard_performance_audit"' in app_source
    assert "rerun_kind=_PERF_RERUN.kind" in app_source
    assert "changed_keys=_PERF_RERUN.changed_keys" in app_source
    assert "sections_ms=PERF_AUDIT.durations_ms" in app_source
    assert "reused_compute_snapshot=_REUSED_COMPUTE_SNAPSHOT" in app_source
    assert "data_refresh_lane=st.session_state.get(\"data_refresh_lane\")" in app_source
    assert "data_refresh_requested_at=st.session_state.get(\"data_refresh_requested_at\")" in app_source
    assert "ohlcv_fetched_count=len(getattr(ohlcv_result, \"data\", {}) or {})" in app_source
    assert "fresh_cache_hit_count=len(getattr(ohlcv_result, \"fresh_cache_hits\", ()) or ())" in app_source
    assert "stale_cache_hit_count=len(getattr(ohlcv_result, \"stale_cache_hits\", ()) or ())" in app_source
    assert "missing_ohlcv_count=len(getattr(ohlcv_result, \"missing\", ()) or ())" in app_source
    assert "provider_warning_count=len(getattr(ohlcv_result, \"warnings\", ()) or ())" in app_source
    assert "cache_refresh_forced=bool(getattr(ohlcv_result, \"cache_refresh_forced\", False))" in app_source
    assert "fred_series_count=len(_fred_data)" in app_source
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


def test_debrief_lab_uses_session_cache_and_logs_cache_health():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    debrief_section = app_source[
        app_source.index("def render_debrief_lab():") : app_source.index("# =============================== compose page")
    ]

    assert "debrief_lab_cache" in debrief_section
    assert "_debrief_cache_key(ohlcv, limit=100)" in debrief_section
    assert "with PERF_AUDIT.section(\"debrief_lab_compute\"):" in debrief_section
    assert 'log_event(APP_LOGGER, "debrief_lab_rendered"' in debrief_section
    assert "cache_hit=cache_hit" in debrief_section
    assert "record_count=len(records)" in debrief_section
    assert "outcome_count=len(outcome_rows)" in debrief_section


def test_app_reuses_compute_snapshot_before_expensive_sections():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "def _refresh_request_pending() -> bool:" in app_source
    assert "data_refresh_completed_request_at" in app_source
    assert "_REFRESH_REQUEST_PENDING = _refresh_request_pending()" in app_source
    assert app_source.index("_REUSED_COMPUTE_SNAPSHOT = should_reuse_dashboard_compute(") < app_source.index(
        'with PERF_AUDIT.section("load_data"):'
    )
    assert app_source.index("_REFRESH_REQUEST_PENDING = _refresh_request_pending()") < app_source.index(
        "_REUSED_COMPUTE_SNAPSHOT = should_reuse_dashboard_compute("
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
    assert '"data_refresh_request_at": st.session_state.get("data_refresh_requested_at")' in app_source
    assert '"data_refresh_completed_after_compute": True' in app_source


def test_refresh_completion_is_recorded_only_after_scoring_snapshot_is_written():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    compute_section = app_source[
        app_source.index('with PERF_AUDIT.section("compute_signals"):') : app_source.index("finally:")
    ]

    assert compute_section.index("scored = apply_state_machine(scored)") < compute_section.index(
        "st.session_state.dashboard_compute_snapshot = {"
    )
    assert compute_section.index("st.session_state.dashboard_compute_snapshot = {") < compute_section.index(
        "_mark_data_refresh_completed(ohlcv_result)"
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

    assert app_source.index("transitions = recent_transitions(n=transition_history_limit)") < app_source.index(
        "if not _REUSED_COMPUTE_SNAPSHOT:"
    )


def test_visual_controls_use_precompute_bridge_actions():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    header_section = app_source[
        app_source.index("def render_header_controls():") : app_source.index("def render_bluf():")
    ]

    assert 'st.button("Refresh"' in header_section
    assert '"VIEW",' in header_section
    assert "apply_control_bridge_query_actions(" in app_source
    assert "refresh_market_data(_load_data)" in app_source
    assert "on_click=_refresh_loaded_data" in header_section
    assert "on_click=toggle_theme" in header_section
    assert "st.rerun()" not in header_section
