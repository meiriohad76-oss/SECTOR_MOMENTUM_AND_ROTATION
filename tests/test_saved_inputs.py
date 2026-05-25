from __future__ import annotations

import json

from src import saved_inputs
from src.portfolio import HoldingInput


def test_save_watchlist_normalizes_deduplicates_and_replaces_by_kind_and_name(tmp_path):
    store_path = tmp_path / "saved_inputs.json"

    first = saved_inputs.save_watchlist(
        " Core Tech ",
        ["xlk", "XLF", "XLK", "bad ticker"],
        path=store_path,
        now="2026-05-21T10:00:00Z",
    )
    second = saved_inputs.save_watchlist(
        "core tech",
        ["soxx"],
        path=store_path,
        now="2026-05-21T11:00:00Z",
    )

    assert first.ok is True
    assert second.ok is True
    items = saved_inputs.load_saved_inputs(store_path)
    assert len(items) == 1
    assert items[0].kind == "watchlist"
    assert items[0].name == "core tech"
    assert items[0].tickers == ["SOXX"]
    assert items[0].updated_at == "2026-05-21T11:00:00Z"


def test_save_watchlist_rejects_empty_name_or_empty_valid_tickers(tmp_path):
    store_path = tmp_path / "saved_inputs.json"

    no_name = saved_inputs.save_watchlist("", ["XLK"], path=store_path)
    no_tickers = saved_inputs.save_watchlist("Empty", ["bad ticker"], path=store_path)

    assert no_name.ok is False
    assert no_name.message == "name is required"
    assert no_tickers.ok is False
    assert no_tickers.message == "at least one valid ticker is required"
    assert saved_inputs.load_saved_inputs(store_path) == []


def test_save_portfolio_round_trips_holding_fields(tmp_path):
    store_path = tmp_path / "saved_inputs.json"
    holdings = [
        HoldingInput(
            ticker="XLK",
            shares=10.0,
            cost_basis=1000.0,
            market_value=2500.0,
            weight=0.6,
            sector="Technology",
            account="IRA",
            notes="core",
        ),
        HoldingInput(ticker="XLF", weight=0.4),
    ]

    result = saved_inputs.save_portfolio(
        "Retirement",
        holdings,
        path=store_path,
        now="2026-05-21T12:00:00Z",
    )

    assert result.ok is True
    loaded = saved_inputs.load_saved_inputs(store_path)
    assert len(loaded) == 1
    assert loaded[0].kind == "portfolio"
    assert loaded[0].name == "Retirement"
    assert loaded[0].holdings == holdings
    assert loaded[0].updated_at == "2026-05-21T12:00:00Z"


def test_delete_saved_input_removes_only_matching_kind_and_name(tmp_path):
    store_path = tmp_path / "saved_inputs.json"
    saved_inputs.save_watchlist("Core", ["XLK"], path=store_path)
    saved_inputs.save_portfolio("Core", [HoldingInput(ticker="XLK", weight=1.0)], path=store_path)

    deleted = saved_inputs.delete_saved_input("watchlist", "core", path=store_path)

    assert deleted is True
    remaining = saved_inputs.load_saved_inputs(store_path)
    assert len(remaining) == 1
    assert remaining[0].kind == "portfolio"
    assert remaining[0].name == "Core"


def test_load_saved_inputs_returns_empty_for_missing_or_corrupt_store(tmp_path):
    store_path = tmp_path / "saved_inputs.json"
    assert saved_inputs.load_saved_inputs(store_path) == []

    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text("{not-json", encoding="utf-8")

    assert saved_inputs.load_saved_inputs(store_path) == []


def test_saved_inputs_path_is_ignored_by_git_and_docker_contexts():
    gitignore = saved_inputs.ROOT.joinpath(".gitignore").read_text(encoding="utf-8")
    dockerignore = saved_inputs.ROOT.joinpath(".dockerignore").read_text(encoding="utf-8")

    assert "data/saved_inputs.json" in gitignore
    assert "data/saved_inputs.json" in dockerignore


def test_store_file_schema_is_versioned(tmp_path):
    store_path = tmp_path / "saved_inputs.json"
    saved_inputs.save_watchlist("Core", ["XLK"], path=store_path)

    payload = json.loads(store_path.read_text(encoding="utf-8"))

    assert payload["version"] == 1
    assert payload["items"][0]["kind"] == "watchlist"
