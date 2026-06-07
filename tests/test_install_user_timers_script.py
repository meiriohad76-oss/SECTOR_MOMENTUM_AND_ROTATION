from __future__ import annotations

import json
from pathlib import Path

from scripts import install_user_timers


def test_install_user_timers_copies_units_rewrites_repo_path_and_enables(monkeypatch, tmp_path, capsys):
    calls: list[list[str]] = []

    def fake_systemctl(args: list[str]) -> tuple[int, str]:
        calls.append(args)
        if args == ["is-enabled", "sector-massive-provider-snapshots.timer"]:
            return 0, "enabled"
        if args == ["is-active", "sector-massive-provider-snapshots.timer"]:
            return 0, "active"
        if args[:2] == ["show", "sector-massive-provider-snapshots.service"]:
            return 0, "success" if args[3] == "Result" else "0"
        return 0, ""

    monkeypatch.setattr(install_user_timers, "_run_systemctl", fake_systemctl)
    user_dir = tmp_path / "user-units"
    repo_root = tmp_path / "custom-checkout"

    exit_code = install_user_timers.main(
        [
            "--timer",
            "sector-massive-provider-snapshots.timer",
            "--repo-root",
            str(repo_root),
            "--user-systemd-dir",
            str(user_dir),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    service_text = (user_dir / "sector-massive-provider-snapshots.service").read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["timers"][0]["ok"] is True
    assert payload["timers"][0]["enabled"] == "enabled"
    assert payload["timers"][0]["active"] == "active"
    assert str(repo_root.resolve()) in service_text
    assert "%h/SECTOR_MOMENTUM_AND_ROTATION" not in service_text
    assert ["daemon-reload"] in calls
    assert ["enable", "--now", "sector-massive-provider-snapshots.timer"] in calls


def test_install_user_timers_defaults_to_operational_non_secret_timers(monkeypatch, tmp_path, capsys):
    def fake_systemctl(args: list[str]) -> tuple[int, str]:
        if args[0] == "is-enabled":
            return 0, "enabled"
        if args[0] == "is-active":
            return 0, "active"
        if args[0] == "show":
            return 0, "0"
        return 0, ""

    monkeypatch.setattr(install_user_timers, "_run_systemctl", fake_systemctl)

    exit_code = install_user_timers.main(
        [
            "--repo-root",
            str(tmp_path / "repo"),
            "--user-systemd-dir",
            str(tmp_path / "user-units"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    timers = {row["timer"] for row in payload["timers"]}
    assert exit_code == 0
    assert timers == {
        "sector-transition-feeds.timer",
        "sector-massive-provider-snapshots.timer",
    }
    assert "sector-email-digest.timer" not in timers


def test_install_user_timers_reports_missing_source_without_systemctl(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(install_user_timers, "_run_systemctl", lambda args: calls.append(args) or (0, ""))

    exit_code = install_user_timers.main(
        [
            "--timer",
            "missing.timer",
            "--user-systemd-dir",
            str(tmp_path / "user-units"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["timers"][0]["ok"] is False
    assert {row["error"] for row in payload["timers"][0]["units"]} == {"source_missing"}
    assert calls == []


def test_install_user_timers_dry_run_does_not_copy_or_call_systemctl(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(install_user_timers, "_run_systemctl", lambda args: calls.append(args) or (0, ""))
    user_dir = tmp_path / "user-units"

    exit_code = install_user_timers.main(
        [
            "--timer",
            "sector-transition-feeds.timer",
            "--user-systemd-dir",
            str(user_dir),
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["timers"][0]["ok"] is True
    assert not user_dir.exists()
    assert calls == []
