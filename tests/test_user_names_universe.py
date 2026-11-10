import json

from src.universe import MEGA_CAP_STOCKS, USER_CLASS, user_class_overrides, user_tickers


def _write(tmp_path, items):
    path = tmp_path / "saved_inputs.json"
    path.write_text(json.dumps({"version": 1, "items": items}), encoding="utf-8")
    return path


def test_user_tickers_merges_watchlists_and_portfolios_without_duplicates(tmp_path):
    path = _write(tmp_path, [
        {"kind": "watchlist", "name": "w", "tickers": ["zbra", "AAOI"]},
        {"kind": "portfolio", "name": "p", "holdings": [{"ticker": "AAOI"}, {"ticker": "ORCL"}]},
    ])
    assert user_tickers(path) == ["ZBRA", "AAOI", "ORCL"]


def test_user_tickers_returns_empty_for_missing_file(tmp_path):
    assert user_tickers(tmp_path / "nope.json") == []


def test_overrides_skip_names_already_in_a_methodology_class(tmp_path):
    mega = MEGA_CAP_STOCKS[0]
    path = _write(tmp_path, [{"kind": "watchlist", "name": "w", "tickers": [mega, "ORCL", "SPY"]}])
    overrides = user_class_overrides(path)
    assert mega not in overrides
    assert overrides.get("ORCL") == USER_CLASS
    assert "SPY" not in overrides  # benchmark keeps its own class
