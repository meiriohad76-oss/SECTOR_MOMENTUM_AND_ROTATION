from __future__ import annotations

from scripts import export_transition_feeds


def test_export_transition_feeds_script_writes_rss_and_ical(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        export_transition_feeds,
        "recent_transitions",
        lambda n=500: [
            {"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-21"},
            {"ticker": "XLF", "from": "WARNING", "to": "STAGE_2_BULLISH", "date": "2026-05-20"},
        ],
    )

    exit_code = export_transition_feeds.main(["--output-dir", str(tmp_path), "--limit", "200"])

    assert exit_code == 0
    rss_path = tmp_path / "transitions.rss"
    ics_path = tmp_path / "transitions.ics"
    assert rss_path.exists()
    assert ics_path.exists()
    assert "XLK transitioned HOLD -&gt; WARNING" in rss_path.read_text(encoding="utf-8")
    assert "SUMMARY:XLF transitioned WARNING -> STAGE_2_BULLISH" in ics_path.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "transition_feeds=written" in out
    assert "transitions.rss" in out
    assert "transitions.ics" in out


def test_export_transition_feeds_script_can_publish_static_feed_copies(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        export_transition_feeds,
        "recent_transitions",
        lambda n=500: [
            {"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-21"},
        ],
    )
    local_dir = tmp_path / "data" / "feeds"
    publish_dir = tmp_path / "public" / "feeds"

    exit_code = export_transition_feeds.main(
        [
            "--output-dir",
            str(local_dir),
            "--publish-dir",
            str(publish_dir),
            "--public-base-url",
            "https://example.test/feeds/",
        ]
    )

    assert exit_code == 0
    assert (local_dir / "transitions.rss").exists()
    assert (local_dir / "transitions.ics").exists()
    assert (publish_dir / "transitions.rss").exists()
    assert (publish_dir / "transitions.ics").exists()
    assert "<link>https://example.test/feeds/transitions.rss</link>" in (
        publish_dir / "transitions.rss"
    ).read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert f"published_rss={publish_dir / 'transitions.rss'}" in out
    assert f"published_ics={publish_dir / 'transitions.ics'}" in out


def test_transition_feed_publish_docs_keep_generated_static_feeds_ignored():
    root = export_transition_feeds.ROOT
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    deploy_docs = (root / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")

    assert "public/feeds/" in gitignore
    assert "public/feeds/" in dockerignore
    assert "--publish-dir public/feeds" in readme
    assert "public/feeds/transitions.rss" in deploy_docs


def test_backlog_records_transition_feed_pi_artifact_validation_without_public_overclaim():
    root = export_transition_feeds.ROOT
    backlog = (root / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    start = backlog.index("### B-122")
    section = backlog[start:backlog.index("### B-123", start)]

    assert "USER TIMER LIVE VALIDATED / PUBLIC ROUTE PENDING" in section
    assert "items=32" in section
    assert "HTTP `200` alone is not accepted as public feed proof" in section
