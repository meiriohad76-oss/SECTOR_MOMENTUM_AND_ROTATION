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
    assert 'fetchDashboardApi<BacktestArtifactsPayload>("/api/v1/backtest-artifacts")' in api_source
    assert 'fetchDashboardApi<TickerChartPayload>(`/api/v1/ticker-chart${query}`)' in api_source
    assert 'postDashboardApi<PortfolioAnalysisPayload>("/api/v1/portfolio/analyze", payload)' in api_source
    assert 'cache: "no-store"' in api_source
    assert "fetchDashboardSnapshot()" in page_source
    assert "fetchBacktestArtifacts()" in page_source
    assert "await Promise.all([" in page_source
    assert 'export const dynamic = "force-dynamic";' in page_source
    assert "export const revalidate = 0;" in page_source
    assert "fetch(" not in page_source
    assert 'fetchDashboardSnapshot(ticker?: string)' in api_source
    assert "fetchBacktestArtifacts()" in api_source
    assert "fetchTickerChart(ticker: string, period = \"3y\", benchmark?: string)" in api_source
    assert "analyzePortfolio(payload: PortfolioAnalysisRequest)" in api_source
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
    for forbidden in ("mockup", "sample market", "XLK", "Technology sector"):
        assert forbidden not in combined


def test_next_shell_snapshot_sections_are_api_driven_not_hardcoded():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")

    assert "DashboardScreensClient" in page_source
    assert "snapshot.screens.overview?.leaders" in client_source
    assert "snapshot.screens.overview?.positions" in client_source
    assert "snapshot.screens.rotation?.sectors" in client_source
    assert "focus?.pillar_scores" in client_source
    assert "decision.rationale" in client_source


def test_next_shell_has_api_backed_portfolio_analyzer_without_fixture_data():
    api_source = (WEB / "lib" / "api.ts").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        "PortfolioAnalysisPayload",
        "PortfolioAnalysisRequest",
        "postDashboardApi<T>",
        "/api/v1/portfolio/analyze",
    ):
        assert marker in api_source
    for marker in (
        "PortfolioAnalyzerPanel",
        "Analyze Ticker Or Portfolio",
        "readFileAsBase64",
        "setMode",
        "analyzePortfolio(request)",
        "CSV Holdings",
        "CSV / Excel File",
        "onSelectTicker(row.ticker)",
    ):
        assert marker in client_source
    for marker in (
        ".portfolio-api-panel",
        ".portfolio-mode-tabs",
        ".portfolio-input-grid",
        ".portfolio-table-wrap",
    ):
        assert marker in css_source
    for forbidden in ("sample holding", "demo portfolio", "Technology sector"):
        assert forbidden not in client_source


def test_next_shell_has_collapsed_backtest_artifact_panel_from_api():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    assert "fetchBacktestArtifacts" in page_source
    assert "backtestResult.data" in page_source
    assert "backtestError={backtestResult.error}" in page_source
    assert "backtestArtifacts={backtestArtifacts}" in page_source
    for marker in (
        "BacktestArtifactPanel",
        "BacktestArtifactsPayload",
        '<details className="backtest-artifact-panel">',
        "payload?.equity.rows",
        "payload.artifacts.map",
        "payload?.report.text",
        "This panel reads manual backtest artifacts only.",
    ):
        assert marker in client_source
    for marker in (
        ".backtest-artifact-panel",
        ".backtest-status-grid",
        ".backtest-mini-chart",
        ".backtest-report-preview",
    ):
        assert marker in css_source
    for forbidden in ("sample equity", "demo backtest", "1.23"):
        assert forbidden not in client_source


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


def test_next_shell_has_handoff_presentation_modes_for_visual_parity():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    assert 'presentation === "a"' in page_source
    assert 'presentation === "b"' in page_source
    assert 'presentation === "c"' in page_source
    assert '"handoff-b" : "handoff-c"' in page_source
    assert 'type PresentationMode = "default" | "handoff-a" | "handoff-b" | "handoff-c"' in client_source
    assert "HandoffAScreens" in client_source
    assert "AOverviewScreen" in client_source
    assert "ADeepDiveScreen" in client_source
    assert "ARotationScreen" in client_source
    assert "HandoffBScreens" in client_source
    assert "BOverviewScreen" in client_source
    assert "BDeepDiveScreen" in client_source
    assert "BRotationScreen" in client_source
    assert "HandoffCScreens" in client_source
    assert "COverviewScreen" in client_source
    assert "CDeepDiveScreen" in client_source
    assert "CRotationScreen" in client_source
    assert 'data-presentation="handoff-a"' in client_source
    assert 'data-presentation="handoff-b"' in client_source
    assert 'data-presentation="handoff-c"' in client_source
    assert ".handoff-main" in css_source
    assert ".a-shell" in css_source
    assert ".a-bluf" in css_source
    assert ".a-heatmap" in css_source
    assert ".b-shell" in css_source
    assert ".b-masthead" in css_source
    assert ".b-headline-grid" in css_source
    assert ".c-shell" in css_source
    assert ".c-weather" in css_source
    assert ".c-overview-grid" in css_source


