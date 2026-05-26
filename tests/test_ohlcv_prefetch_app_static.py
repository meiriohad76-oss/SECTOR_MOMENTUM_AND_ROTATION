from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_async_ohlcv_prefetch_as_cache_warmer_only():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.ohlcv_prefetch import prefetch_status, submit_ohlcv_prefetch" in app_source
    assert "def _start_ohlcv_cache_prefetch() -> None:" in app_source
    assert 'future = submit_ohlcv_prefetch(DATA_SYMBOLS, period="3y")' in app_source
    assert 'st.session_state["ohlcv_prefetch_future"] = future' in app_source
    assert 'st.session_state["ohlcv_prefetch_status"] = prefetch_status(future)' in app_source
    assert 'with PERF_AUDIT.section("ohlcv_prefetch"):' in app_source


def test_prefetch_does_not_feed_scoring_or_provider_status():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    compute_section = app_source[
        app_source.index('with PERF_AUDIT.section("compute_signals"):') : app_source.index(
            "st.session_state.dashboard_compute_snapshot = {"
        )
    ]

    assert 'ohlcv_result = _load_data("3y")' in app_source
    assert "submit_ohlcv_prefetch" not in compute_section
    assert "ohlcv_prefetch_future" not in compute_section
    assert "prefetch_status" not in compute_section
    assert "scoring_ohlcv = {t: ohlcv[t] for t in ALL_TICKERS if t in ohlcv}" in compute_section
    assert "MASSIVE_API_KEY" not in compute_section
    assert "Authorization" not in compute_section
