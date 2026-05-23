from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_has_explicit_browser_qa_mode_for_visual_fixtures():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "import os" in app_source
    assert "def _browser_qa_mode_enabled() -> bool:" in app_source
    assert "BROWSER_QA_MODE" in app_source
    assert 'return fetch_ohlcv_result(tickers, period=period, provider="yfinance")' in app_source
    assert "if _browser_qa_mode_enabled():\n        return {}" in app_source
    assert "browser_qa_palette" in app_source
    assert "st.session_state.color_palette = qa_palette" in app_source
    assert "browser_qa_provider_banner" in app_source
    assert "Browser QA provider fallback fixture - no API keys required." in app_source
    assert "browser_qa_transition" in app_source
    assert "BROWSER_QA" in app_source
    assert "_browser_qa_transitions(scored)" in app_source
