from __future__ import annotations

from datetime import datetime, timezone

from src.transition_feeds import feed_items_from_transitions, ical_calendar, rss_feed_xml


def test_feed_items_from_transitions_normalizes_and_sorts_newest_first():
    transitions = [
        {"ticker": "xlf", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"},
        {"ticker": "XLK", "from": "WARNING", "to": "STAGE_2_BULLISH", "date": "2026-05-21"},
    ]

    items = feed_items_from_transitions(transitions)

    assert [item.ticker for item in items] == ["XLK", "XLF"]
    assert items[0].title == "XLK transitioned WARNING -> STAGE_2_BULLISH"
    assert items[0].uid == "transition-20260521-xlk-warning-stage-2-bullish"


def test_feed_items_from_transitions_skip_malformed_transition_dates():
    transitions = [
        {"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-13-40"},
        {"ticker": "XLF", "from": "HOLD", "to": "WARNING", "date": ""},
        {"ticker": "XLV", "from": "HOLD", "to": "WARNING", "date": "2026-05-21"},
    ]

    items = feed_items_from_transitions(transitions)

    assert [item.ticker for item in items] == ["XLV"]
    assert items[0].uid == "transition-20260521-xlv-hold-warning"


def test_rss_feed_xml_escapes_text_and_includes_items():
    items = feed_items_from_transitions(
        [{"ticker": "XL&K", "from": "HOLD", "to": "WARNING", "date": "2026-05-20"}]
    )

    xml = rss_feed_xml(
        items,
        feed_url="https://example.test/transitions.rss",
        generated_at=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )

    assert '<rss version="2.0">' in xml
    assert "<title>Sector Momentum State Transitions</title>" in xml
    assert "XL&amp;K transitioned HOLD -&gt; WARNING" in xml
    assert "<guid isPermaLink=\"false\">transition-20260520-xl-k-hold-warning</guid>" in xml
    assert "Thu, 21 May 2026 12:00:00 +0000" in xml


def test_ical_calendar_emits_all_day_events_chronologically():
    items = feed_items_from_transitions(
        [
            {"ticker": "XLK", "from": "HOLD", "to": "WARNING", "date": "2026-05-21"},
            {"ticker": "XLF", "from": "WARNING", "to": "STAGE_2_BULLISH", "date": "2026-05-20"},
        ]
    )

    calendar = ical_calendar(items, generated_at=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc))

    assert calendar.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0")
    assert "DTSTAMP:20260521T120000Z" in calendar
    assert "DTSTART;VALUE=DATE:20260520" in calendar
    assert "SUMMARY:XLF transitioned WARNING -> STAGE_2_BULLISH" in calendar
    assert "DTSTART;VALUE=DATE:20260521" in calendar
    assert calendar.index("DTSTART;VALUE=DATE:20260520") < calendar.index("DTSTART;VALUE=DATE:20260521")
    assert calendar.endswith("END:VCALENDAR\r\n")


def test_ical_calendar_folds_long_content_lines_for_strict_clients():
    items = feed_items_from_transitions(
        [
            {
                "ticker": "XLK",
                "from": "HOLD",
                "to": "VERY_LONG_STAGE_NAME_WITH_A_DETAILED_REASON_THAT_EXCEEDS_ICAL_LINE_LENGTH",
                "date": "2026-05-21",
            }
        ]
    )

    calendar = ical_calendar(items, generated_at=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc))
    content_lines = calendar.rstrip("\r\n").split("\r\n")

    assert "\r\n " in calendar
    assert all(len(line.encode("utf-8")) <= 75 for line in content_lines)
