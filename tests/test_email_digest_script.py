from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import send_email_digest


ROOT = Path(__file__).resolve().parent.parent


def test_email_digest_script_sends_chronological_recent_transitions(monkeypatch, capsys):
    sent = []

    monkeypatch.setattr(
        send_email_digest,
        "recent_transitions",
        lambda n=500: [
            {"ticker": "XLF", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"},
            {"ticker": "XLK", "from": "HOLD", "to": "STAGE_2_BULLISH", "date": "2026-05-20"},
        ],
    )

    def fake_send(transitions):
        sent.extend(transitions)
        return True

    monkeypatch.setattr(send_email_digest, "send_low_severity_email_digest", fake_send)

    exit_code = send_email_digest.main()

    assert exit_code == 0
    assert [row["ticker"] for row in sent] == ["XLK", "XLF"]
    assert "email_digest=sent" in capsys.readouterr().out


def test_email_digest_script_dry_run_reports_eligible_count_without_sending(monkeypatch, capsys):
    monkeypatch.setattr(
        send_email_digest,
        "recent_transitions",
        lambda n=500: [
            {"ticker": "XLK", "from": "HOLD", "to": "STAGE_2_BULLISH", "date": "2026-05-21"},
            {"ticker": "XLF", "from": "HOLD", "to": "EXIT", "date": "2026-05-21"},
        ],
    )

    def fail_send(_transitions):
        raise AssertionError("dry-run must not send email")

    monkeypatch.setattr(send_email_digest, "send_low_severity_email_digest", fail_send)

    exit_code = send_email_digest.main(["--dry-run", "--digest-date", "2026-05-21"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "email_digest=dry_run" in output
    assert "recent_transitions=2" in output
    assert "eligible_transitions=1" in output


def test_email_digest_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/send_email_digest.py"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "email_digest=" in result.stdout


def test_email_digest_script_avoids_heavy_scoring_import():
    script_source = (ROOT / "scripts" / "send_email_digest.py").read_text(encoding="utf-8")

    assert "from src.scoring import recent_transitions" not in script_source
    assert "def recent_transitions" in script_source


def test_email_digest_systemd_templates_schedule_daily_0800_et():
    service = (ROOT / "systemd" / "sector-email-digest.service").read_text(encoding="utf-8")
    timer = (ROOT / "systemd" / "sector-email-digest.timer").read_text(encoding="utf-8")
    deploy_docs = (ROOT / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")

    assert "Description=Sector Rotation Email Digest" in service
    assert "WorkingDirectory=/home/meiri/sector-rotation-dashboard" in service
    assert "/home/meiri/sector-rotation-dashboard/.venv/bin/python scripts/send_email_digest.py" in service
    assert "Environment=PYTHONUNBUFFERED=1" in service
    assert "OnCalendar=*-*-* 08:00:00 America/New_York" in timer
    assert "Persistent=true" in timer
    assert "sector-email-digest.timer" in deploy_docs
    assert "scripts/send_email_digest.py --dry-run" in deploy_docs
