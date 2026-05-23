"""Repeatable browser QA target definitions and report helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


BROWSER_QA_TICKETS = (
    "B-110",
    "B-111",
    "B-112",
    "B-113",
    "B-114",
    "B-115",
    "B-116",
    "B-117",
    "B-146",
    "B-147",
)


@dataclass(frozen=True)
class BrowserQaTarget:
    target_id: str
    viewport: str
    width: int
    height: int
    path: str
    tickets: tuple[str, ...]
    checks: tuple[str, ...]
    focus_text: str = ""
    setup_actions: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class BrowserQaResult:
    target_id: str
    viewport: str
    tickets: tuple[str, ...]
    url: str
    screenshot: str
    checks: tuple[str, ...]
    ok: bool
    notes: tuple[str, ...] = ()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_rendered_text(value: str) -> str:
    return " ".join(value.casefold().split())


def missing_text_checks(rendered_text: str, checks: tuple[str, ...]) -> tuple[str, ...]:
    normalized_text = _normalize_rendered_text(rendered_text)
    missing: list[str] = []
    for check in checks:
        if not check.startswith("text:"):
            continue
        expected_text = _normalize_rendered_text(check.removeprefix("text:"))
        if expected_text and expected_text not in normalized_text:
            missing.append(check)
    return tuple(missing)


def browser_qa_targets() -> tuple[BrowserQaTarget, ...]:
    return (
        BrowserQaTarget(
            target_id="desktop-overview",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK",
            tickets=("B-110", "B-147"),
            checks=(
                "text:SENTIMENT BOARD",
                "text:BLUF",
                "text:VIEW OPTIONS",
            ),
            focus_text="SENTIMENT BOARD",
        ),
        BrowserQaTarget(
            target_id="desktop-palette-view-options",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK&browser_qa_palette=Solarized",
            tickets=("B-117",),
            checks=(
                "text:VIEW OPTIONS",
                "text:Palette",
                "text:Solarized",
            ),
            focus_text="Palette",
            setup_actions=(
                "expand:VIEW OPTIONS",
                "expand:VIEW OPTIONS",
                "expect-radio-checked:Solarized",
            ),
        ),
        BrowserQaTarget(
            target_id="desktop-rrg-spaghetti-drill",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK",
            tickets=("B-111", "B-112", "B-116"),
            checks=(
                "text:SECTOR SPAGHETTI",
                "text:DRILL",
                "text:CMF",
            ),
            focus_text="US SECTOR RELATIVE STRENGTH",
        ),
        BrowserQaTarget(
            target_id="desktop-comparison-view",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK",
            tickets=("B-115",),
            checks=(
                "text:COMPARE TICKERS",
            ),
            focus_text="COMPARE TICKERS",
        ),
        BrowserQaTarget(
            target_id="desktop-transition-pulse",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK&browser_qa_transition=1",
            tickets=("B-114",),
            checks=(
                "text:Recent transitions",
                "text:BROWSER QA",
                "text:STAGE 2 BULLISH",
            ),
            focus_text="Recent transitions",
            actions=(
                "expect-visible:.alert-row.pulse-transition",
            ),
        ),
        BrowserQaTarget(
            target_id="desktop-provider-status-banner",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK&browser_qa_provider_banner=1",
            tickets=("B-146",),
            checks=(
                "text:Provider gap",
                "text:Browser QA provider fallback fixture",
            ),
            focus_text="Provider gap",
            actions=(
                "expect-visible:.provider-status-banner",
            ),
        ),
        BrowserQaTarget(
            target_id="desktop-full-matrix-table",
            viewport="desktop",
            width=1440,
            height=1100,
            path="/?ticker=XLK",
            tickets=("B-113",),
            checks=(
                "text:FULL 7",
                "text:HIDE FULL",
            ),
            focus_text="FULL 7",
            actions=(
                "hover:first-full-table-row",
                "expect-visible:.full-table tbody tr:first-child .row-preview",
            ),
        ),
        BrowserQaTarget(
            target_id="tablet-dashboard",
            viewport="tablet",
            width=900,
            height=1100,
            path="/?ticker=XLK",
            tickets=("B-110", "B-112", "B-115"),
            checks=(
                "text:SENTIMENT BOARD",
                "text:Risk regime",
                "text:DRILL",
            ),
            focus_text="Risk regime",
        ),
        BrowserQaTarget(
            target_id="mobile-dashboard",
            viewport="mobile",
            width=390,
            height=1000,
            path="/?ticker=XLK",
            tickets=("B-110", "B-112", "B-114", "B-116", "B-117"),
            checks=(
                "text:SENTIMENT BOARD",
                "text:BLUF",
                "text:INSTRUMENTS",
            ),
            focus_text="BLUF",
        ),
    )


def build_browser_qa_report(
    results: list[BrowserQaResult],
    *,
    generated_at: str | None = None,
) -> str:
    stamp = generated_at or utc_timestamp()
    passed = sum(1 for result in results if result.ok)
    lines = [
        "# Browser QA Evidence",
        "",
        f"Generated: `{stamp}`",
        "",
        f"Targets: `{passed}/{len(results)}` passed",
        "",
        "| Target | Viewport | Tickets | Status | Screenshot | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        notes = "; ".join(result.notes) if result.notes else "ok"
        tickets = ", ".join(result.tickets)
        lines.append(
            f"| `{result.target_id}` | `{result.viewport}` | {tickets} | **{status}** | "
            f"`{result.screenshot}` | {notes} |"
        )
    lines.extend(
        [
            "",
            "Checks:",
        ]
    )
    for result in results:
        checks = ", ".join(f"`{check}`" for check in result.checks)
        lines.append(f"- `{result.target_id}`: {checks}")
    lines.extend(
        [
            "",
            "Scope:",
            "- Local dashboard browser rendering only.",
            "- No credentials, account data, notification endpoints, or private config values are required.",
            "- Screenshots are stored as local QA artifacts and should be regenerated after major UI changes.",
        ]
    )
    return "\n".join(lines) + "\n"
