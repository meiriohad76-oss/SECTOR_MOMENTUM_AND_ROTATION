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