def test_next_shell_chart_primitives_are_snapshot_driven():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for component in ("PillarHeatmap", "WaterfallChart", "PillarDetailGrid", "RrgChart", "MomentumBars", "FlowRiver"):
        assert component in chart_source
        assert component in client_source
    assert "pillarContributions(row: SnapshotRow)" in chart_source
    assert "row.s_score / rawSum" in chart_source
    assert "positiveOffset += width" in chart_source
    assert "negativeOffset += width" in chart_source
    assert "x(100)" in chart_source
    assert "y(100)" in chart_source
    assert ".sort((a, b) => (b.momentum_pct ?? 0) - (a.momentum_pct ?? 0))" in chart_source
    assert "Data-derived map from current weakest flow/score rows into strongest flow/score rows." in chart_source
    assert "Jegadeesh & Titman 1993" in chart_source
    assert "weights sum to 1.00" in chart_source
    assert "Price + 30wMA" in client_source
    assert "No OBV divergence" in client_source
    assert ".pillar-stack" in css_source
    assert ".waterfall-chart" in css_source
    assert ".rrg-chart" in css_source
    assert ".flow-river" in css_source


def test_next_shell_flow_river_uses_live_pressure_summary_not_fixture_lanes():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        "function flowLabel(row: SnapshotRow): string",
        "const balancedPressure = Math.min(totalOut, totalIn)",
        "flowRiverGradient",
        "relative pressure ${fmt(pressure, 2)}",
        "weakest support is led by {outflows[0].display_label}",
        "strongest sponsorship is led by {inflows[0].display_label}",
    ):
        assert marker in chart_source

    for forbidden in (
        "Tech/Semis",
        "Gold miners",
        "$3.4B",
        "scenario fixtures",
    ):
        assert forbidden not in chart_source

    for marker in (
        ".flow-river .flow-out-node",
        ".flow-river .flow-in-node",
        ".flow-river [data-tooltip]",
    ):
        assert marker in css_source


def test_next_shell_c3_rotation_uses_handoff_metadata_without_static_rows():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        'title="Relative rotation | US Sectors"',
        'subtitle="4-week trail"',
        "meta={`${rows.length} rows`}",
        'title="12-1 momentum"',
        'meta="z-scored"',
        "Where the money was, where it is, where it's heading.",
    ):
        assert marker in client_source

    for marker in (
        "title = \"Relative Rotation Graph\"",
        "meta?: string;",
        "{meta ? <strong>{meta}</strong> : null}",
        "title = \"12-1 Momentum Rank\"",
    ):
        assert marker in chart_source

    for marker in (
        ".c-rotation-head {",
        "max-width: 860px;",
        "font-size: 2rem;",
    ):
        assert marker in css_source

    assert "11 sectors" not in client_source


def test_next_shell_b3_leaderboards_open_editorial_deep_dive():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")

    for marker in (
        "function BLeaderboard({ title, rows, onSelectTicker }",
        "const openDeepDive = (ticker: string) =>",
        "onSelectTicker(ticker);",
        "setActiveScreen(\"deepdive\")",
        "<BLeaderboard title=\"LEADERS\" rows={leaders} onSelectTicker={openDeepDive} />",
        "<BLeaderboard title=\"LAGGARDS\" rows={laggards} onSelectTicker={openDeepDive} />",
    ):
        assert marker in client_source

    for forbidden in ("Tech/Semis", "Gold miners", "$3.4B"):
        assert forbidden not in client_source


def test_next_shell_b3_rrg_points_are_keyboard_drilldowns():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")

    for marker in (
        "function BRrgEditorial({ rows, onSelectTicker }",
        "className=\"b-rrg-point\"",
        "role=\"button\"",
        "tabIndex={0}",
        "onKeyDown={(event) =>",
        "event.key === \"Enter\" || event.key === \" \"",
        "event.preventDefault();",
        "aria-label={`Open ${row.ticker} editorial deep dive`}",
        "<title>{`Open ${row.ticker} editorial deep dive`}</title>",
    ):
        assert marker in client_source


