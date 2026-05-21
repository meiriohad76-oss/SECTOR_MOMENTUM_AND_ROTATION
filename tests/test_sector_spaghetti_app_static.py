from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_sector_spaghetti_chart_from_existing_ohlcv():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "sector_spaghetti_chart" in app_source
    assert "US_SECTORS" in app_source
    assert "def render_sector_spaghetti():" in app_source
    assert 'sector_spaghetti_chart(ohlcv, US_SECTORS, BENCH["US"])' in app_source
    assert "fetch_ohlcv(US_SECTORS" not in app_source


def test_sector_spaghetti_renders_between_rrg_and_drill():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        "render_rrg()\nrender_sector_spaghetti()\nrender_drill()"
        in app_source
    )
