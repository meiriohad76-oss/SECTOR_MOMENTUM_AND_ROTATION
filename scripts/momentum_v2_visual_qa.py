"""Capture Momentum v2 screen screenshots and compare against handoff refs.

This is intentionally a QA harness, not a deployment gate yet. The current
Streamlit implementation is an adaptation of the React handoff, so the first
useful output is a repeatable capture set plus a similarity report that can be
tightened as pixel fidelity improves.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REFERENCE_MAP = {
    ("A", "overview"): "A1-terminal-overview.png",
    ("A", "deepdive"): "A2-terminal-deepdive.png",
    ("A", "rotation"): "A3-terminal-rotation.png",
    ("B", "overview"): "B1-editorial-brief.png",
    ("B", "deepdive"): "B2-editorial-article.png",
    ("B", "rotation"): "B3-editorial-rotation.png",
    ("C", "overview"): "C1-pillarstack-heatmap.png",
    ("C", "deepdive"): "C2-pillarstack-waterfall.png",
    ("C", "rotation"): "C3-pillarstack-rotation.png",
}
DISPLAY_LABEL = {
    "A": "A | Terminal",
    "B": "B | Editorial",
    "C": "C | Pillar Stack",
}
SCREEN_LABEL = {
    "overview": "Overview",
    "deepdive": "Deep dive",
    "rotation": "Rotation",
}


def _reference_dir() -> Path:
    return ROOT / "momentum v2" / "design_handoff_momentum_v2" / "media" / "screens"


def _iter_targets(displays: Iterable[str], screens: Iterable[str]) -> list[tuple[str, str]]:
    return [
        (display, screen)
        for display in displays
        for screen in screens
        if (display, screen) in REFERENCE_MAP
    ]


def _click_segment(page, label: str) -> None:
    # Streamlit segmented controls render as buttons/radio-like controls
    # depending on version. Try accessible exact text first, then a text match.
    try:
        page.get_by_role("button", name=label, exact=True).click(timeout=2500)
        return
    except Exception:
        pass
    try:
        page.get_by_text(label, exact=True).click(timeout=2500)
        return
    except Exception as exc:
        raise RuntimeError(f"Could not click segmented-control option: {label}") from exc


def _capture(url: str, output_dir: Path, targets: list[tuple[str, str]]) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Playwright is required. Install with: python -m pip install -r requirements-qa.txt "
            "and python -m playwright install chromium"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1800}, device_scale_factor=1)
        page.goto(url, wait_until="networkidle", timeout=90000)
        page.locator(".mv2-shell").first.wait_for(timeout=90000)
        for display, screen in targets:
            _click_segment(page, DISPLAY_LABEL[display])
            _click_segment(page, SCREEN_LABEL[screen])
            page.locator(".mv2-shell").first.wait_for(timeout=30000)
            path = output_dir / f"{display}-{screen}.png"
            page.locator(".mv2-shell").first.screenshot(path=str(path))
            rows.append({"display": display, "screen": screen, "capture": str(path)})
        browser.close()
    return rows


def _fixture_rows():
    from src.momentum_v2 import MomentumV2Row

    data = [
        ("XLE", "Energy sector", "US Sectors", "STAGE_2_BULLISH", 1.42, 0.76, 31.0, "2", "Leading", 108, 106, 0.18, 0.32, 0.72, True, True, [0.24, 0.10, 0.18, 0.08, 0.12, 0.04, 0.66]),
        ("XLV", "Health care sector", "US Sectors", "STAGE_2_BULLISH", 1.18, 0.44, 19.0, "2", "Leading", 106, 105, 0.12, 0.21, 0.68, True, True, [0.19, 0.08, 0.16, 0.06, 0.12, 0.06, 0.51]),
        ("XLK", "Technology sector", "US Sectors", "WARNING", -0.18, -0.21, 24.6, "2", "Weakening", 103, 96, -0.03, 0.02, 0.58, True, True, [0.18, -0.04, 0.06, -0.18, 0.08, -0.04, -0.24]),
        ("XLF", "Financials sector", "US Sectors", "WARNING", -0.42, -0.34, 12.0, "2", "Weakening", 101, 95, -0.06, -0.05, 0.44, True, True, [0.08, -0.09, -0.04, -0.12, 0.08, -0.02, -0.31]),
        ("SMH", "Semiconductors", "US Industries", "EXIT", -1.04, -0.62, 22.0, "3", "Lagging", 96, 92, -0.14, -0.20, 0.38, False, False, [0.15, -0.16, -0.18, -0.16, -0.08, -0.04, -0.57]),
        ("GDX", "Gold miners", "US Industries", "STAGE_2_BULLISH", 1.58, 0.88, 39.0, "2", "Leading", 109, 108, 0.20, 0.36, 0.74, True, True, [0.31, 0.10, 0.20, 0.10, 0.12, 0.03, 0.72]),
        ("EWJ", "Japan", "Countries", "HOLD", 0.32, 0.12, 14.0, "2", "Improving", 99, 104, 0.04, 0.08, 0.56, True, True, [0.08, 0.02, -0.01, 0.08, 0.08, 0.00, 0.07]),
        ("MTUM", "Momentum factor", "Factors", "WARNING", -0.34, -0.18, 22.0, "2", "Weakening", 102, 96, -0.02, 0.01, 0.49, True, True, [0.16, -0.02, 0.04, -0.14, 0.08, -0.01, -0.45]),
    ]
    rows = []
    for item in data:
        ticker, identity, asset_class, state, s, f, mom, stage, quad, rsr, rsm, cmf, mans, breadth, above, slope, pillars = item
        rows.append(
            MomentumV2Row(
                ticker=ticker,
                identity=identity,
                asset_class=asset_class,
                state=state,
                s_score=s,
                f_score=f,
                momentum_pct=mom,
                stage=stage,
                quadrant=quad,
                rs_ratio=rsr,
                rs_momentum=rsm,
                cmf21=cmf,
                mansfield_rs=mans,
                breadth_50d=breadth,
                above_30wma=above,
                ma_slope_pos=slope,
                pillars=dict(zip(("MOM", "MANS", "RS-R", "RS-M", "FILT", "CYC", "FLOW"), pillars)),
                reasons=(
                    "Fixture QA row generated from the handoff late-cycle story.",
                    f"RRG is {quad}; flow score is {f:+.2f}.",
                ),
            )
        )
    return rows


def _static_html(display: str, screen: str) -> str:
    from src.momentum_v2 import css, render_display

    body = render_display(display, _fixture_rows(), "FRI MAY 22 2026 | 16:00 ET", screen=screen, focus_ticker="XLK")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>:root{--font-mono:'Consolas','Courier New',monospace;--font-prose:Inter,Arial,sans-serif}"
        "body{margin:0;background:#d8d8d8;padding:24px}"
        + css()
        + "</style></head><body>"
        + body
        + "</body></html>"
    )


def _capture_static(output_dir: Path, targets: list[tuple[str, str]]) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Playwright is required. Install requirements-qa.txt and Chromium.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1800}, device_scale_factor=1)
        for display, screen in targets:
            html_path = output_dir / f"{display}-{screen}.html"
            html_path.write_text(_static_html(display, screen), encoding="utf-8")
            page.goto(html_path.resolve().as_uri(), wait_until="load")
            page.locator(".mv2-shell").first.wait_for(timeout=30000)
            path = output_dir / f"{display}-{screen}.png"
            page.locator(".mv2-shell").first.screenshot(path=str(path))
            rows.append({"display": display, "screen": screen, "capture": str(path), "mode": "static"})
        browser.close()
    return rows


def _rms_similarity(capture: Path, reference: Path) -> dict:
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required for image comparison. Install requirements-qa.txt") from exc

    with Image.open(capture).convert("RGB") as cap, Image.open(reference).convert("RGB") as ref:
        ref_resized = ref.resize(cap.size)
        diff = ImageChops.difference(cap, ref_resized)
        hist = diff.histogram()
        sq = (value * ((idx % 256) ** 2) for idx, value in enumerate(hist))
        rms = math.sqrt(sum(sq) / float(cap.size[0] * cap.size[1] * 3))
        similarity = max(0.0, 1.0 - (rms / 255.0))
        return {
            "capture_size": list(cap.size),
            "reference_size": list(ref.size),
            "rms": round(rms, 4),
            "similarity": round(similarity, 4),
        }


def _compare(rows: list[dict], reference_dir: Path) -> list[dict]:
    compared = []
    for row in rows:
        key = (row["display"], row["screen"])
        reference = reference_dir / REFERENCE_MAP[key]
        entry = dict(row)
        entry["reference"] = str(reference)
        entry["reference_exists"] = reference.exists()
        if reference.exists():
            entry.update(_rms_similarity(Path(row["capture"]), reference))
        compared.append(entry)
    return compared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--output-dir", default=str(ROOT / ".tmp" / "momentum_v2_visual_qa"))
    parser.add_argument("--reference-dir", default=str(_reference_dir()))
    parser.add_argument("--static-fixture", action="store_true", help="Capture deterministic static Momentum v2 HTML instead of a live Streamlit URL")
    parser.add_argument("--display", action="append", choices=["A", "B", "C"], help="Repeatable; defaults to all")
    parser.add_argument("--screen", action="append", choices=["overview", "deepdive", "rotation"], help="Repeatable; defaults to all")
    args = parser.parse_args()

    displays = args.display or ["A", "B", "C"]
    screens = args.screen or ["overview", "deepdive", "rotation"]
    targets = _iter_targets(displays, screens)
    rows = (
        _capture_static(Path(args.output_dir), targets)
        if args.static_fixture
        else _capture(args.url, Path(args.output_dir), targets)
    )
    report = _compare(rows, Path(args.reference_dir))
    report_path = Path(args.output_dir) / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"screens": len(report), "report": str(report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