def test_next_shell_pillar_stack_has_native_value_specific_tooltips():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    assert "function pillarTooltip(row: SnapshotRow, pillar: PillarContribution): string" in chart_source
    assert "pillarReading(row, pillar)" in chart_source
    assert "Weight ${Math.round(pillar.weight * 100)}%" in chart_source
    assert "normalized input ${fmt(pillar.raw, 2)}" in chart_source
    assert "contribution ${fmt(pillar.contribution, 2)}" in chart_source
    assert "data-tooltip={tooltip}" in chart_source
    assert "data-pillar-code={pillar.code}" in chart_source
    assert "aria-label={tooltip}" in chart_source
    assert "title={tooltip}" in chart_source
    assert 'title={`${pillar.label}: ${fmt(pillar.contribution)}`}' not in chart_source
    assert ".pillar-heatmap-card" in css_source
    assert ".pillar-segment[data-tooltip]::after" in css_source
    assert "width: min(360px, calc(100vw - 48px));" in css_source
    assert "max-width: calc(100vw - 48px);" in css_source
    assert "overflow-wrap: break-word;" in css_source
    assert "white-space: normal;" in css_source


def test_next_shell_c1_heatmap_uses_handoff_pillar_palette_and_layout():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for hue in ("#2e6fa3", "#5d8ec0", "#3f8862", "#6da884", "#9d7838", "#a85a3a", "#7a3a5d"):
        assert hue in chart_source
    for marker in (
        'className="chart-heading c-heatmap-heading"',
        "{rows.length} instruments | sorted by S",
        "PillarLegend",
        "composition-axis-copy",
    ):
        assert marker in chart_source
    for marker in (
        ".pillar-heatmap-card",
        "padding: 22px 28px;",
        "background: #fff;",
        ".c-heatmap-heading h3",
        "grid-template-columns: 52px minmax(260px, 1fr) 78px 60px 64px;",
        "font-family: ui-monospace, SFMono-Regular, Consolas, monospace;",
        "border-bottom: 1px solid #e6e1d8;",
    ):
        assert marker in css_source


def test_next_shell_c_topbar_uses_handoff_logo_and_controls():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        '<span className="c-logo" aria-hidden="true">',
        'aria-label="Refresh candidate snapshot">↻</button>',
        'aria-label="Display mode">☾</button>',
    ):
        assert marker in client_source
    for marker in (
        "grid-template-columns: repeat(4, 3.6px);",
        ".c-logo span:nth-child(1)",
        "height: 16px;",
        ".c-brand > span:last-child",
        "margin-right: auto;",
    ):
        assert marker in css_source


def test_next_shell_c_weather_strip_uses_handoff_outer_band_and_inner_card():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    assert 'className="c-screen c-overview-screen"' in client_source
    assert 'className="c-weather-card"' in client_source
    assert ".c-weather-card" in css_source
    assert ".c-overview-screen" in css_source
    assert "const headline = `${leadText} leads; ${riskText} under pressure.`;" in client_source
    assert "<strong>{headline}</strong>" in client_source
    assert "padding: 24px 0 20px;" in css_source
    assert "grid-template-columns: 1.4fr repeat(5, minmax(0, 1fr));" in css_source
    assert "padding: 18px 24px;" in css_source
    assert ".c-weather-card > div:not(.c-weather-lead) strong" in css_source


def test_next_shell_c1_right_rail_uses_handoff_padded_cards():
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        "const transitions = snapshot.screens.overview?.transitions ?? [];",
        "<TransitionRailRow",
        "No saved transition rows were found in the snapshot; showing latest model actions instead.",
        "function TransitionRailRow",
        "transitioned ${transition.from} to ${transition.to}",
        "<time>{transition.date || \"undated\"}</time>",
    ):
        assert marker in client_source

    for marker in (
        ".c-right-rail .c-rail-card",
        "padding: 18px 22px;",
        ".c-right-rail .c-sec-head",
        "grid-template-columns: 8px 44px minmax(0, 1fr) auto;",
        "grid-template-columns: 48px minmax(0, 1fr) auto;",
        "padding: 10px 0;",
        ".c-rail-card button.good i",
        ".c-rail-card button.bad i",
        ".c-rail-card button time",
    ):
        assert marker in css_source


def test_next_shell_c1_heatmap_uses_handoff_legend_strip():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        'className="c-pillar-legend-strip"',
        "Pillar contribution legend and axis",
        "<span>TKR</span>",
        "<span>COMPOSITION</span>",
        "<span>STATE</span>",
        "<span>MOM</span>",
    ):
        assert marker in chart_source

    for marker in (
        ".c-pillar-legend-strip",
        "padding: 0 0 14px;",
        "border-bottom: 1px solid #e6e1d8;",
        ".c-pillar-legend-strip .composition-axis-copy",
        "justify-content: flex-start;",
    ):
        assert marker in css_source


