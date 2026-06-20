from __future__ import annotations

from pathlib import Path

from scripts import restart_sector_dashboard


ROOT = Path(__file__).resolve().parent.parent


def test_pi_restart_script_uses_non_interactive_mainpid_restart():
    script = (ROOT / "scripts" / "restart_sector_dashboard.py").read_text(encoding="utf-8")

    assert "systemctl" in script
    assert "MainPID" in script
    assert "os.kill" in script
    assert "signal.SIGTERM" in script
    assert 'getattr(signal, "SIGKILL", signal.SIGTERM)' in script
    assert "urllib.request.urlopen" in script
    assert "classify_local_dashboard_response" in script
    assert "sudo" not in script.lower()
    assert "restart_result=healthy" in script


def test_pi_restart_docs_reference_noninteractive_helper_and_cloudflare_access_qa():
    deploy_docs = (ROOT / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "scripts/restart_sector_dashboard.py" in deploy_docs
    assert "non-interactive" in deploy_docs
    assert "Cloudflare Access" in readme
    assert "--base-url https://sentimentdashboard.ahaddashboards.uk" in readme


def test_restart_helper_fails_closed_when_initial_mainpid_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(restart_sector_dashboard, "_main_pid", lambda service, user_service=False: 0)

    exit_code = restart_sector_dashboard.restart_and_wait(
        "sector-dashboard",
        "http://127.0.0.1:8501/?ticker=XLK",
        timeout_seconds=5,
        poll_seconds=0,
    )

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "restart_result=failed_no_mainpid" in captured


def test_restart_helper_tolerates_pid_race_when_fresh_pid_becomes_healthy(monkeypatch, capsys):
    pids = iter([123, 124])
    monkeypatch.setattr(restart_sector_dashboard, "_main_pid", lambda service, user_service=False: next(pids, 124))
    monkeypatch.setattr(restart_sector_dashboard, "_active", lambda service, user_service=False: "active")
    monkeypatch.setattr(
        restart_sector_dashboard,
        "_http_probe",
        lambda url, timeout: (200, "SENTIMENT BOARD BLUF Data and dashboard health"),
    )

    def already_exited(pid, sig):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(restart_sector_dashboard.os, "kill", already_exited)

    exit_code = restart_sector_dashboard.restart_and_wait(
        "sector-dashboard",
        "http://127.0.0.1:8501/?ticker=XLK",
        timeout_seconds=5,
        poll_seconds=0,
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "restart_action=mainpid_already_exited" in captured
    assert "restart_result=healthy" in captured


def test_restart_helper_rejects_http_200_with_wrong_content(monkeypatch, capsys):
    pids = iter([123, 124, 124])
    monkeypatch.setattr(restart_sector_dashboard, "_main_pid", lambda service, user_service=False: next(pids, 124))
    monkeypatch.setattr(restart_sector_dashboard, "_active", lambda service, user_service=False: "active")
    monkeypatch.setattr(restart_sector_dashboard.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(
        restart_sector_dashboard,
        "_http_probe",
        lambda url, timeout: (200, "Welcome"),
    )

    exit_code = restart_sector_dashboard.restart_and_wait(
        "sector-dashboard",
        "http://127.0.0.1:8501/?ticker=XLK",
        timeout_seconds=1,
        poll_seconds=0,
    )

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "content=wrong_content" in captured


def test_restart_helper_escalates_wedged_old_pid_with_dead_http(monkeypatch, capsys):
    pids = iter([123, 123, 123, 123, 123, 123, 124])
    probes = iter(
        [
            (0, ""),
            (0, ""),
            (0, ""),
            (0, ""),
            (0, ""),
            (200, "SENTIMENT BOARD BLUF Data and dashboard health"),
        ]
    )
    kills: list[tuple[int, int]] = []

    monkeypatch.setattr(restart_sector_dashboard, "_main_pid", lambda service, user_service=False: next(pids, 124))
    monkeypatch.setattr(restart_sector_dashboard, "_active", lambda service, user_service=False: "active")
    monkeypatch.setattr(restart_sector_dashboard, "_http_probe", lambda url, timeout: next(probes))

    def record_kill(pid, sig):
        kills.append((pid, sig))

    monkeypatch.setattr(restart_sector_dashboard.os, "kill", record_kill)

    exit_code = restart_sector_dashboard.restart_and_wait(
        "sector-dashboard",
        "http://127.0.0.1:8501/?ticker=XLK",
        timeout_seconds=5,
        poll_seconds=0,
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert kills == [
        (123, restart_sector_dashboard.signal.SIGTERM),
        (123, restart_sector_dashboard.SIGKILL),
    ]
    assert "restart_action=sent_sigkill" in captured
    assert "restart_result=healthy" in captured
