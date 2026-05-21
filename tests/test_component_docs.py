from __future__ import annotations

from pathlib import Path

from src.component_docs import (
    DASHBOARD_COMPONENT_DOCS,
    component_docs_html,
    component_docs_rows,
    documented_render_functions,
)


ROOT = Path(__file__).resolve().parent.parent


def test_component_docs_cover_dashboard_render_sections():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_lines = [
        line.strip()
        for line in app_source.splitlines()
        if line.strip().startswith('_render_timed("render_')
    ]
    render_functions = {
        line.split(",", 1)[1].split(")", 1)[0].strip()
        for line in render_lines
        if "render_component_docs" not in line
    }

    assert render_functions
    assert documented_render_functions(DASHBOARD_COMPONENT_DOCS) == render_functions


def test_component_docs_rows_are_operator_scannable():
    rows = component_docs_rows(DASHBOARD_COMPONENT_DOCS)

    assert len(rows) >= 10
    assert rows[0] == {
        "Component": "Header",
        "Section": "Shell",
        "Render Function": "render_header",
        "Data Inputs": "clock, app version, current theme",
        "States": "live timestamp, next refresh label",
        "QA": "static app wiring, responsive CSS",
    }
    assert all(row["Component"] for row in rows)
    assert all(row["Render Function"].startswith("render_") for row in rows)


def test_component_docs_html_is_generated_from_catalog():
    html = component_docs_html(DASHBOARD_COMPONENT_DOCS)

    assert "Component docs" in html
    assert "Storybook-style inventory" in html
    assert "render_bluf" in html
    assert "Portfolio analyzer" in html
    assert "Backtest lab" in html
    assert "fetch_ohlcv(" not in html
