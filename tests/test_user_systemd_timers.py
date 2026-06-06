from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
USER_SYSTEMD = ROOT / "systemd" / "user"


def _read_unit(name: str) -> str:
    return (USER_SYSTEMD / name).read_text(encoding="utf-8")


def test_user_email_digest_timer_runs_without_sudo_from_repo_checkout():
    service = _read_unit("sector-email-digest.service")
    timer = _read_unit("sector-email-digest.timer")

    assert "WorkingDirectory=%h/SECTOR_MOMENTUM_AND_ROTATION" in service
    assert "ExecStart=%h/SECTOR_MOMENTUM_AND_ROTATION/.venv/bin/python scripts/send_email_digest.py" in service
    assert "User=" not in service
    assert "OnCalendar=*-*-* 08:00:00 America/New_York" in timer
    assert "Persistent=true" in timer


def test_user_transition_feed_timer_publishes_static_feed_copies():
    service = _read_unit("sector-transition-feeds.service")
    timer = _read_unit("sector-transition-feeds.timer")
    deploy_docs = (ROOT / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")

    assert "WorkingDirectory=%h/SECTOR_MOMENTUM_AND_ROTATION" in service
    assert "scripts/export_transition_feeds.py" in service
    assert "--publish-dir public/feeds" in service
    assert "--public-base-url https://www.ahaddashboards.uk/feeds/" in service
    assert "OnCalendar=*:0/15" in timer
    assert "Persistent=true" in timer
    assert "systemctl --user enable --now sector-transition-feeds.timer" in deploy_docs


def test_user_massive_provider_snapshot_timer_runs_without_sudo_after_market_close():
    service = _read_unit("sector-massive-provider-snapshots.service")
    timer = _read_unit("sector-massive-provider-snapshots.timer")
    deploy_docs = (ROOT / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "WorkingDirectory=%h/SECTOR_MOMENTUM_AND_ROTATION" in service
    assert "scripts/capture_massive_provider_snapshots.py --universe scored" in service
    assert "--limit 5000" in service
    assert "User=" not in service
    assert "OnCalendar=Mon..Fri *-*-* 18:45:00 America/New_York" in timer
    assert "Persistent=true" in timer
    assert "systemctl --user enable --now sector-massive-provider-snapshots.timer" in deploy_docs
    assert "systemd/user/sector-massive-provider-snapshots.service" in backlog


def test_backlog_references_non_sudo_user_timers():
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "systemd/user/sector-email-digest.service" in backlog
    assert "systemd/user/sector-transition-feeds.service" in backlog
    assert "systemd/user/sector-massive-provider-snapshots.service" in backlog
    assert "non-sudo user timer" in backlog


def test_backlog_records_user_timer_live_validation_evidence():
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    email_start = backlog.index("### B-120")
    email_section = backlog[email_start:backlog.index("### B-122", email_start)]
    feed_start = backlog.index("### B-122")
    feed_section = backlog[feed_start:backlog.index("### B-123", feed_start)]

    assert "USER TIMER LIVE VALIDATED / SMTP CONFIG PENDING" in email_section
    assert "sector-email-digest.timer" in email_section
    assert "email_digest=skipped" in email_section
    assert "USER TIMER + EXTERNAL PUBLIC FEEDS LIVE VALIDATED" in feed_section
    assert "sector-transition-feeds.timer" in feed_section
    assert "items=32" in feed_section
    assert "www.ahaddashboards.uk" in feed_section
