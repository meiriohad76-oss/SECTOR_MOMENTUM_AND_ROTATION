from __future__ import annotations

from src import performance_audit


def test_classify_initial_rerun_without_previous_snapshot():
    current = performance_audit.session_snapshot({"theme": "dark"})

    result = performance_audit.classify_rerun(None, current)

    assert result.kind == "initial"
    assert result.changed_keys == ()


def test_classify_visual_only_rerun_reports_changed_keys():
    previous = performance_audit.session_snapshot(
        {
            "theme": "dark",
            "bluf_mode": "Full",
            "view_density": "Comfortable",
            "sparkline_style": "Line",
            "color_palette": "Default",
            "klass": "US Sectors",
        }
    )
    current = performance_audit.session_snapshot(
        {
            "theme": "light",
            "bluf_mode": "Full",
            "view_density": "Comfortable",
            "sparkline_style": "Line",
            "color_palette": "Default",
            "klass": "US Sectors",
        }
    )

    result = performance_audit.classify_rerun(previous, current)

    assert result.kind == "visual_only"
    assert result.changed_keys == ("theme",)


def test_preference_profile_controls_are_visual_only_state():
    previous = performance_audit.session_snapshot(
        {
            "theme": "dark",
            "preference_profile_choice": "Desk",
            "preference_profile_name": "",
            "preference_profile_message": "",
        }
    )
    current = performance_audit.session_snapshot(
        {
            "theme": "dark",
            "preference_profile_choice": "Review",
            "preference_profile_name": "Review",
            "preference_profile_message": "loaded profile Review",
        }
    )

    result = performance_audit.classify_rerun(previous, current)

    assert result.kind == "visual_only"
    assert result.changed_keys == (
        "preference_profile_choice",
        "preference_profile_name",
        "preference_profile_message",
    )


def test_full_table_sort_controls_are_visual_only_state():
    previous = performance_audit.session_snapshot(
        {
            "table_sort": "S_score:desc",
            "table_sort_field": "S_score",
            "table_sort_direction": "desc",
            "table_sort_field_choice": "S_score",
            "table_sort_direction_choice": "desc",
        }
    )
    current = performance_audit.session_snapshot(
        {
            "table_sort": "F_score:asc",
            "table_sort_field": "F_score",
            "table_sort_direction": "asc",
            "table_sort_field_choice": "F_score",
            "table_sort_direction_choice": "asc",
        }
    )

    result = performance_audit.classify_rerun(previous, current)

    assert result.kind == "visual_only"
    assert result.changed_keys == (
        "table_sort",
        "table_sort_field",
        "table_sort_direction",
        "table_sort_field_choice",
        "table_sort_direction_choice",
    )


def test_classify_interactive_rerun_when_non_visual_state_changes():
    previous = performance_audit.session_snapshot({"theme": "dark", "klass": "US Sectors"})
    current = performance_audit.session_snapshot({"theme": "dark", "klass": "ALL"})

    result = performance_audit.classify_rerun(previous, current)

    assert result.kind == "interactive"
    assert result.changed_keys == ("klass",)


def test_should_reuse_dashboard_compute_only_for_visual_only_complete_snapshot():
    classification = performance_audit.RerunClassification("visual_only", ("theme",))
    snapshot = {
        "ohlcv_result": object(),
        "ohlcv": object(),
        "fred_data": object(),
        "regime": object(),
        "scored": object(),
        "created_at": 1_000.0,
    }

    assert performance_audit.should_reuse_dashboard_compute(classification, snapshot, now=1_100.0) is True
    assert performance_audit.should_reuse_dashboard_compute(
        performance_audit.RerunClassification("interactive", ("klass",)),
        snapshot,
        now=1_100.0,
    ) is False
    assert performance_audit.should_reuse_dashboard_compute(classification, None, now=1_100.0) is False
    assert performance_audit.should_reuse_dashboard_compute(
        classification,
        {"ohlcv_result": object(), "ohlcv": object()},
        now=1_100.0,
    ) is False
    without_created_at = dict(snapshot)
    without_created_at.pop("created_at")
    assert performance_audit.should_reuse_dashboard_compute(classification, without_created_at, now=1_100.0) is False