def test_next_shell_c1_heatmap_uses_compact_state_and_shared_bar_domain():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")

    for marker in (
        "function compactStateLabel",
        'return "BULLISH"',
        'return "WARN"',
        'return "EXIT"',
        "compactStateLabel(state)",
        "function signedFmt",
        "function momentumFmt",
        "function pillarSideTotals",
        "maxSide?: number",
        "const heatmapMaxSide = Math.max",
        "maxSide={heatmapMaxSide}",
        "signedFmt(row.s_score)",
        "momentumFmt(row.momentum_pct)",
    ):
        assert marker in chart_source


def test_next_shell_c1_heatmap_uses_compact_live_row_density():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        "const C1_VISIBLE_ROW_TARGET = 67;",
        "function c1VisibleRowCounts",
        "const visibleCounts = c1VisibleRowCounts(grouped, classes);",
        'className="composition-overflow"',
        "{overflow.length} more live rows",
        "function CompositionRowButton",
    ):
        assert marker in chart_source

    for marker in (
        "min-height: 32px;",
        "padding: 4px 0;",
        "min-width: 68px;",
        "font-size: 0.62rem;",
        "height: 20px;",
        "height: 16px;",
        "padding: 10px 0 3px;",
        ".composition-overflow summary",
        ".composition-overflow[open] summary",
    ):
        assert marker in css_source


def test_next_shell_rrg_and_flow_have_native_value_specific_tooltips():
    chart_source = (WEB / "app" / "chart-primitives.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        "function rrgTooltip(row: SnapshotRow): string",
        "RS-ratio ${ratio}",
        "RS-momentum ${momentum}",
        "S ${fmt(row.s_score)} and F ${fmt(row.f_score)}",
        "const tooltip = rrgTooltip(row);",
        "role=\"button\"",
        "tabIndex={0}",
        "onKeyDown={(event) =>",
        "<title>{tooltip}</title>",
        "data-tooltip={tooltip}",
    ):
        assert marker in chart_source
    for marker in (
        "function flowMagnitude(row: SnapshotRow): number",
        "function flowTooltip(row: SnapshotRow, side: \"outflow\" | \"inflow\"): string",
        "F-score ${fmt(row.f_score)}; CMF(21) ${fmt(row.cmf21, 2)}; S ${fmt(row.s_score)}",
        "function flowLaneTooltip(source: SnapshotRow, target: SnapshotRow, width: number, pressure: number): string",
        "<title>{flowLaneTooltip(source, target, strokeWidth, pressure)}</title>",
        "aria-label={tooltip} data-tooltip={tooltip}",
    ):
        assert marker in chart_source
    assert ".rrg-point:focus-visible circle" in css_source
    assert "stroke-width: 3px;" in css_source


def test_next_shell_deep_dive_fetches_cached_ticker_chart_without_fixture_data():
    api_source = (WEB / "lib" / "api.ts").read_text(encoding="utf-8")
    client_source = (WEB / "app" / "dashboard-screens-client.tsx").read_text(encoding="utf-8")
    css_source = (WEB / "app" / "globals.css").read_text(encoding="utf-8")

    for marker in (
        "TickerChartPayload",
        "TickerChartPoint",
        "TickerFlowPoint",
        "TickerRelativeStrengthPoint",
        "/api/v1/ticker-chart",
        "relative_strength_series",
        "momentum_12w",
        "momentum_52w",
        "fetchTickerChart(ticker: string, period = \"3y\", benchmark?: string)",
    ):
        assert marker in api_source
    for marker in (
        "TickerPriceChartPanel",
        "fetchTickerChart(row.ticker, \"3y\")",
        "payload?.series.filter",
        "Weekly close",
        "30wMA",
        "Source is",
        "<TickerPriceChartPanel row={focus} />",
        "TickerFlowChartPanels",
        "FlowMiniLine",
        "payload?.flow_series",
        "CMF(21)",
        "OBV slope",
        "<TickerFlowChartPanels row={focus} />",
        "TickerRelativeStrengthPanel",
        "RelativeMiniLine",
        "payload?.relative_strength_series",
        "Relative strength + momentum",
        "<TickerRelativeStrengthPanel row={focus} />",
    ):
        assert marker in client_source
    for marker in (
        ".c-price-chart-panel",
        ".price-chart-kpis",
        ".ticker-price-chart",
        ".ticker-price-chart .price-line",
        ".ticker-price-chart .ma-line",
        ".c-flow-evidence-panel",
        ".flow-evidence-grid",
        ".flow-mini-chart.cmf-line",
        ".flow-mini-chart.obv-line",
        ".flow-mini-chart.rs-line",
        ".flow-mini-chart.momentum-line",
    ):
        assert marker in css_source
    for forbidden in ("sample close", "demo price", "fixture price"):
        assert forbidden not in client_source


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
