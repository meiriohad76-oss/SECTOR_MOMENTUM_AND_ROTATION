from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_saved_inputs_without_new_fetch_or_state_paths():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.saved_inputs import (" in app_source
    assert "SAVED_INPUTS_PATH = APP_ROOT / \"data\" / \"saved_inputs.json\"" in app_source
    assert "load_saved_inputs(SAVED_INPUTS_PATH)" in app_source
    assert "save_watchlist(" in app_source
    assert "save_portfolio(" in app_source
    assert "delete_saved_input(" in app_source
    assert "PortfolioInputResult(holdings=loaded.holdings, errors=[])" in app_source
    assert "parse_custom_universe_text(\" \".join(loaded.tickers))" in app_source
    assert "fetch_ohlcv(loaded" not in app_source
    assert "apply_state_machine(loaded" not in app_source


def test_app_exposes_save_load_delete_controls_for_watchlists_and_portfolios():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "def _saved_items(kind: str):" in app_source
    assert "def _render_save_watchlist_controls(" in app_source
    assert "def _render_save_portfolio_controls(" in app_source
    assert "LOAD WATCHLIST" in app_source
    assert "DELETE WATCHLIST" in app_source
    assert "SAVE WATCHLIST" in app_source
    assert "LOAD PORTFOLIO" in app_source
    assert "DELETE PORTFOLIO" in app_source
    assert "SAVE PORTFOLIO" in app_source


def test_readme_documents_local_saved_inputs():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "data/saved_inputs.json" in readme
    assert "Saved watchlists and portfolios" in readme
