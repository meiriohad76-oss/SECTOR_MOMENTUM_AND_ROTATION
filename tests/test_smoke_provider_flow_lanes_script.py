from __future__ import annotations

import json

from scripts import smoke_provider_flow_lanes


def test_provider_flow_smoke_checks_massive_and_finra_without_secret_output(monkeypatch, capsys):
    monkeypatch.setattr(smoke_provider_flow_lanes, "resolve_config_value", lambda name, root=None: "MASSIVE_SECRET")
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_massive_stock_trades",
        lambda ticker, limit=25, timeout=20: [{"p": 100.0}],
    )
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_finra_ats_weekly_summary",
        lambda ticker, limit=25, timeout=20: [{"ats": ticker}],
    )
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_finra_short_interest",
        lambda ticker, limit=4, timeout=20: [],
    )

    exit_code = smoke_provider_flow_lanes.main(["--ticker", "spy", "--limit", "25"])

    output = capsys.readouterr().out
    payload = json.loads(output)
    statuses = {(row["lane"], row["status"], row.get("records")) for row in payload["rows"]}
    assert exit_code == 0
    assert payload["ok"] is True
    assert ("massive_block_trades", "ok", 1) in statuses
    assert ("finra_ats_dark_pool", "ok", 1) in statuses
    assert ("finra_short_interest", "ok", 0) in statuses
    assert "MASSIVE_SECRET" not in output


def test_provider_flow_smoke_skips_missing_massive_key_by_default(monkeypatch):
    monkeypatch.setattr(smoke_provider_flow_lanes, "resolve_config_value", lambda name, root=None: None)
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_finra_ats_weekly_summary",
        lambda ticker, limit=25, timeout=20: [],
    )
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_finra_short_interest",
        lambda ticker, limit=4, timeout=20: [],
    )

    payload = smoke_provider_flow_lanes.smoke_provider_flow_lanes(["SPY"], timeout=1, limit=1)

    massive = [row for row in payload["rows"] if row["lane"] == "massive_block_trades"][0]
    assert payload["ok"] is True
    assert massive["status"] == "skipped_missing_config"


def test_provider_flow_smoke_can_require_massive_key(monkeypatch):
    monkeypatch.setattr(smoke_provider_flow_lanes, "resolve_config_value", lambda name, root=None: None)
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_finra_ats_weekly_summary",
        lambda ticker, limit=25, timeout=20: [],
    )
    monkeypatch.setattr(
        smoke_provider_flow_lanes.flow,
        "_fetch_finra_short_interest",
        lambda ticker, limit=4, timeout=20: [],
    )

    payload = smoke_provider_flow_lanes.smoke_provider_flow_lanes(
        ["SPY"],
        timeout=1,
        limit=1,
        require_massive=True,
    )

    assert payload["ok"] is False
    assert payload["missing_required"] == 1


def test_provider_flow_smoke_sanitizes_failures(monkeypatch, capsys):
    monkeypatch.setattr(smoke_provider_flow_lanes, "resolve_config_value", lambda name, root=None: "SECRET")

    def fail(*args, **kwargs):
        raise RuntimeError("Bearer SECRET")

    monkeypatch.setattr(smoke_provider_flow_lanes.flow, "_fetch_massive_stock_trades", fail)
    monkeypatch.setattr(smoke_provider_flow_lanes.flow, "_fetch_finra_ats_weekly_summary", lambda *a, **k: [])
    monkeypatch.setattr(smoke_provider_flow_lanes.flow, "_fetch_finra_short_interest", lambda *a, **k: [])

    exit_code = smoke_provider_flow_lanes.main(["--ticker", "SPY"])

    output = capsys.readouterr().out
    payload = json.loads(output)
    failed = [row for row in payload["rows"] if row["status"] == "failed"]
    assert exit_code == 2
    assert failed == [
        {
            "lane": "massive_block_trades",
            "provider": "Massive",
            "ticker": "SPY",
            "status": "failed",
            "error_type": "RuntimeError",
        }
    ]
    assert "Bearer" not in output
    assert "SECRET" not in output
