from __future__ import annotations

from scripts import smoke_deploy_gate


def test_deploy_gate_passes_local_dashboard_and_cloudflare_access(capsys, monkeypatch):
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
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "local_dashboard_smoke ok=true state=dashboard_content" in output
    assert "public_dashboard_smoke ok=true state=cloudflare_access_challenge" in output


def test_deploy_gate_fails_wrong_local_content(capsys, monkeypatch):
    monkeypatch.setattr(smoke_deploy_gate, "_fetch", lambda url, timeout: (200, {}, "Welcome"))

    exit_code = smoke_deploy_gate.main(["--local-dashboard-url", "http://127.0.0.1:8501/?ticker=XLK"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "local_dashboard_smoke ok=false state=wrong_content" in output


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
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "state=authenticated_dashboard" in output
    assert "expected=cloudflare_access_challenge" in output
