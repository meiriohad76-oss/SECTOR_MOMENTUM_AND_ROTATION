"""RSS and iCal feed formatters for state-machine transitions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from email.utils import format_datetime
import re
from typing import Iterable, Mapping
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class TransitionFeedItem:
    ticker: str
    from_state: str
    to_state: str
    date: str
    title: str
    uid: str


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _compact_date(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit()) or "undated"


def _transition_datetime(value: str) -> datetime:
    try:
        date_value = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        date_value = datetime(1970, 1, 1).date()
    return datetime.combine(date_value, time.min, tzinfo=timezone.utc)


def _ical_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")


def feed_items_from_transitions(transitions: Iterable[Mapping[str, object]]) -> list[TransitionFeedItem]:
    items: list[TransitionFeedItem] = []
    for transition in transitions:
        ticker = str(transition.get("ticker", "UNKNOWN")).upper()
        from_state = str(transition.get("from", "UNKNOWN"))
        to_state = str(transition.get("to", "UNKNOWN"))
        date = str(transition.get("date", ""))
        title = f"{ticker} transitioned {from_state} -> {to_state}"
        uid = f"transition-{_compact_date(date)}-{_slug(ticker)}-{_slug(from_state)}-{_slug(to_state)}"
        items.append(
            TransitionFeedItem(
                ticker=ticker,
                from_state=from_state,
                to_state=to_state,
                date=date,
                title=title,
                uid=uid,
            )
        )
    return sorted(items, key=lambda item: (item.date, item.ticker), reverse=True)


def rss_feed_xml(
    items: Iterable[TransitionFeedItem],
    *,
    feed_url: str = "",
    generated_at: datetime | None = None,
) -> str:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    item_xml = []
    for item in items:
        pub_date = format_datetime(_transition_datetime(item.date))
        description = f"{item.title} on {item.date}"
        item_xml.append(
            "\n".join(
                [
                    "    <item>",
                    f"      <title>{escape(item.title)}</title>",
                    f"      <description>{escape(description)}</description>",
                    f"      <guid isPermaLink=\"false\">{escape(item.uid)}</guid>",
                    f"      <pubDate>{pub_date}</pubDate>",
                    "    </item>",
                ]
            )
        )
    atom_link = f'    <link>{escape(feed_url)}</link>\n' if feed_url else ""
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0">',
            "  <channel>",
            "    <title>Sector Momentum State Transitions</title>",
            "    <description>State-machine transitions from the Sector Momentum dashboard.</description>",
            atom_link.rstrip("\n"),
            f"    <lastBuildDate>{format_datetime(generated.astimezone(timezone.utc))}</lastBuildDate>",
            *item_xml,
            "  </channel>",
            "</rss>",
            "",
        ]
    )


def ical_calendar(items: Iterable[TransitionFeedItem], *, generated_at: datetime | None = None) -> str:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    stamp = generated.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Sector Momentum//State Transitions//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for item in sorted(items, key=lambda entry: (entry.date, entry.ticker)):
        date_value = _compact_date(item.date)
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_ical_escape(item.uid)}@sector-momentum",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{date_value}",
                f"SUMMARY:{_ical_escape(item.title)}",
                f"DESCRIPTION:{_ical_escape(item.title + ' on ' + item.date)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
