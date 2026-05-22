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


def _feed_url_from_public_base(public_base_url: str) -> str:
    if not public_base_url:
        return ""
    return f"{public_base_url.rstrip('/')}/transitions.rss"


def _write_feed_files(output_dir: Path, *, items: list, feed_url: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rss_path = output_dir / "transitions.rss"
    ics_path = output_dir / "transitions.ics"
    rss_path.write_text(rss_feed_xml(items, feed_url=feed_url), encoding="utf-8")
    ics_path.write_text(ical_calendar(items), encoding="utf-8")
    return rss_path, ics_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export state-transition RSS and iCal feed artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for transitions.rss/.ics")
    parser.add_argument("--limit", type=int, default=500, help="Maximum transitions to read from state.json")
    parser.add_argument("--feed-url", default="", help="Optional public URL for the RSS feed link field")
    parser.add_argument(
        "--publish-dir",
        default="",
        help="Optional static directory for public feed copies, for example public/feeds",
    )
    parser.add_argument(
        "--public-base-url",
        default="",
        help="Optional public base URL used to derive the RSS link, for example https://example.test/feeds/",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit < 0:
        print("error: limit must be non-negative", file=sys.stderr)
        return 2
    transitions = list(reversed(recent_transitions(n=args.limit)))
    items = feed_items_from_transitions(transitions)
    feed_url = args.feed_url or _feed_url_from_public_base(args.public_base_url)
    rss_path, ics_path = _write_feed_files(Path(args.output_dir), items=items, feed_url=feed_url)
    message = f"transition_feeds=written rss={rss_path} ics={ics_path} items={len(items)}"
    if args.publish_dir:
        published_rss, published_ics = _write_feed_files(Path(args.publish_dir), items=items, feed_url=feed_url)
        message += f" published_rss={published_rss} published_ics={published_ics}"
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
