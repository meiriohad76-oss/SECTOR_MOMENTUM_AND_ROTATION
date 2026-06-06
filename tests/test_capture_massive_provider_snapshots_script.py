from __future__ import annotations

from scripts import capture_massive_provider_snapshots
from src import provider_snapshots


def test_fetch_massive_trades_for_snapshot_limits_query_to_as_of_day(monkeypatch):
    calls = []

    def fake_fetch(ticker, *, start_date=None, end_date=None, limit=5_000, timeout=20):
        calls.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "timeout": timeout,
            }
        )
        return []

    monkeypatch.setattr(capture_massive_provider_snapshots.flow, "_fetch_massive_stock_trades", fake_fetch)

    assert (
        capture_massive_provider_snapshots._fetch_massive_trades_for_snapshot(
            "XLK",
            as_of="2026-05-19",
            limit=25,
            timeout=7,
        )
        == []
    )

    assert calls == [
        {
            "ticker": "XLK",
            "start_date": "2026-05-19",
            "end_date": "2026-05-20",
            "limit": 25,
            "timeout": 7,
        }
    ]


def test_capture_massive_provider_snapshots_stores_trade_payloads(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "provider_snapshots.sqlite"
    calls = []

    def fake_fetch(ticker, *, as_of, limit, timeout):
        calls.append({"ticker": ticker, "as_of": as_of, "limit": limit, "timeout": timeout})
        return [{"p": 100.0, "s": 100, "sip_timestamp": 1}]

    monkeypatch.setattr(
        capture_massive_provider_snapshots,
        "_fetch_massive_trades_for_snapshot",
        fake_fetch,
    )
    monkeypatch.setattr(capture_massive_provider_snapshots, "_bootstrap_massive_secret", lambda: True)

    assert (
        capture_massive_provider_snapshots.main(
            [
                "--ticker",
                "xlk",
                "--ticker",
                "xlf",
                "--as-of",
                "2026-05-19",
                "--db-path",
                str(db_path),
                "--limit",
                "25",
                "--timeout",
                "7",
            ]
        )
        == 0
    )

    xlk = provider_snapshots.load_provider_snapshot_as_of(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-19",
    )
    xlf = provider_snapshots.load_provider_snapshot_as_of(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLF",
        as_of="2026-05-19",
    )
    output = capsys.readouterr().out

    assert calls == [
        {"ticker": "XLK", "as_of": "2026-05-19", "limit": 25, "timeout": 7},
        {"ticker": "XLF", "as_of": "2026-05-19", "limit": 25, "timeout": 7},
    ]
    assert xlk is not None
    assert xlk.payload["trades"] == [{"p": 100.0, "s": 100, "sip_timestamp": 1}]
    assert xlk.payload["source"] == "massive/v3/trades"
    assert xlk.payload["request"] == {
        "endpoint": "https://api.massive.com/v3/trades/{ticker}",
        "ticker": "XLK",
        "params": {
            "limit": 25,
            "order": "desc",
            "sort": "timestamp",
            "timestamp.gte": "2026-05-19",
            "timestamp.lt": "2026-05-20",
        },
    }
    assert xlk.payload["response"] == {
        "result_count": 1,
        "status": "captured",
    }
    assert xlf is not None
    assert "Saved massive stock_trades snapshot for XLK as_of=2026-05-19 trades=1" in output
    assert "Bearer" not in output
    assert "MASSIVE_API_KEY" not in output


def test_capture_massive_provider_snapshots_sanitizes_failure_output(monkeypatch, tmp_path, capsys):
    def fail_fetch(ticker, *, as_of, limit, timeout):
        raise RuntimeError(
            "request failed headers={'Authorization': 'Bearer SECRET'} env=MASSIVE_API_KEY"
        )

    monkeypatch.setattr(
        capture_massive_provider_snapshots,
        "_fetch_massive_trades_for_snapshot",
        fail_fetch,
    )
    monkeypatch.setattr(capture_massive_provider_snapshots, "_bootstrap_massive_secret", lambda: True)

    assert (
        capture_massive_provider_snapshots.main(
            [
                "--ticker",
                "XLK",
                "--as-of",
                "2026-05-19",
                "--db-path",
                str(tmp_path / "provider_snapshots.sqlite"),
            ]
        )
        == 2
    )

    output = capsys.readouterr().out
    assert "Massive provider snapshot capture failed." in output
    assert "Bearer" not in output
    assert "SECRET" not in output
    assert "MASSIVE_API_KEY" not in output


def test_capture_massive_provider_snapshots_supports_scored_universe(monkeypatch, tmp_path):
    tickers = []

    def fake_fetch(ticker, *, as_of, limit, timeout):
        tickers.append(ticker)
        return [{"p": 100.0, "s": 100, "sip_timestamp": 1}]

    monkeypatch.setattr(
        capture_massive_provider_snapshots,
        "_fetch_massive_trades_for_snapshot",
        fake_fetch,
    )
    monkeypatch.setattr(capture_massive_provider_snapshots, "_bootstrap_massive_secret", lambda: True)

    assert (
        capture_massive_provider_snapshots.main(
            [
                "--universe",
                "scored",
                "--as-of",
                "2026-05-19",
                "--db-path",
                str(tmp_path / "provider_snapshots.sqlite"),
                "--limit",
                "25",
            ]
        )
        == 0
    )

    assert "XLK" in tickers
    assert "NVDA" in tickers
    assert "TLT" in tickers
    assert "SPY" not in tickers


def test_capture_massive_provider_snapshots_does_not_write_without_massive_key(monkeypatch, tmp_path, capsys):
    called = False

    def fake_fetch(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(
        capture_massive_provider_snapshots,
        "_fetch_massive_trades_for_snapshot",
        fake_fetch,
    )
    monkeypatch.setattr(capture_massive_provider_snapshots, "_bootstrap_massive_secret", lambda: False)

    assert (
        capture_massive_provider_snapshots.main(
            [
                "--ticker",
                "XLK",
                "--as-of",
                "2026-05-19",
                "--db-path",
                str(tmp_path / "provider_snapshots.sqlite"),
            ]
        )
        == 2
    )

    output = capsys.readouterr().out
    assert called is False
    assert "MASSIVE_API_KEY is not configured" in output
    assert not (tmp_path / "provider_snapshots.sqlite").exists()
