from __future__ import annotations

import json

from scripts import refresh_dashboard_state
from src import scoring
from src.data import OhlcvFetchResult
from src.run_journal import list_runs


def test_refresh_dashboard_state_writes_state_and_run_journal(
    monkeypatch,
    tmp_path,
    ohlcv_frame_factory,
):
    state_file = tmp_path / "state.json"
    journal_path = tmp_path / "run_journal.sqlite"
    market = {
        "XLK": ohlcv_frame_factory(start_price=100, daily_return=0.0014),
        "XLF": ohlcv_frame_factory(start_price=80, daily_return=0.0007),
        "SPY": ohlcv_frame_factory(start_price=100, daily_return=0.0010),
        "BIL": ohlcv_frame_factory(start_price=90, daily_return=0.0001),
        "^TNX": ohlcv_frame_factory(start_price=40, daily_return=0.0002),
        "^IRX": ohlcv_frame_factory(start_price=35, daily_return=0.0001),
    }

    monkeypatch.setattr(refresh_dashboard_state, "DATA_SYMBOLS", list(market))
    monkeypatch.setattr(
        refresh_dashboard_state,
        "fetch_ohlcv_result",
        lambda tickers, period, force_refresh=False: OhlcvFetchResult(
            {ticker: market[ticker] for ticker in tickers if ticker in market},
            provider="massive",
        ),
    )
    monkeypatch.setattr(refresh_dashboard_state, "fred_available", lambda: False)
    monkeypatch.setattr(refresh_dashboard_state, "_current_git_sha", lambda: "abc123")
    monkeypatch.setattr(refresh_dashboard_state, "_bootstrap_runtime_config", lambda: None)
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    monkeypatch.setattr(scoring, "STATE_TRANSITION_JOURNAL", None)
    monkeypatch.setattr(scoring, "_STATE_FILE_EXPLICIT", True)
    monkeypatch.setattr(scoring, "_send_transition_alerts", lambda transitions: None)

    payload = refresh_dashboard_state.refresh_dashboard_state(
        period="3y",
        force_refresh=False,
        provider_flow_mode="stubbed",
        allow_stale_provider_cache=False,
        journal_path=journal_path,
        dedupe_journal=True,
    )

    state_payload = json.loads(state_file.read_text(encoding="utf-8"))
    runs = list_runs(journal_path)
    assert payload["ok"] is True
    assert payload["provider"] == "massive"
    assert payload["ticker_count"] >= 2
    assert payload["state_storage"]["state_file_exists"] is True
    assert payload["state_storage"]["freshness_state"] == "fresh"
    assert "XLK" in state_payload["by_ticker"]
    assert state_payload["updated"]
    assert len(runs) == 1
    assert runs[0]["provider"] == "massive"
    assert runs[0]["metadata"]["headless"] is True


def test_refresh_dashboard_state_main_is_secret_safe_on_failure(monkeypatch, capsys):
    def fail_refresh(**kwargs):
        raise RuntimeError("Bearer SECRET MASSIVE_API_KEY")

    monkeypatch.setattr(refresh_dashboard_state, "refresh_dashboard_state", fail_refresh)

    exit_code = refresh_dashboard_state.main([])

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 2
    assert payload == {"error": "RuntimeError", "ok": False}
    assert "SECRET" not in output
    assert "MASSIVE_API_KEY" not in output
