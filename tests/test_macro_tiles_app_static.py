from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_fetches_macro_context_symbols_for_header_tiles():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.macro_tiles import MACRO_CONTEXT_SYMBOLS, macro_tile_rows" in app_source
    assert "DATA_SYMBOLS = list(dict.fromkeys(ALL_TICKERS + list(MACRO_CONTEXT_SYMBOLS) + [\"^TNX\", \"^IRX\"]))" in app_source
    assert "tickers = DATA_SYMBOLS" in app_source
    assert "daily OHLCV (3y, {len(DATA_SYMBOLS)} symbols)" in app_source
    assert "missing_ohlcv\": sorted(set(DATA_SYMBOLS) - set(ohlcv_payload))" in app_source
    assert "scoring_ohlcv = {t: ohlcv[t] for t in ALL_TICKERS if t in ohlcv}" in app_source
    assert "compute_all_indicators(scoring_ohlcv, bench_ticker, bil_ticker)" in app_source
    assert "compute_flow_signals(scoring_ohlcv)" in app_source
    assert "macro_tile_rows(ohlcv)" in app_source
    assert "macro_tiles_html" in app_source
    assert "Market state <span class=\"count\">7 indicators</span>" in app_source


def test_status_row_css_supports_macro_tile_layout():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".status-row {\n  display: grid;\n  grid-template-columns: repeat(4, 1fr);" in css
    assert ".macro-tile .tile-value" in css
