from __future__ import annotations

import json

from scripts import warm_provider_flow_cache


def test_warm_provider_flow_cache_uses_default_scored_universe_and_secret_safe_summary(monkeypatch, capsys):
    calls = []

    class FakeFlow:
        MASSIVE_TRADES_STUB_MODE = True
        FINRA_ATS_STUB_MODE = True
        FINRA_SHORT_INTEREST_STUB_MODE = True
        SEC_13F_STUB_MODE = True
        ETF_PRIMARY_FLOW_STUB_MODE = True

        @staticmethod
        def _fetch_massive_stock_trades(ticker, *, limit, timeout):
            calls.append(("massive", ticker, limit, timeout))
            return [{"p": 100.0}]

        @staticmethod
        def _fetch_finra_ats_weekly_summary(ticker, *, limit, timeout):
            calls.append(("ats", ticker, limit, timeout))
            return [{"issueSymbolIdentifier": ticker}]

        @staticmethod
        def _fetch_finra_short_interest(ticker, *, timeout):
            calls.append(("short", ticker, None, timeout))
            return [{"symbolCode": ticker}]

    monkeypatch.setattr(warm_provider_flow_cache, "_bootstrap_runtime_config", lambda: None)
    monkeypatch.setattr(warm_provider_flow_cache, "_import_flow_module", lambda: FakeFlow)
    monkeypatch.setattr(
        warm_provider_flow_cache,
        "provider_flow_cache_status",
        lambda: {"state": "ready", "rows": 3},
    )

    exit_code = warm_provider_flow_cache.main(
        [
            "--ticker",
            "xlk",
            "--lane",
            "massive_block_trades",
            "--massive-limit",
            "25",
            "--timeout",
            "7",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert calls == [("massive", "XLK", 25, 7)]
    assert payload["ok"] is True
    assert payload["ticker_count"] == 1
    assert payload["failed"] == 0
    assert payload["cache"] == {"state": "ready", "rows": 3}
    assert "SECRET" not in json.dumps(payload)


def test_warm_provider_flow_cache_continues_after_lane_failure(monkeypatch, capsys):
    class FakeFlow:
        MASSIVE_TRADES_STUB_MODE = True
        FINRA_ATS_STUB_MODE = True
        FINRA_SHORT_INTEREST_STUB_MODE = True
        SEC_13F_STUB_MODE = True
        ETF_PRIMARY_FLOW_STUB_MODE = True

        @staticmethod
        def _fetch_massive_stock_trades(ticker, *, limit, timeout):
            if ticker == "XLK":
                return [{"p": 100.0}]
            raise RuntimeError("Bearer SECRET")

        @staticmethod
        def _fetch_finra_ats_weekly_summary(ticker, *, limit, timeout):
            return []

        @staticmethod
        def _fetch_finra_short_interest(ticker, *, timeout):
            return []

    monkeypatch.setattr(warm_provider_flow_cache, "_bootstrap_runtime_config", lambda: None)
    monkeypatch.setattr(warm_provider_flow_cache, "_import_flow_module", lambda: FakeFlow)
    monkeypatch.setattr(
        warm_provider_flow_cache,
        "provider_flow_cache_status",
        lambda: {"state": "ready", "rows": 1},
    )

    exit_code = warm_provider_flow_cache.main(
        [
            "--ticker",
            "XLK",
            "--ticker",
            "XLF",
            "--lane",
            "massive_block_trades",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    serialized = json.dumps(payload)
    assert exit_code == 1
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1
    assert payload["sample_rows"][1] == {
        "ticker": "XLF",
        "lane": "massive_block_trades",
        "status": "failed",
        "error_type": "RuntimeError",
        "records": 0,
    }
    assert "Bearer" not in serialized
    assert "SECRET" not in serialized


def test_warm_provider_flow_cache_returns_failure_without_tickers(monkeypatch, capsys):
    monkeypatch.setattr(warm_provider_flow_cache, "_tickers_for_universe", lambda name: [])

    exit_code = warm_provider_flow_cache.main([])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload == {"error": "no_tickers", "ok": False}
