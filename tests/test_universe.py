from __future__ import annotations

import re
from pathlib import Path

from src import universe
from src.universe import ALL_TICKERS, THEMES, TOP_N, UNIVERSE_BY_CLASS, US_INDUSTRIES, class_of


EXPECTED_CRYPTO_TICKERS = ("BITO", "IBIT", "ETHE")
EXPECTED_THEME_TICKERS = ("ARKK", "HACK", "MOO", "URA", "LIT", "TAN", "ICLN", "BOTZ")
ROOT = Path(__file__).resolve().parents[1]


def test_theme_universe_contains_backlog_theme_etfs():
    assert tuple(THEMES) == EXPECTED_THEME_TICKERS
    assert UNIVERSE_BY_CLASS["Themes"] == THEMES


def test_crypto_universe_contains_backlog_crypto_etfs():
    assert tuple(universe.CRYPTO) == EXPECTED_CRYPTO_TICKERS
    assert UNIVERSE_BY_CLASS["Crypto"] == universe.CRYPTO


def test_theme_tickers_classify_as_themes_not_industries():
    for ticker in EXPECTED_THEME_TICKERS:
        assert class_of(ticker) == "Themes"
        assert ticker not in US_INDUSTRIES


def test_crypto_tickers_classify_as_crypto():
    for ticker in EXPECTED_CRYPTO_TICKERS:
        assert class_of(ticker) == "Crypto"


def test_all_tickers_includes_theme_etfs_without_duplicates():
    for ticker in EXPECTED_THEME_TICKERS + EXPECTED_CRYPTO_TICKERS:
        assert ticker in ALL_TICKERS
    assert len(ALL_TICKERS) == len(set(ALL_TICKERS))


def test_every_universe_class_has_positive_top_n_target():
    assert TOP_N["Themes"] == 3
    assert TOP_N["Crypto"] == 1
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


def test_product_design_summary_documents_theme_universe_count():
    text = (ROOT / "docs" / "PRODUCT_DESIGN.md").read_text(encoding="utf-8")

    assert "76+ ETFs" in text
    assert "thematic exposures" in text
    assert "crypto exposures" in text
    assert "73+ ETFs" not in text
    assert "67+ ETFs" not in text


def test_app_copy_uses_current_universe_count_without_stale_numbers():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "{len(ALL_TICKERS)} ETFs" in text
    assert "{len(scored)} of {len(ALL_TICKERS)} ETFs" in text
    assert "67 ETFs" not in text
    assert "73 ETFs" not in text
