from __future__ import annotations

import json

import pytest

from src import provider_snapshots


def test_provider_snapshot_store_replays_latest_record_as_of_without_future_leakage(tmp_path):
    db_path = tmp_path / "provider_snapshots.sqlite"

    older = provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="xlk",
        as_of="2026-05-17",
        payload={"trades": [{"p": 100.0, "s": 100, "sip_timestamp": 1}]},
        captured_at_utc="2026-05-17T21:00:00Z",
    )
    provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-19",
        payload={"trades": [{"p": 200.0, "s": 100, "sip_timestamp": 1}]},
        captured_at_utc="2026-05-19T21:00:00Z",
    )

    before_first = provider_snapshots.load_provider_snapshot_as_of(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-16",
    )
    replayed = provider_snapshots.load_provider_snapshot_as_of(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-18",
    )

    assert before_first is None
    assert replayed == older
    assert replayed.ticker == "XLK"
    assert replayed.as_of == "2026-05-17"
    assert replayed.payload == {"trades": [{"p": 100.0, "s": 100, "sip_timestamp": 1}]}
    assert replayed.payload_sha256 == provider_snapshots.payload_sha256(replayed.payload)


def test_block_trade_ratio_as_of_uses_stored_massive_trades_only(tmp_path):
    db_path = tmp_path / "provider_snapshots.sqlite"
    provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-17",
        payload={
            "trades": [
                {"p": 100.0, "s": 100, "sip_timestamp": 1, "correction": 0},
                {"p": 101.0, "s": 3_000, "sip_timestamp": 2, "correction": 0},
                {"p": 99.0, "s": 4_000, "sip_timestamp": 3, "correction": 0},
            ]
        },
        captured_at_utc="2026-05-17T21:00:00Z",
    )
    provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-19",
        payload={"trades": [{"p": 999.0, "s": 50_000, "sip_timestamp": 1}]},
        captured_at_utc="2026-05-19T21:00:00Z",
    )

    ratio = provider_snapshots.block_trade_upside_ratio_as_of(
        db_path,
        ticker="XLK",
        as_of="2026-05-18",
    )

    assert ratio == pytest.approx((101.0 * 3_000) / (99.0 * 4_000))


def test_provider_snapshot_upsert_replaces_same_as_of_record(tmp_path):
    db_path = tmp_path / "provider_snapshots.sqlite"
    first = provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="MASSIVE",
        dataset="stock_trades",
        ticker="xlk",
        as_of="2026-05-17",
        payload={"trades": [{"p": 100.0}]},
        captured_at_utc="2026-05-17T21:00:00Z",
    )
    second = provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-17",
        payload={"trades": [{"p": 101.0}]},
        captured_at_utc="2026-05-17T22:00:00Z",
    )

    loaded = provider_snapshots.load_provider_snapshot_as_of(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-17",
    )
    rows = provider_snapshots.list_provider_snapshots(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
    )

    assert first.payload_sha256 != second.payload_sha256
    assert loaded == second
    assert len(rows) == 1
    assert json.dumps(loaded.payload, sort_keys=True) == '{"trades": [{"p": 101.0}]}'
