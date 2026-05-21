"""Export RSS and iCal artifacts from the local transition log."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.scoring import recent_transitions
from src.transition_feeds import feed_items_from_transitions, ical_calendar, rss_feed_xml


DEFAULT_OUTPUT_DIR = ROOT / "data" / "feeds"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export state-transition RSS and iCal feed artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for transitions.rss/.ics")
    parser.add_argument("--limit", type=int, default=500, help="Maximum transitions to read from state.json")
    parser.add_argument("--feed-url", default="", help="Optional public URL for the RSS feed link field")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    transitions = list(reversed(recent_transitions(n=args.limit)))
    items = feed_items_from_transitions(transitions)
    rss_path = output_dir / "transitions.rss"
    ics_path = output_dir / "transitions.ics"
    rss_path.write_text(rss_feed_xml(items, feed_url=args.feed_url), encoding="utf-8")
    ics_path.write_text(ical_calendar(items), encoding="utf-8")
    print(f"transition_feeds=written rss={rss_path} ics={ics_path} items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
