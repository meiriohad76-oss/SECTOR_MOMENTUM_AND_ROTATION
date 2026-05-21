from __future__ import annotations

import re
from pathlib import Path

from src import universe
from src.universe import (
    ALL_TICKERS,
    BENCH,
    SCORED_TICKERS,
    THEMES,
    TOP_N,
    UNIVERSE_BY_CLASS,
    US_INDUSTRIES,
    class_of,
)


EXPECTED_CRYPTO_TICKERS = ("BITO", "IBIT", "ETHE")
EXPECTED_MEGA_CAP_STOCKS = ("NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA")
EXPECTED_THEME_TICKERS = ("ARKK", "HACK", "MOO", "URA", "LIT", "TAN", "ICLN", "BOTZ")
ROOT = Path(__file__).resolve().parents[1]


def test_theme_universe_contains_backlog_theme_etfs():
    assert tuple(THEMES) == EXPECTED_THEME_TICKERS
    assert UNIVERSE_BY_CLASS["Themes"] == THEMES


def test_crypto_universe_contains_backlog_crypto_etfs():
    assert tuple(universe.CRYPTO) == EXPECTED_CRYPTO_TICKERS
    assert UNIVERSE_BY_CLASS["Crypto"] == universe.CRYPTO


def test_mega_cap_stock_universe_contains_backlog_tickers():
    assert tuple(universe.MEGA_CAP_STOCKS) == EXPECTED_MEGA_CAP_STOCKS
    assert UNIVERSE_BY_CLASS["Mega-Cap Stocks"] == universe.MEGA_CAP_STOCKS


def test_theme_tickers_classify_as_themes_not_industries():
    for ticker in EXPECTED_THEME_TICKERS:
        assert class_of(ticker) == "Themes"
        assert ticker not in US_INDUSTRIES


def test_crypto_tickers_classify_as_crypto():
    for ticker in EXPECTED_CRYPTO_TICKERS:
        assert class_of(ticker) == "Crypto"


def test_mega_cap_stocks_classify_as_their_own_class():
    for ticker in EXPECTED_MEGA_CAP_STOCKS:
        assert class_of(ticker) == "Mega-Cap Stocks"


def test_all_tickers_includes_theme_etfs_without_duplicates():
    for ticker in EXPECTED_THEME_TICKERS + EXPECTED_CRYPTO_TICKERS + EXPECTED_MEGA_CAP_STOCKS:
        assert ticker in ALL_TICKERS
    assert len(ALL_TICKERS) == len(set(ALL_TICKERS))


def test_scored_tickers_exclude_benchmarks_for_dashboard_counts():
    assert len(SCORED_TICKERS) == 83
    for ticker in BENCH.values():
        assert ticker in ALL_TICKERS
        assert ticker not in SCORED_TICKERS


def test_every_universe_class_has_positive_top_n_target():
    assert TOP_N["Themes"] == 3
    assert TOP_N["Crypto"] == 1
    assert TOP_N["Mega-Cap Stocks"] == 3
    for class_name in UNIVERSE_BY_CLASS:
        assert TOP_N[class_name] > 0


def test_methodology_universe_section_documents_theme_class():
    text = (ROOT / "docs" / "sector-rotation-methodology.md").read_text(encoding="utf-8")

    industries_match = re.search(r"### 3\.2 US industries.*?\n`([^`]+)`", text, re.S)
    assert industries_match is not None
    industry_tickers = industries_match.group(1).split()
    assert "TAN" not in industry_tickers
    assert "ICLN" not in industry_tickers
    assert "### 3.5 Thematic exposures" in text
    assert "`ARKK HACK MOO URA LIT TAN ICLN BOTZ`" in text
    assert "### 3.6 Crypto exposures" in text
    assert "`BITO IBIT ETHE`" in text
    assert "N_crypto        = 1   (out of 3)" in text
    assert "### 3.7 Mega-cap individual stocks" in text
    assert "`NVDA AAPL MSFT AMZN GOOGL META TSLA`" in text
    assert "N_mega_cap_stocks = 3   (out of 7)" in text


def test_product_design_summary_documents_theme_universe_count():
    text = (ROOT / "docs" / "PRODUCT_DESIGN.md").read_text(encoding="utf-8")

    assert "83+ instruments" in text
    assert "thematic exposures" in text
    assert "crypto exposures" in text
    assert "mega-cap stocks" in text
    assert "76+ ETFs" not in text
    assert "73+ ETFs" not in text
    assert "67+ ETFs" not in text


def test_app_copy_uses_current_universe_count_without_stale_numbers():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "{len(SCORED_TICKERS)} instruments" in text
    assert "{len(scored)} of {len(SCORED_TICKERS)} instruments" in text
    assert "daily OHLCV (3y, {len(ALL_TICKERS) + 2} symbols)" in text
    assert "{len(scored)} INSTRUMENTS" in text
    assert "67 ETFs" not in text
    assert "73 ETFs" not in text
    assert "76 ETFs" not in text
    assert "ETFS" not in text
    assert "~70 tickers" not in text
