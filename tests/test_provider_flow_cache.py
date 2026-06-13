from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

from src.provider_flow_cache import (
    initialize_provider_flow_cache,
    provider_flow_cache_coverage,
    provider_flow_cache_status,
    read_provider_flow_cache,
    request_hash,
    write_provider_flow_cache,
)


def test_provider_flow_cache_round_trips_fresh_rows(tmp_path):
    db_path = tmp_path / "provider_flow_cache.sqlite"
    rows = [{"p": 100.0, "s": 10_000}]

    written = write_provider_flow_cache(
        provider="Massive",
        lane="massive_block_trades",
        ticker="xlk",
        params={"limit": 25},
        payload=rows,
        path=db_path,
        created_at_utc=datetime(2026, 5, 27, 12, tzinfo=timezone.utc),
    )
    loaded = read_provider_flow_cache(
        provider="massive",
        lane="massive_block_trades",
        ticker="XLK",
        params={"limit": 25},
        ttl_seconds=3600,
        path=db_path,
        now=datetime(2026, 5, 27, 12, 10, tzinfo=timezone.utc),
    )

    assert written.ticker == "XLK"
    assert loaded is not None
    assert loaded.payload == rows
    assert loaded.is_fresh is True
    assert loaded.age_seconds == 600


def test_provider_flow_cache_respects_stale_policy(tmp_path):
    db_path = tmp_path / "provider_flow_cache.sqlite"
    write_provider_flow_cache(
        provider="finra",
        lane="finra_short_interest",
        ticker="XLK",
        params={"limit": 4},
        payload=[{"symbolCode": "XLK"}],
        path=db_path,
        created_at_utc=datetime(2026, 5, 27, 12, tzinfo=timezone.utc),
    )

    strict = read_provider_flow_cache(
        provider="finra",
        lane="finra_short_interest",
        ticker="XLK",
        params={"limit": 4},
        ttl_seconds=60,
        path=db_path,
        now=datetime(2026, 5, 27, 12, 2, tzinfo=timezone.utc),
    )
    stale = read_provider_flow_cache(
        provider="finra",
        lane="finra_short_interest",
        ticker="XLK",
        params={"limit": 4},
        ttl_seconds=60,
        path=db_path,
        allow_stale=True,
        now=datetime(2026, 5, 27, 12, 2, tzinfo=timezone.utc),
    )

    assert strict is None
    assert stale is not None
    assert stale.is_fresh is False


def test_provider_flow_cache_ignores_malformed_or_tampered_payload(tmp_path):
    db_path = tmp_path / "provider_flow_cache.sqlite"
    initialize_provider_flow_cache(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO provider_flow_cache (
                provider, lane, ticker, request_hash, created_at_utc, payload_json, payload_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "finra",
                "finra_ats_dark_pool",
                "XLK",
                request_hash({"limit": 40}),
                (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
                json.dumps([{"issueSymbolIdentifier": "XLK"}]),
                "wrong-hash",
            ),
        )

    loaded = read_provider_flow_cache(
        provider="finra",
        lane="finra_ats_dark_pool",
        ticker="XLK",
        params={"limit": 40},
        ttl_seconds=3600,
        path=db_path,
    )

    assert loaded is None


def test_provider_flow_cache_status_is_secret_safe(tmp_path):
    db_path = tmp_path / "provider_flow_cache.sqlite"
    write_provider_flow_cache(
        provider="massive",
        lane="massive_block_trades",
        ticker="SPY",
        params={"limit": 25, "api_key": "should-not-be-used-by-callers"},
        payload=[{"p": 1.0}],
        path=db_path,
    )

    status = provider_flow_cache_status(db_path)
    serialized = json.dumps(status)

    assert status["state"] == "ready"
    assert status["rows"] == 1
    assert "should-not-be-used" not in serialized


def test_provider_flow_cache_coverage_reports_missing_pairs_without_payloads(tmp_path):
    db_path = tmp_path / "provider_flow_cache.sqlite"
    write_provider_flow_cache(
        provider="massive",
        lane="massive_block_trades",
        ticker="XLK",
        params={"limit": 25, "api_key": "secret-value"},
        payload=[{"p": 1.0}],
        path=db_path,
        created_at_utc=datetime(2026, 5, 27, 12, tzinfo=timezone.utc),
    )
    write_provider_flow_cache(
        provider="finra",
        lane="finra_ats_dark_pool",
        ticker="XLF",
        params={"limit": 40},
        payload=[],
        path=db_path,
        created_at_utc=datetime(2026, 5, 27, 12, 5, tzinfo=timezone.utc),
    )

    coverage = provider_flow_cache_coverage(
        tickers=["xlk", "XLF"],
        lanes=["massive_block_trades", "finra_ats_dark_pool"],
        path=db_path,
    )
    serialized = json.dumps(coverage)

    assert coverage["state"] == "incomplete"
    assert coverage["expected_pair_count"] == 4
    assert coverage["covered_pair_count"] == 2
    assert coverage["missing_pair_count"] == 2
    assert coverage["coverage_ratio"] == 0.5
    assert coverage["covered_tickers_by_lane"] == {
        "massive_block_trades": 1,
        "finra_ats_dark_pool": 1,
    }
    assert {"lane": "massive_block_trades", "ticker": "XLF"} in coverage["missing_pairs"]
    assert coverage["latest_created_at_utc"] == "2026-05-27T12:05:00Z"
    assert "secret-value" not in serialized
