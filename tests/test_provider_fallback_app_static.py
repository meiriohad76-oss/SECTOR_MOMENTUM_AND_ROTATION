from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_uses_fetch_result_and_renders_provider_status_banner():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.data import fetch_ohlcv_result, _select_ohlcv_provider" in app_source
    assert "def provider_status_banner_html(ohlcv_result)" in app_source
    assert "def render_provider_status_banner(ohlcv_result) -> None:" in app_source
    assert "return fetch_ohlcv_result(tickers, period=period)" in app_source
    assert "ohlcv_result = _load_data(\"3y\")" in app_source
    assert "render_provider_status_banner(ohlcv_result)" in app_source
    assert "ohlcv = ohlcv_result.data" in app_source
    assert "used_stale_cache" in app_source
    assert "provider-status-banner" in app_source


def test_provider_status_banner_css_exists():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".provider-status-banner" in css
    assert ".provider-status-banner .label" in css