def test_should_reuse_dashboard_compute_rejects_stale_or_missing_snapshot_age():
    classification = performance_audit.RerunClassification("visual_only", ("theme",))
    snapshot = {
        "ohlcv_result": object(),
        "ohlcv": object(),
        "fred_data": object(),
        "regime": object(),
        "scored": object(),
        "created_at": 1_000.0,
    }

    assert performance_audit.should_reuse_dashboard_compute(classification, snapshot, now=4_599.0) is True
    assert performance_audit.should_reuse_dashboard_compute(classification, snapshot, now=4_601.0) is False

    missing_age = dict(snapshot)
    missing_age.pop("created_at")
    assert performance_audit.should_reuse_dashboard_compute(classification, missing_age, now=1_100.0) is False


def test_session_snapshot_tracks_interactive_widget_keys_and_ignores_audit_state():
    snapshot = performance_audit.session_snapshot(
        {
            "theme": "dark",
            "methodology_ticker_input": "NVDA",
            "comparison_tickers": ["XLK", "XLF"],
            "portfolio_analyzer_mode": "Portfolio",
            "portfolio_single_ticker": "XLK",
            "portfolio_single_source": "XLF",
            "custom_universe_mode": "Paste tickers",
            "custom_universe_text": "XLK XLF",
            "saved_portfolio_select": "Retirement",
            "loaded_portfolio_name": "Retirement",
            "save_portfolio_name": "Retirement",
            "saved_watchlist_select": "Core",
            "loaded_watchlist_name": "Core",
            "save_watchlist_name": "Core",
            "table_sort": "S_score:desc",
            "table_sort_field": "S_score",
            "table_sort_direction": "desc",
            "table_sort_field_choice": "S_score",
            "table_sort_direction_choice": "desc",
            "performance_last_snapshot": (("theme", "light"),),
            "ohlcv_prefetch_future": object(),
            "ohlcv_prefetch_status": "running",
        }
    )
    values = dict(snapshot)

    assert values["comparison_tickers"] == "['XLK', 'XLF']"
    assert values["methodology_ticker_input"] == "NVDA"
    assert values["portfolio_analyzer_mode"] == "Portfolio"
    assert values["portfolio_single_ticker"] == "XLK"
    assert values["portfolio_single_source"] == "XLF"
    assert values["custom_universe_mode"] == "Paste tickers"
    assert values["custom_universe_text"] == "XLK XLF"
    assert values["saved_portfolio_select"] == "Retirement"
    assert values["loaded_portfolio_name"] == "Retirement"
    assert values["save_portfolio_name"] == "Retirement"
    assert values["saved_watchlist_select"] == "Core"
    assert values["loaded_watchlist_name"] == "Core"
    assert values["save_watchlist_name"] == "Core"
    assert values["table_sort"] == "S_score:desc"
    assert values["table_sort_field"] == "S_score"
    assert values["table_sort_direction"] == "desc"
    assert values["table_sort_field_choice"] == "S_score"
    assert values["table_sort_direction_choice"] == "desc"
    assert "performance_last_snapshot" not in values
    assert "ohlcv_prefetch_future" not in values
    assert "ohlcv_prefetch_status" not in values


def test_dashboard_performance_audit_records_section_durations():
    ticks = iter([10.0, 10.25, 11.0, 12.5])
    audit = performance_audit.DashboardPerformanceAudit(timer=lambda: next(ticks))

    with audit.section("load_data"):
        pass
    with audit.section("render_header"):
        pass

    assert audit.durations_ms == {"load_data": 250.0, "render_header": 1500.0}


def test_dashboard_performance_audit_accumulates_repeated_section_names():
    ticks = iter([1.0, 1.1, 2.0, 2.2])
    audit = performance_audit.DashboardPerformanceAudit(timer=lambda: next(ticks))

    with audit.section("render_section"):
        pass
    with audit.section("render_section"):
        pass

    assert audit.durations_ms == {"render_section": 300.0}
