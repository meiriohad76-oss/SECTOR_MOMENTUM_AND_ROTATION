from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from scripts import smoke_deploy_gate


def test_deploy_gate_passes_local_state_and_cloudflare_access(tmp_path, capsys, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "by_ticker": {f"T{i:02d}": {"state": "HOLD"} for i in range(83)},
            }
        ),
        encoding="utf-8",
    )

    def fake_fetch(url: str, timeout: float):
        if "127.0.0.1" in url:
            return 200, {}, "SENTIMENT BOARD BLUF Data and dashboard health"
        return 302, {"Location": "https://team.cloudflareaccess.com/cdn-cgi/access/login"}, ""

    monkeypatch.setattr(smoke_deploy_gate, "_fetch", fake_fetch)

    exit_code = smoke_deploy_gate.main(
        [
            "--public-dashboard-url",
            "https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK",
            "--expect-cloudflare-access",
            "--require-local-dashboard-markers",
            "--state-file",
            str(state_file),
            "--min-state-tickers",
            "80",
            "--max-state-age-seconds",
            "300",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "local_dashboard_smoke ok=true state=dashboard_content" in output
    assert "dashboard_state_smoke ok=true state=fresh_state" in output
    assert "public_dashboard_smoke ok=true state=cloudflare_access_challenge" in output


def test_deploy_gate_fails_wrong_local_content(capsys, monkeypatch):
    monkeypatch.setattr(smoke_deploy_gate, "_fetch", lambda url, timeout: (200, {}, "Welcome"))

    exit_code = smoke_deploy_gate.main(["--local-dashboard-url", "http://127.0.0.1:8501/?ticker=XLK"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "local_dashboard_smoke ok=false state=wrong_content" in output


def test_deploy_gate_passes_fresh_populated_state_file(tmp_path, capsys, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "by_ticker": {f"T{i:02d}": {"state": "HOLD"} for i in range(83)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(smoke_deploy_gate, "_fetch", lambda url, timeout: (200, {}, "Welcome"))

    exit_code = smoke_deploy_gate.main(
        [
            "--local-dashboard-url",
            "http://127.0.0.1:8501/?ticker=XLK",
            "--state-file",
            str(state_file),
            "--min-state-tickers",
            "80",
            "--max-state-age-seconds",
            "300",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "local_dashboard_smoke ok=false state=wrong_content" in output
    assert "dashboard_state_smoke ok=true state=fresh_state" in output
    assert "tickers=83" in output


def test_deploy_gate_fails_stale_or_thin_state_file(tmp_path, capsys, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                "by_ticker": {"XLK": {"state": "HOLD"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        smoke_deploy_gate,
        "_fetch",
        lambda url, timeout: (200, {}, "SENTIMENT BOARD BLUF Data and dashboard health"),
    )

    exit_code = smoke_deploy_gate.main(
        [
            "--state-file",
            str(state_file),
            "--min-state-tickers",
            "80",
            "--max-state-age-seconds",
            "300",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "dashboard_state_smoke ok=false state=thin_state" in output


def test_deploy_gate_strict_local_mode_rejects_shell_only_response(capsys, monkeypatch):
    monkeypatch.setattr(
        smoke_deploy_gate,
        "_fetch",
        lambda url, timeout: (
            200,
            {},
            "<html><head><title>Streamlit</title></head><script src='./static/js/index.js'></script></html>",
        ),
    )

    exit_code = smoke_deploy_gate.main(
        [
            "--local-dashboard-url",
            "http://127.0.0.1:8501/?ticker=XLK",
            "--require-local-dashboard-markers",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "local_dashboard_smoke ok=false state=missing_dashboard_markers" in output


def test_deploy_gate_fails_when_public_route_is_authenticated_but_access_expected(capsys, monkeypatch):
    def fake_fetch(url: str, timeout: float):
        if "127.0.0.1" in url:
            return 200, {}, "SENTIMENT BOARD BLUF Data and dashboard health"
        return 200, {}, "SENTIMENT BOARD BLUF Data and dashboard health"

    monkeypatch.setattr(smoke_deploy_gate, "_fetch", fake_fetch)

    exit_code = smoke_deploy_gate.main(
        [
            "--public-dashboard-url",
            "https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK",
            "--expect-cloudflare-access",
            "--require-local-dashboard-markers",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "state=authenticated_dashboard" in output
    assert "expected=cloudflare_access_challenge" in output
