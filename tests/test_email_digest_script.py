from __future__ import annotations

import subprocess
import sys

from scripts import send_email_digest


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


def test_email_digest_script_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/send_email_digest.py"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "email_digest=" in result.stdout
