from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_next_shell_package_declares_next_react_and_scripts():
    package = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((WEB / "package-lock.json").read_text(encoding="utf-8"))

    assert package["private"] is True
    assert package["scripts"]["dev"] == "next dev --hostname 127.0.0.1 --port 3000"
    assert package["scripts"]["build"] == "next build"
    assert package["dependencies"]["next"].startswith("15.")
    assert package["dependencies"]["react"].startswith("19.")
    assert package["dependencies"]["react-dom"].startswith("19.")
    assert package["overrides"]["postcss"] == "8.5.10"
    assert lock["packages"][""]["dependencies"]["next"] == package["dependencies"]["next"]
    assert lock["packages"]["node_modules/postcss"]["version"] == "8.5.10"


def test_next_shell_fetches_real_api_health_and_data_health_paths():
    api_source = (WEB / "lib" / "api.ts").read_text(encoding="utf-8")
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")

    assert 'process.env.NEXT_PUBLIC_API_BASE_URL' in api_source
    assert 'process.env.API_BASE_URL' in api_source
    assert 'fetchDashboardApi<DashboardHealthPayload>("/api/v1/health")' in api_source
    assert 'fetchDashboardApi<DashboardHealthPayload>("/api/v1/data-health")' in api_source
    assert 'fetchDashboardApi<DashboardSnapshotPayload>(`/api/v1/dashboard-snapshot${query}`)' in api_source
    assert 'cache: "no-store"' in api_source
    assert "fetchDashboardSnapshot()" in page_source
    assert "await Promise.all([" in page_source
    assert "fetch(" not in page_source
    assert 'fetchDashboardSnapshot(ticker?: string)' in api_source
    assert 'fetch("' not in client_source


def test_next_shell_renders_health_tables_and_provider_rail_without_fixture_market_data():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    combined = page_source + "\n" + client_source

    for marker in (
        "Persisted Data Health",
        "Provider Data Health",
        "Provider Flow",
        "A | Overview",
        "B | Deep Dive",
        "C | Rotation",
        "API connection pending",
        "provider_flow_readiness",
        "provider_",
    ):
        assert marker in combined
    for forbidden in ("handoff", "mockup", "sample market", "XLK", "Technology sector"):
        assert forbidden not in combined


def test_next_shell_snapshot_sections_are_api_driven_not_hardcoded():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")

    assert "DashboardScreensClient" in page_source
    assert "snapshot.screens.overview?.leaders" in client_source
    assert "snapshot.screens.rotation?.sectors" in client_source
    assert "focus?.pillar_scores" in client_source
    assert "decision.rationale" in client_source


def test_next_shell_has_native_react_interactions_for_abc_screens():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    assert client_source.startswith('"use client";')
    assert 'type ScreenId = "overview" | "deepdive" | "rotation"' in client_source
    assert 'const SCREENS:' in client_source
    assert 'const QUADRANTS = ["Leading", "Weakening", "Lagging", "Improving", "Unknown"]' in client_source
    assert "useState<ScreenId>" in client_source
    assert "useState<SortKey>" in client_source
    assert "setSelectedTicker" in client_source
    assert "setSelectedQuadrant" in client_source
    assert "sortRows(leaders" in client_source
    assert 'aria-label="Dashboard display selector"' in client_source
    assert 'aria-label="Selected quadrant instrument list"' in client_source
    assert ".screen-tabs" in css_source
    assert ".interactive-card" in css_source
    assert ".rotation-detail tbody tr" in css_source


def test_next_shell_chart_primitives_are_snapshot_driven():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for component in ("PillarHeatmap", "WaterfallChart", "RrgChart", "MomentumBars", "FlowRiver"):
        assert component in chart_source
        assert component in client_source
    assert "pillarContributions(row: SnapshotRow)" in chart_source
    assert "row.s_score / rawSum" in chart_source
    assert "x(100)" in chart_source
    assert "y(100)" in chart_source
    assert ".sort((a, b) => (b.momentum_pct ?? 0) - (a.momentum_pct ?? 0))" in chart_source
    assert "Data-derived map from current weakest flow/score rows into strongest flow/score rows." in chart_source
    assert ".pillar-stack" in css_source
    assert ".waterfall-chart" in css_source
    assert ".rrg-chart" in css_source
    assert ".flow-river" in css_source


def test_next_shell_chart_primitives_do_not_embed_handoff_fixture_tickers():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")

    for forbidden in ("XLK", "XLY", "XLF", "XLU", "XLP", "KRE", "Semis lost leadership", "$3.4B"):
        assert forbidden not in chart_source
    assert "SnapshotRow" in chart_source
    assert ".filter((row)" in chart_source


def test_next_shell_gitignore_excludes_node_and_next_artifacts():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "node_modules/" in gitignore
    assert "web/.next/" in gitignore
    assert "web/node_modules/" in gitignore
