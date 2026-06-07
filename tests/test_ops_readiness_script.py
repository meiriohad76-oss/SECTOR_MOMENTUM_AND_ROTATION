from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

from scripts import check_ops_readiness
from src.provider_flow_cache import write_provider_flow_cache
from src.universe import US_SECTORS


REQUIRED_PROVIDER_FLOW_CACHE_LANES = (
    "massive_block_trades",
    "finra_ats_dark_pool",
    "finra_short_interest",
)


def _write_provider_flow_cache_grid(path, *, omit: tuple[str, str] | None = None) -> None:
    for ticker in US_SECTORS:
        for lane in REQUIRED_PROVIDER_FLOW_CACHE_LANES:
            if omit == (lane, ticker):
                continue
            provider = "massive" if lane == "massive_block_trades" else "finra"
            write_provider_flow_cache(
                provider=provider,
                lane=lane,
                ticker=ticker,
                params={"test": lane},
                payload=[{"ticker": ticker, "lane": lane}],
                path=path,
                created_at_utc=datetime(2026, 5, 27, 12, tzinfo=timezone.utc),
            )


def test_ops_readiness_reports_all_pending_integration_tickets_without_secret_values(tmp_path, monkeypatch, capsys):
    subscriptions_path = tmp_path / "subscriptions.json"
    subscriptions_path.write_text(
        json.dumps(
            {
                "subscriptions": [
                    {
                        "endpoint": "https://push.example.test/sub",
                        "keys": {"p256dh": "browser-public", "auth": "browser-auth"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    data_feed_dir = tmp_path / "data" / "feeds"
    public_feed_dir = tmp_path / "public" / "feeds"
    data_feed_dir.mkdir(parents=True)
    public_feed_dir.mkdir(parents=True)
    (data_feed_dir / "transitions.rss").write_text("<rss />", encoding="utf-8")
    (data_feed_dir / "transitions.ics").write_text("BEGIN:VCALENDAR", encoding="utf-8")
    (public_feed_dir / "transitions.rss").write_text("<rss />", encoding="utf-8")
    (public_feed_dir / "transitions.ics").write_text("BEGIN:VCALENDAR", encoding="utf-8")
    state_file = tmp_path / "data" / "state.json"
    transition_journal = tmp_path / "data" / "state_transitions.jsonl"
    run_journal = tmp_path / "data" / "run_journal" / "runs.sqlite"
    provider_snapshots = tmp_path / "data" / "provider_snapshots" / "provider_snapshots.sqlite"
    provider_flow_cache = tmp_path / "data" / "provider_flow_cache" / "provider_flow_cache.sqlite"
    ohlcv_cache = tmp_path / "data_cache" / "ohlcv.duckdb"
    rendered_smoke_json = tmp_path / "data" / "rendered_dashboard_smoke" / "latest.json"
    user_systemd_dir = tmp_path / ".config" / "systemd" / "user"

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state_file.write_text(
        json.dumps(
            {
                "updated": state_updated,
                "by_ticker": {"XLK": {"state": "STAGE_2_BULLISH"}},
                "transitions": [{"ticker": "XLK", "from": "HOLD", "to": "STAGE_2_BULLISH"}],
            }
        ),
        encoding="utf-8",
    )
    transition_journal.write_text(
        json.dumps({"ticker": "XLK", "from": "HOLD", "to": "STAGE_2_BULLISH"}) + "\n",
        encoding="utf-8",
    )
    run_journal.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(run_journal) as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT)")
        conn.execute("INSERT INTO runs VALUES ('run-1')")
    provider_snapshots.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(provider_snapshots) as conn:
        conn.execute("CREATE TABLE provider_snapshots (provider TEXT)")
        conn.execute("INSERT INTO provider_snapshots VALUES ('massive')")
    _write_provider_flow_cache_grid(provider_flow_cache)
    ohlcv_cache.parent.mkdir(parents=True, exist_ok=True)
    ohlcv_cache.write_bytes(b"duckdb-placeholder")
    rendered_smoke_json.parent.mkdir(parents=True, exist_ok=True)
    rendered_smoke_json.write_text(
        json.dumps(
            {
                "ok": True,
                "state": "rendered_dashboard",
                "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "url": "http://127.0.0.1:8501/?ticker=XLK",
                "expected_text": ["text:SENTIMENT BOARD", "text:BLUF"],
            }
        ),
        encoding="utf-8",
    )
    user_systemd_dir.mkdir(parents=True)
    (user_systemd_dir / "sector-massive-provider-snapshots.service").write_text("[Service]\n", encoding="utf-8")
    (user_systemd_dir / "sector-massive-provider-snapshots.timer").write_text("[Timer]\n", encoding="utf-8")
    (user_systemd_dir / "sector-provider-flow-cache.service").write_text("[Service]\n", encoding="utf-8")
    (user_systemd_dir / "sector-provider-flow-cache.timer").write_text("[Timer]\n", encoding="utf-8")
    (user_systemd_dir / "sector-dashboard-state-refresh.service").write_text("[Service]\n", encoding="utf-8")
    (user_systemd_dir / "sector-dashboard-state-refresh.timer").write_text("[Timer]\n", encoding="utf-8")
    (user_systemd_dir / "sector-rendered-dashboard-smoke.service").write_text("[Service]\n", encoding="utf-8")
    (user_systemd_dir / "sector-rendered-dashboard-smoke.timer").write_text("[Timer]\n", encoding="utf-8")

    def fake_config(name: str) -> str | None:
        values = {
            "OHLCV_PROVIDER": "massive",
            "MASSIVE_API_KEY": "massive-live-secret",
            "MASSIVE_VERIFY_SSL": "true",
            "FRED_API_KEY": "fred-live-secret",
            "FLOW_STUB_MODE": "false",
            "MASSIVE_TRADES_STUB_MODE": "false",
            "FINRA_ATS_STUB_MODE": "false",
            "FINRA_SHORT_INTEREST_STUB_MODE": "false",
            "SEC_13F_STUB_MODE": "false",
            "SEC_13F_DATA_URL": "https://sec.example.test/form13f.zip",
            "SEC_USER_AGENT": "ops@example.test",
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "TELEGRAM_CHAT_ID": "123",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.test/secret",
            "SMTP_HOST": "smtp.example.test",
            "EMAIL_DIGEST_TO": "ops@example.test",
            "VAPID_PRIVATE_KEY": "data/vapid_private_key.pem",
            "VAPID_PUBLIC_KEY": "public-key",
            "VAPID_CLAIM_EMAIL": "ops@example.test",
            "DISCORD_WEBHOOK_URL": "https://discord.test/secret",
            "BROKER_PROVIDER": "alpaca",
            "ALPACA_API_KEY_ID": "alpaca-key",
            "ALPACA_API_SECRET_KEY": "alpaca-secret",
        }
        return values.get(name)

    monkeypatch.setattr(check_ops_readiness, "resolve_config_value", fake_config)
    monkeypatch.setattr(
        check_ops_readiness,
        "_systemctl_user",
        lambda args: {
            ("is-enabled", "sector-massive-provider-snapshots.timer"): "enabled",
            ("is-active", "sector-massive-provider-snapshots.timer"): "active",
            ("show", "sector-massive-provider-snapshots.service", "-p", "Result", "--value"): "success",
            ("show", "sector-massive-provider-snapshots.service", "-p", "ExecMainStatus", "--value"): "0",
            ("is-enabled", "sector-provider-flow-cache.timer"): "enabled",
            ("is-active", "sector-provider-flow-cache.timer"): "active",
            ("show", "sector-provider-flow-cache.service", "-p", "Result", "--value"): "success",
            ("show", "sector-provider-flow-cache.service", "-p", "ExecMainStatus", "--value"): "0",
            ("is-enabled", "sector-dashboard-state-refresh.timer"): "enabled",
            ("is-active", "sector-dashboard-state-refresh.timer"): "active",
            ("show", "sector-dashboard-state-refresh.service", "-p", "Result", "--value"): "success",
            ("show", "sector-dashboard-state-refresh.service", "-p", "ExecMainStatus", "--value"): "0",
            ("is-enabled", "sector-rendered-dashboard-smoke.timer"): "enabled",
            ("is-active", "sector-rendered-dashboard-smoke.timer"): "active",
            ("show", "sector-rendered-dashboard-smoke.service", "-p", "Result", "--value"): "success",
            ("show", "sector-rendered-dashboard-smoke.service", "-p", "ExecMainStatus", "--value"): "0",
        }.get(tuple(args)),
    )

    exit_code = check_ops_readiness.main(
        [
            "--subscriptions-path",
            str(subscriptions_path),
            "--feed-dir",
            str(data_feed_dir),
            "--public-feed-dir",
            str(public_feed_dir),
            "--state-file",
            str(state_file),
            "--state-transition-journal",
            str(transition_journal),
            "--run-journal-path",
            str(run_journal),
            "--provider-snapshot-db",
            str(provider_snapshots),
            "--provider-flow-cache-db",
            str(provider_flow_cache),
            "--ohlcv-cache-path",
            str(ohlcv_cache),
            "--rendered-smoke-json",
            str(rendered_smoke_json),
            "--user-systemd-dir",
            str(user_systemd_dir),
            "--strict-production",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    serialized = json.dumps(payload)
    assert exit_code == 0
    assert "production" in payload
    assert payload["production"]["ohlcv_provider"]["state"] == "configured"
    assert payload["production"]["ohlcv_provider"]["massive_api_key"] == "configured"
    assert payload["production"]["ohlcv_provider"]["massive_verify_ssl"] == "configured_true"
    assert payload["production"]["fred"]["api_key"] == "configured"
    assert payload["production"]["provider_flow"]["massive_block_trades"]["state"] == "live_configured"
    assert payload["production"]["provider_flow"]["finra_ats_dark_pool"]["state"] == "live_configured"
    assert payload["production"]["provider_flow"]["finra_short_interest"]["state"] == "live_configured"
    assert payload["production"]["provider_flow"]["sec_13f"]["state"] == "live_configured"
    assert payload["production"]["state_persistence"]["by_ticker_count"] == 1
    assert payload["production"]["state_persistence"]["journal_transition_count"] == 1
    assert payload["production"]["state_persistence"]["freshness_state"] == "fresh"
    assert payload["production"]["state_persistence"]["state_updated_age_seconds"] is not None
    assert payload["production"]["state_persistence"]["refresh_timer"]["state"] == "ready"
    assert payload["production"]["state_persistence"]["refresh_timer"]["timer_enabled"] == "enabled"
    assert payload["production"]["state_persistence"]["refresh_timer"]["timer_active"] == "active"
    assert payload["production"]["run_journal"]["runs"] == 1
    assert payload["production"]["provider_snapshots"]["snapshots"] == 1
    assert payload["production"]["provider_snapshots"]["capture_timer"]["state"] == "ready"
    assert payload["production"]["provider_snapshots"]["capture_timer"]["timer_enabled"] == "enabled"
    assert payload["production"]["provider_snapshots"]["capture_timer"]["timer_active"] == "active"
    assert payload["production"]["provider_flow_cache"]["state"] == "ready"
    assert payload["production"]["provider_flow_cache"]["rows"] == 33
    assert payload["production"]["provider_flow_cache"]["us_sector_coverage"]["state"] == "ready"
    assert payload["production"]["provider_flow_cache"]["us_sector_coverage"]["expected_pair_count"] == 33
    assert payload["production"]["provider_flow_cache"]["us_sector_coverage"]["covered_pair_count"] == 33
    assert payload["production"]["provider_flow_cache"]["us_sector_coverage"]["missing_pair_count"] == 0
    assert payload["production"]["provider_flow_cache"]["warmup_timer"]["state"] == "ready"
    assert payload["production"]["provider_flow_cache"]["warmup_timer"]["timer_enabled"] == "enabled"
    assert payload["production"]["provider_flow_cache"]["warmup_timer"]["timer_active"] == "active"
    assert payload["production"]["ohlcv_cache"]["state"] == "ready"
    assert payload["production"]["browser_qa_fixture_guard"]["state"] == "safe"
    assert payload["production"]["rendered_dashboard_smoke"]["state"] == "ok"
    assert payload["production"]["rendered_dashboard_smoke"]["ok"] is True
    assert payload["production"]["rendered_dashboard_smoke"]["smoke_state"] == "rendered_dashboard"
    assert payload["production"]["rendered_dashboard_smoke"]["expected_text_count"] == 2
    assert payload["production"]["rendered_dashboard_smoke"]["timer"]["state"] == "ready"
    assert payload["strict_production"] == {"enforced": True, "failures": [], "ok": True}
    assert set(payload) >= {"B-021", "B-120", "B-121", "B-122", "B-123", "B-131"}
    assert payload["B-021"]["telegram"] == "configured"
    assert payload["B-120"]["smtp_delivery"] == "configured"
    assert payload["B-121"]["subscriptions"] == 1
    assert payload["B-122"]["public_feed_artifacts"] == "ready"
    assert payload["B-123"]["discord"] == "configured"
    assert payload["B-131"]["broker_config"] == "ready"
    assert "secret" not in serialized
    assert "telegram-token" not in serialized
    assert "massive-live-secret" not in serialized
    assert "fred-live-secret" not in serialized


def test_ops_readiness_strict_mode_fails_when_provider_flow_cache_coverage_is_incomplete(
    tmp_path, monkeypatch, capsys
):
    provider_flow_cache = tmp_path / "provider_flow_cache.sqlite"
    _write_provider_flow_cache_grid(provider_flow_cache, omit=("finra_short_interest", "XLK"))
    monkeypatch.setattr(check_ops_readiness, "_systemctl_user", lambda args: None)

    exit_code = check_ops_readiness.main(
        [
            "--provider-flow-cache-db",
            str(provider_flow_cache),
            "--strict-production",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    coverage = payload["production"]["provider_flow_cache"]["us_sector_coverage"]
    assert exit_code == 2
    assert coverage["state"] == "incomplete"
    assert coverage["expected_pair_count"] == 33
    assert coverage["covered_pair_count"] == 32
    assert coverage["missing_pair_count"] == 1
    assert {"lane": "finra_short_interest", "ticker": "XLK"} in coverage["missing_pairs"]
    assert any(
        row["id"] == "provider_flow_cache.us_sector_coverage"
        for row in payload["strict_production"]["failures"]
    )


def test_ops_readiness_flags_browser_qa_fixtures_as_unsafe(monkeypatch, capsys):
    def fake_config(name: str) -> str | None:
        if name == "BROWSER_QA_ALLOW_FIXTURES":
            return "true"
        return None

    monkeypatch.setattr(check_ops_readiness, "resolve_config_value", fake_config)

    exit_code = check_ops_readiness.main([])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["production"]["browser_qa_fixture_guard"] == {
        "state": "unsafe_enabled",
        "flag": "configured",
    }
    assert payload["strict_production"]["ok"] is False
    assert any(row["id"] == "browser_qa_fixture_guard" for row in payload["strict_production"]["failures"])


def test_ops_readiness_strict_mode_fails_on_stale_state(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    journal = tmp_path / "state_transitions.jsonl"
    state_file.write_text(
        json.dumps(
            {
                "updated": "2020-01-01T00:00:00Z",
                "by_ticker": {"XLK": {"state": "HOLD"}},
                "transitions": [],
            }
        ),
        encoding="utf-8",
    )
    journal.write_text("", encoding="utf-8")
    monkeypatch.setattr(check_ops_readiness, "_systemctl_user", lambda args: None)

    exit_code = check_ops_readiness.main(
        [
            "--state-file",
            str(state_file),
            "--state-transition-journal",
            str(journal),
            "--strict-production",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["production"]["state_persistence"]["freshness_state"] == "stale"
    assert payload["strict_production"]["enforced"] is True
    assert payload["strict_production"]["ok"] is False
    assert any(row["id"] == "state_freshness" for row in payload["strict_production"]["failures"])


def test_ops_readiness_marks_missing_massive_snapshot_timer(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_ops_readiness, "_systemctl_user", lambda args: None)

    exit_code = check_ops_readiness.main(["--user-systemd-dir", str(tmp_path / "missing-user-units")])

    payload = json.loads(capsys.readouterr().out)
    timer = payload["production"]["provider_snapshots"]["capture_timer"]
    assert exit_code == 0
    assert timer["state"] == "missing"
    assert timer["service_installed"] is False
    assert timer["timer_installed"] is False


def test_ops_readiness_docs_reference_single_command():
    root = check_ops_readiness.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "scripts/check_ops_readiness.py" in readme
    assert "scripts/check_ops_readiness.py" in backlog
