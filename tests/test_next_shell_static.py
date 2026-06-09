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

    assert 'process.env.NEXT_PUBLIC_API_BASE_URL' in api_source
    assert 'process.env.API_BASE_URL' in api_source
    assert 'fetchDashboardApi<DashboardHealthPayload>("/api/v1/health")' in api_source
    assert 'fetchDashboardApi<DashboardHealthPayload>("/api/v1/data-health")' in api_source
    assert 'fetchDashboardApi<DashboardSnapshotPayload>(`/api/v1/dashboard-snapshot${query}`)' in api_source
    assert 'cache: "no-store"' in api_source
    assert "fetchDashboardSnapshot()" in page_source
    assert "await Promise.all([" in page_source
    assert "fetch(" not in page_source


def test_next_shell_renders_health_tables_and_provider_rail_without_fixture_market_data():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")

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
        assert marker in page_source
    for forbidden in ("handoff", "mockup", "sample market", "XLK", "Technology sector"):
        assert forbidden not in page_source


def test_next_shell_snapshot_sections_are_api_driven_not_hardcoded():
    page_source = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")

    assert "SnapshotScreens" in page_source
    assert "snapshot?.screens.overview?.leaders" in page_source
    assert "snapshot?.screens.rotation?.sectors" in page_source
    assert "focus?.pillar_scores" in page_source
    assert "decision.rationale" in page_source


def test_next_shell_gitignore_excludes_node_and_next_artifacts():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "node_modules/" in gitignore
    assert "web/.next/" in gitignore
    assert "web/node_modules/" in gitignore
