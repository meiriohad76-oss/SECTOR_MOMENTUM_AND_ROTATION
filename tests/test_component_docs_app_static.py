from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _function_source(source: str, name: str) -> str:
    start = source.index(f"def {name}():")
    tail = source[start:]
    markers = [idx for marker in ("\ndef ", "\n# ===") if (idx := tail.find(marker, 1)) != -1]
    end = min(markers) if markers else len(tail)
    return tail[:end]


def test_app_wires_component_docs_page_without_data_fetches():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.component_docs import DASHBOARD_COMPONENT_DOCS, component_docs_html" in app_source
    assert "def render_component_docs():" in app_source

    docs_source = _function_source(app_source, "render_component_docs")

    assert "_operator_mode_enabled()" in docs_source
    assert "Component inventory" in docs_source
    assert "component_docs_html(DASHBOARD_COMPONENT_DOCS)" in docs_source
    assert "fetch_ohlcv(" not in docs_source
    assert "_load_data(" not in docs_source
    assert "refresh_market_data(" not in docs_source
    assert "compute_all_indicators(" not in docs_source
    assert "apply_state_machine(" not in docs_source
    assert "append_dashboard_run(" not in docs_source
    assert "st.session_state" not in docs_source


def test_component_docs_render_early_in_dashboard_order():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    render_order = [
        '_render_timed("render_explainer", render_explainer)',
        '_render_timed("render_component_docs", render_component_docs)',
        '_render_timed("render_bluf", render_bluf)',
    ]
    positions = [app_source.index(call) for call in render_order]

    assert positions == sorted(positions)
