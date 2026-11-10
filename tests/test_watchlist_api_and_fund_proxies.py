from src.api_watchlists import (
    build_saved_watchlists_payload,
    delete_saved_watchlist_payload,
    save_saved_watchlist_payload,
)
from src.bluf import load_fund_proxy_notes, portfolio_view


def test_watchlist_round_trip_uses_only_the_given_file(tmp_path):
    path = tmp_path / "saved_inputs.json"
    saved = save_saved_watchlist_payload({"name": "Test list", "tickers": "aaoi, zbra\nqqq"}, path=path)
    assert saved["status"] == "ready"
    listed = build_saved_watchlists_payload(path)
    assert listed["watchlist_count"] == 1
    assert listed["watchlists"][0]["tickers"] == ["AAOI", "ZBRA", "QQQ"]
    assert delete_saved_watchlist_payload("Test list", path=path)["deleted"] is True
    assert build_saved_watchlists_payload(path)["watchlist_count"] == 0


def test_watchlist_save_rejects_empty_name_or_tickers(tmp_path):
    path = tmp_path / "saved_inputs.json"
    assert save_saved_watchlist_payload({"name": "", "tickers": ["AAOI"]}, path=path)["status"] == "error"
    assert save_saved_watchlist_payload({"name": "x", "tickers": []}, path=path)["status"] == "error"


def test_fund_proxy_notes_load_and_flow_into_portfolio_view():
    notes = load_fund_proxy_notes()
    assert "CGDV" in notes and not any(k.startswith("_") for k in notes)
    rows = portfolio_view([], {"CGDV": "XLK"}, ["CGDV", "ORCL"], set())
    by = {r["ticker"]: r for r in rows}
    assert by["CGDV"]["sector_note"] == notes["CGDV"]
    assert by["ORCL"]["sector_note"] is None
