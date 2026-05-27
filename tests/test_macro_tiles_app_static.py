from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_fetches_macro_context_symbols_for_header_tiles():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        "from src.macro_tiles import MACRO_CONTEXT_SYMBOLS, fred_macro_snapshot, "
        "fred_macro_tile_groups, macro_tile_rows, session_range_tile"
    ) in app_source
    assert "DATA_SYMBOLS = list(dict.fromkeys(ALL_TICKERS + list(MACRO_CONTEXT_SYMBOLS) + [\"^TNX\", \"^IRX\"]))" in app_source
    assert "tickers = DATA_SYMBOLS" in app_source
    assert "daily OHLCV (3y, {len(DATA_SYMBOLS)} symbols)" in app_source
    assert "missing_ohlcv\": sorted(set(DATA_SYMBOLS) - set(ohlcv_payload))" in app_source
    assert "scoring_ohlcv = {t: ohlcv[t] for t in ALL_TICKERS if t in ohlcv}" in app_source
    assert "compute_all_indicators(scoring_ohlcv, bench_ticker, bil_ticker)" in app_source
    assert "compute_flow_signals(scoring_ohlcv)" in app_source
    assert "session_range_tile(ohlcv.get(BENCH[\"US\"]), BENCH[\"US\"])" in app_source
    assert "session_tile_html" in app_source
    assert "macro_tile_rows(ohlcv, fred_data=_fred_data)" in app_source
    assert "macro_tiles_html" in app_source
    assert "fred_macro_tile_groups(_fred_data)" in app_source
    assert "fred_macro_groups_html" in app_source
    assert "def _macro_tile_html(row: dict[str, object], extra_class: str = \"\") -> str:" in app_source
    assert 'class="tile macro-tile {extra_class} {tone}"' in app_source
    assert '_macro_tile_html(row, extra_class="fred-macro-tile")' in app_source
    assert "data-tip=\"{_esc(str(row.get('tooltip', '')))}\"" in app_source
    assert "macro-signal {sentiment_class}" in app_source
    assert "macro-gauge\" style=\"--gauge:{gauge_pct}%\"" in app_source
    assert "Market state <span class=\"count\">Live indicators</span>" in app_source
    assert "Expanded FRED macro context" in app_source


def test_status_row_css_supports_macro_tile_layout():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".status-row {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));" in css
    assert ".macro-tile .tile-value" in css
    assert ".macro-signal" in css
    assert ".macro-gauge" in css
    assert ".fred-macro-context" in css
    assert ".fred-macro-grid" in css
    assert ".fred-macro-tile .tile-label" in css
