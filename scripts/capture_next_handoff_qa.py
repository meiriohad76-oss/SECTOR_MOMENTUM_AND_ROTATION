"""Capture the Next.js migration shell and compare it with handoff stills.

This is a visual evidence harness for B-170. It does not assert pixel parity by
default because the React shell is still running as a migration candidate, but
it creates repeatable screenshots and similarity scores against the Momentum v2
handoff PNGs so parity can be tightened ticket by ticket.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NEXT_SCREEN_BUTTONS = {
    "overview": "Overview",
    "deepdive": "Deep Dive",
    "rotation": "Rotation",
}

QA_PROFILES = {
    "a": {
        "reference_profile": "Momentum v2 Display A handoff: A1/A2/A3 baseline",
        "default_url": "http://127.0.0.1:3000/",
        "capture_prefix": "next-a",
        "buttons": NEXT_SCREEN_BUTTONS,
        "reference_map": {
            "overview": "A1-terminal-overview.png",
            "deepdive": "A2-terminal-deepdive.png",
            "rotation": "A3-terminal-rotation.png",
        },
        "required_text": {
            "overview": ("A | Overview", "LEADERS", "RISK QUEUE"),
            "deepdive": ("B | Deep Dive", "Ticker focus", "The composite, built pillar by pillar"),
            "rotation": ("C | Rotation", "Relative Rotation Graph", "The flow river"),
        },
    },
    "b": {
        "reference_profile": "Momentum v2 Display B handoff: B1/B2/B3 baseline",
        "default_url": "http://127.0.0.1:3000/",
        "capture_prefix": "next-b",
        "buttons": NEXT_SCREEN_BUTTONS,
        "reference_map": {
            "overview": "B1-editorial-brief.png",
            "deepdive": "B2-editorial-article.png",
            "rotation": "B3-editorial-rotation.png",
        },
        "required_text": {
            "overview": ("A | Overview", "LEADERS", "RISK QUEUE"),
            "deepdive": ("B | Deep Dive", "Ticker focus", "The composite, built pillar by pillar"),
            "rotation": ("C | Rotation", "Relative Rotation Graph", "The flow river"),
        },
    },
    "c": {
        "reference_profile": "Momentum v2 Display C handoff: C1/C2/C3",
        "default_url": "http://127.0.0.1:3000/?presentation=c",
        "capture_prefix": "next",
        "buttons": {
            "overview": "Heatmap",
            "deepdive": "Deep dive",
            "rotation": "Rotation",
        },
        "reference_map": {
            "overview": "C1-pillarstack-heatmap.png",
            "deepdive": "C2-pillarstack-waterfall.png",
            "rotation": "C3-pillarstack-rotation.png",
        },
        "required_text": {
            "overview": ("The composite, dissected", "State changes", "Bullish cohort"),
            "deepdive": ("The composite, built pillar by pillar", "FOCUS", "State machine"),
            "rotation": ("The rotation map", "The flow river", "Flow internals"),
        },
    },
}

NEXT_SCREEN_REFERENCE_MAP = QA_PROFILES["c"]["reference_map"]
NEXT_SCREEN_REQUIRED_TEXT = QA_PROFILES["c"]["required_text"]


def _reference_dir() -> Path:
    return ROOT / "momentum v2" / "design_handoff_momentum_v2" / "media" / "screens"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _image_similarity(capture: Path, reference: Path) -> dict[str, object]:
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required. Install requirements-qa.txt") from exc

    with Image.open(capture).convert("RGB") as cap, Image.open(reference).convert("RGB") as ref:
        ref_resized = ref.resize(cap.size)
        diff = ImageChops.difference(cap, ref_resized)
        hist = diff.histogram()
        sq = (value * ((idx % 256) ** 2) for idx, value in enumerate(hist))
        rms = math.sqrt(sum(sq) / float(cap.size[0] * cap.size[1] * 3))
        return {
            "capture_size": list(cap.size),
            "reference_size": list(ref.size),
            "rms": round(rms, 4),
            "similarity": round(max(0.0, 1.0 - (rms / 255.0)), 4),
        }


def _image_nonblank(path: Path) -> bool:
    try:
        from PIL import Image, ImageStat
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required. Install requirements-qa.txt") from exc

    with Image.open(path).convert("RGB") as image:
        stat = ImageStat.Stat(image)
        return any(channel > 2 for channel in stat.stddev)


def _missing_text(body_text: str, required: tuple[str, ...]) -> list[str]:
    normalized = body_text.replace("\xa0", " ")
    return [text for text in required if text not in normalized]


def _click_screen_button(page, label: str, timeout_ms: int) -> None:
    fallback_timeout = min(timeout_ms, 1_500)
    try:
        page.get_by_role("button", name=label, exact=True).click(timeout=fallback_timeout)
        return
    except Exception:
        pass
    try:
        page.locator("button[aria-pressed]").filter(has_text=label).first.click(timeout=fallback_timeout)
        return
    except Exception:
        pass
    try:
        page.get_by_text(label, exact=True).click(timeout=fallback_timeout)
        return
    except Exception:
        pass
    page.locator("button").filter(has_text=label).first.click(timeout=timeout_ms)


def _wait_for_any_text(page, required: tuple[str, ...], timeout_ms: int) -> None:
    deadline = max(1_000, min(timeout_ms, 20_000))
    page.wait_for_function(
        """
        (items) => {
          const text = document.body ? document.body.innerText.replace(/\\u00a0/g, ' ') : '';
          return items.some((item) => text.includes(item));
        }
        """,
        arg=list(required),
        timeout=deadline,
    )


def _capture(
    url: str,
    output_dir: Path,
    screens: list[str],
    timeout_ms: int,
    *,
    profile: dict[str, object],
) -> list[dict[str, object]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Playwright is required. Install with: python -m pip install -r requirements-qa.txt "
            "and python -m playwright install chromium"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    buttons = profile["buttons"]
    required_text = profile["required_text"]
    capture_prefix = str(profile["capture_prefix"])
    rows: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1800}, device_scale_factor=1)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.locator("main").first.wait_for(timeout=timeout_ms)
        page.add_style_tag(
            content="""
            nextjs-portal,
            [data-nextjs-toast],
            [data-nextjs-dialog-overlay],
            [data-nextjs-dev-tools-button],
            [data-next-badge-root] {
              display: none !important;
              visibility: hidden !important;
            }
            """
        )
        for screen in screens:
            button_name = buttons[screen]
            screen_required_text = required_text[screen]
            screenshot_path = output_dir / f"{capture_prefix}-{screen}.png"
            error = ""
            try:
                if screen != "overview":
                    _click_screen_button(page, button_name, timeout_ms)
                _wait_for_any_text(page, screen_required_text, timeout_ms)
                page.wait_for_timeout(600)
                body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
                page.screenshot(path=str(screenshot_path), full_page=True, timeout=timeout_ms)
                missing = _missing_text(body_text, screen_required_text)
                nonblank = _image_nonblank(screenshot_path)
            except Exception as exc:
                body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
                try:
                    page.screenshot(path=str(screenshot_path), full_page=True, timeout=timeout_ms)
                    nonblank = _image_nonblank(screenshot_path)
                except Exception:
                    screenshot_path.write_bytes(b"")
                    nonblank = False
                missing = _missing_text(body_text, screen_required_text)
                error = f"{type(exc).__name__}: {exc}"
            rows.append(
                {
                    "screen": screen,
                    "capture": str(screenshot_path),
                    "required_text": list(screen_required_text),
                    "missing_text": missing,
                    "nonblank": nonblank,
                    "error": error,
                }
            )
        browser.close()
    return rows


def _compare(rows: list[dict[str, object]], reference_dir: Path, *, profile: dict[str, object]) -> list[dict[str, object]]:
    reference_map = profile["reference_map"]
    compared: list[dict[str, object]] = []
    for row in rows:
        screen = str(row["screen"])
        reference = reference_dir / reference_map[screen]
        entry = dict(row)
        entry["reference"] = str(reference)
        entry["reference_exists"] = reference.exists()
        if reference.exists():
            entry.update(_image_similarity(Path(str(row["capture"])), reference))
        entry["ok"] = bool(entry["nonblank"]) and not entry["missing_text"] and bool(entry["reference_exists"])
        compared.append(entry)
    return compared


def _write_report(output_dir: Path, report: list[dict[str, object]], *, url: str, profile_name: str, profile: dict[str, object]) -> Path:
    payload = {
        "generated_at_utc": _utc_stamp(),
        "profile": profile_name,
        "url": url,
        "reference_profile": profile["reference_profile"],
        "screens": report,
    }
    suffix = "" if profile_name == "c" else f"_{profile_name}"
    path = output_dir / f"next_handoff_qa_report{suffix}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(QA_PROFILES), default="c")
    parser.add_argument("--url", default=None, help="Override the profile default URL.")
    parser.add_argument("--output-dir", default=str(ROOT / ".tmp" / "next_handoff_qa"))
    parser.add_argument("--reference-dir", default=str(_reference_dir()))
    parser.add_argument("--screen", action="append", choices=sorted(NEXT_SCREEN_REFERENCE_MAP), help="Repeatable; defaults to all")
    parser.add_argument("--timeout-ms", type=int, default=90_000)
    parser.add_argument("--min-similarity", type=float, default=None, help="Optional 0..1 gate for future parity releases.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = QA_PROFILES[args.profile]
    url = args.url or profile["default_url"]
    screens = args.screen or ["overview", "deepdive", "rotation"]
    output_dir = Path(args.output_dir)
    rows = _capture(str(url), output_dir, screens, args.timeout_ms, profile=profile)
    report = _compare(rows, Path(args.reference_dir), profile=profile)
    report_path = _write_report(output_dir, report, url=str(url), profile_name=args.profile, profile=profile)
    print(json.dumps({"screens": len(report), "report": str(report_path)}, indent=2))
    failures = [row for row in report if not row.get("ok")]
    if args.min_similarity is not None:
        failures.extend(
            row
            for row in report
            if row.get("reference_exists") and float(row.get("similarity", 0.0)) < args.min_similarity
        )
    if failures:
        print(
            json.dumps(
                {
                    "failed": [
                        {
                            "screen": row.get("screen"),
                            "missing_text": row.get("missing_text"),
                            "nonblank": row.get("nonblank"),
                            "similarity": row.get("similarity"),
                        }
                        for row in failures
                    ]
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
