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


def test_classify_interactive_rerun_when_non_visual_state_changes():
    previous = performance_audit.session_snapshot({"theme": "dark", "klass": "US Sectors"})
    current = performance_audit.session_snapshot({"theme": "dark", "klass": "ALL"})

    result = performance_audit.classify_rerun(previous, current)

    assert result.kind == "interactive"
    assert result.changed_keys == ("klass",)


def test_session_snapshot_tracks_interactive_widget_keys_and_ignores_audit_state():
    snapshot = performance_audit.session_snapshot(
        {
            "theme": "dark",
            "comparison_tickers": ["XLK", "XLF"],
            "portfolio_analyzer_mode": "Portfolio",
            "portfolio_single_ticker": "XLK",
            "portfolio_single_source": "XLF",
            "custom_universe_mode": "Paste tickers",
            "custom_universe_text": "XLK XLF",
            "sort_choice": "S_score:desc",
            "performance_last_snapshot": (("theme", "light"),),
        }
    )
    values = dict(snapshot)

    assert values["comparison_tickers"] == "['XLK', 'XLF']"
    assert values["portfolio_analyzer_mode"] == "Portfolio"
    assert values["portfolio_single_ticker"] == "XLK"
    assert values["portfolio_single_source"] == "XLF"
    assert values["custom_universe_mode"] == "Paste tickers"
    assert values["custom_universe_text"] == "XLK XLF"
    assert values["sort_choice"] == "S_score:desc"
    assert "performance_last_snapshot" not in values


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
