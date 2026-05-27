"""Capture browser screenshots for dashboard visual QA."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.browser_qa import (
    BrowserQaResult,
    browser_qa_targets,
    build_browser_qa_report,
    missing_text_checks,
    utc_timestamp,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8501"
DEFAULT_OUT_DIR = Path("docs/browser-qa/latest")
DEFAULT_QA_MODE = "local-dashboard"


def _target_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _image_nonblank(path: Path) -> bool:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for browser QA image checks. Install with: python -m pip install -r requirements-qa.txt") from exc

    with Image.open(path) as image:
        image = image.convert("RGB")
        extrema = image.getextrema()
    return any(low != high for low, high in extrema)


def _page_body_text(page) -> str:
    return page.evaluate("() => document.body ? document.body.innerText : ''")


def _wait_for_text_checks(page, checks: tuple[str, ...], timeout_ms: int) -> tuple[str, ...]:
    deadline = time.monotonic() + (timeout_ms / 1000)
    missing: tuple[str, ...] = tuple(check for check in checks if check.startswith("text:"))
    while time.monotonic() < deadline:
        body_text = _page_body_text(page)
        missing = missing_text_checks(body_text, checks)
        if not missing:
            return ()
        page.wait_for_timeout(500)
    return missing


def _wait_for_dashboard_idle(page, timeout_ms: int) -> tuple[str, ...]:
    loading_markers = (
        "LOADING MARKET DATA",
        "COMPUTING INDICATORS",
        "PREPARING DASHBOARD DATA",
        "FETCHING",
    )
    script = """
    (markers) => {
      const visibleText = [];
      for (const element of document.querySelectorAll('body *')) {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 0 || rect.height <= 0) {
          continue;
        }
        const text = (element.innerText || element.textContent || '').trim();
        if (text) {
          visibleText.push(text);
        }
      }
      const joined = visibleText.join(' ').toUpperCase();
      return markers.filter((marker) => joined.includes(marker));
    }
    """
    deadline = time.monotonic() + (timeout_ms / 1000)
    blockers: tuple[str, ...] = loading_markers
    while time.monotonic() < deadline:
        blockers = tuple(page.evaluate(script, list(loading_markers)))
        body_text = _page_body_text(page).replace("\xa0", " ").upper()
        if "SENTIMENT BOARD" in body_text and not blockers:
            return ()
        page.wait_for_timeout(500)
    return blockers


def _scroll_to_focus_text(page, focus_text: str, timeout_ms: int) -> str | None:
    if not focus_text:
        return None
    script = """
    (needle) => {
      const main = document.querySelector('section[data-testid="stMain"]');
      const normalize = (value) => String(value || '').toLowerCase().replace(/\\s+/g, ' ').trim();
      const target = normalize(needle);
      const canMeasure = (element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      };
      let best = null;
      let bestScore = Number.POSITIVE_INFINITY;
      for (const element of document.querySelectorAll('body *')) {
        const rawText = element.innerText || element.textContent || '';
        const text = normalize(rawText);
        if (!text.includes(target) || !canMeasure(element)) {
          continue;
        }
        if (text.length > Math.max(target.length + 120, 240)) {
          continue;
        }
        const rect = element.getBoundingClientRect();
        const score = (rect.width * rect.height) + (text.length * 5);
        if (score < bestScore) {
          best = element;
          bestScore = score;
        }
      }
      if (!best) {
        if (main) {
          main.scrollTop = Math.min(main.scrollTop + 700, main.scrollHeight);
        }
        return { found: false, scrollTop: main ? Math.round(main.scrollTop) : 0 };
      }
      const rect = best.getBoundingClientRect();
      const label = (best.innerText || best.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
      const viewportHeight = main ? main.clientHeight : window.innerHeight;
      const desiredTop = Math.min(520, Math.max(160, Math.round(viewportHeight * 0.38)));
      const visible = rect.top >= 96 && rect.bottom <= viewportHeight - 96;
      if (main && !visible) {
        main.scrollTop = Math.max(0, main.scrollTop + rect.top - desiredTop);
      }
      return {
        found: true,
        visible,
        label,
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        height: Math.round(rect.height),
        scrollTop: main ? Math.round(main.scrollTop) : 0,
        viewportHeight: Math.round(viewportHeight),
      };
    }
    """
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        result = page.evaluate(script, focus_text)
        if result.get("found") and result.get("visible"):
            page.wait_for_timeout(750)
            return (
                f"focused text: {focus_text} visible=true "
                f"top={result.get('top')} height={result.get('height')} scrollTop={result.get('scrollTop')}"
            )
        page.wait_for_timeout(500)
    return None


def _run_target_actions(page, actions: tuple[str, ...], timeout_ms: int) -> tuple[str, ...]:
    notes: list[str] = []
    action_timeout = min(timeout_ms, 15_000)
    for action in actions:
        if action.startswith("expand:"):
            label = action.removeprefix("expand:")
            if label == "VIEW OPTIONS":
                try:
                    if page.get_by_text("Palette", exact=True).first.is_visible(timeout=750):
                        notes.append("view options already expanded")
                        continue
                except Exception:
                    pass
            page.get_by_text(label, exact=True).first.click(timeout=action_timeout)
            page.wait_for_timeout(750)
            notes.append(f"expanded: {label}")
            continue
        if action.startswith("radio:"):
            payload = action.removeprefix("radio:")
            group, value = payload.split("=", 1)
            page.locator("label").filter(has_text=value).first.click(timeout=action_timeout)
            page.wait_for_timeout(1_500)
            notes.append(f"selected radio: {group}={value}")
            continue
        if action == "hover:first-full-table-row":
            page.locator(".full-table tbody tr").first.hover(timeout=action_timeout)
            page.wait_for_timeout(750)
            notes.append("hovered first full-table row")
            continue
        if action.startswith("expect-visible:"):
            selector = action.removeprefix("expect-visible:")
            page.locator(selector).first.wait_for(state="visible", timeout=action_timeout)
            notes.append(f"visible selector: {selector}")
            continue
        if action.startswith("expect-radio-checked:"):
            value = action.removeprefix("expect-radio-checked:")
            page.wait_for_function(
                """
                (value) => Array.from(document.querySelectorAll('label'))
                  .some((label) => label.innerText.trim() === value && label.querySelector('input')?.checked)
                """,
                arg=value,
                timeout=action_timeout,
            )
            notes.append(f"checked radio: {value}")
            continue
        raise ValueError(f"Unsupported browser QA action: {action}")
    return tuple(notes)


def _run_playwright_capture(
    base_url: str,
    out_dir: Path,
    timeout_ms: int,
    settle_ms: int,
    browser_channel: str | None = None,
    user_data_dir: str | None = None,
    headed: bool = False,
) -> list[BrowserQaResult]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright is required for browser QA screenshots. "
            "Install with: python -m pip install playwright && python -m playwright install chromium"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[BrowserQaResult] = []
    with sync_playwright() as playwright:
        browser = None
        context = None
        if user_data_dir:
            context = (
                playwright.chromium.launch_persistent_context(
                    user_data_dir,
                    channel=browser_channel,
                    headless=not headed,
                )
                if browser_channel
                else playwright.chromium.launch_persistent_context(user_data_dir, headless=not headed)
            )
        else:
            browser = (
                playwright.chromium.launch(channel=browser_channel, headless=not headed)
                if browser_channel
                else playwright.chromium.launch(headless=not headed)
            )
            context = browser
        try:
            for target in browser_qa_targets():
                screenshot_path = out_dir / f"{target.target_id}.png"
                if screenshot_path.exists():
                    screenshot_path.unlink()
                url = _target_url(base_url, target.path)
                page = context.new_page()
                page.set_viewport_size({"width": target.width, "height": target.height})
                notes: list[str] = []
                ok = True
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    try:
                        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15_000))
                    except Exception:
                        notes.append("networkidle timeout; continued with body text polling")
                    page.wait_for_timeout(settle_ms)
                    ready_missing = _wait_for_text_checks(
                        page,
                        ("text:SENTIMENT BOARD",),
                        min(timeout_ms, 60_000),
                    )
                    if ready_missing:
                        ok = False
                        notes.append("dashboard ready text missing")
                    idle_blockers = _wait_for_dashboard_idle(page, min(timeout_ms, 90_000))
                    if idle_blockers:
                        ok = False
                        notes.append(f"dashboard idle timeout: {', '.join(idle_blockers)}")
                    try:
                        notes.extend(_run_target_actions(page, target.setup_actions, min(timeout_ms, 60_000)))
                    except Exception as exc:
                        ok = False
                        notes.append(f"setup action error: {type(exc).__name__}: {exc}")
                    if target.setup_actions:
                        idle_blockers = _wait_for_dashboard_idle(page, min(timeout_ms, 90_000))
                        if idle_blockers:
                            ok = False
                            notes.append(f"dashboard idle timeout after setup: {', '.join(idle_blockers)}")
                    focus_note = _scroll_to_focus_text(page, target.focus_text, min(timeout_ms, 60_000))
                    if focus_note:
                        notes.append(focus_note)
                    elif target.focus_text:
                        ok = False
                        notes.append(f"focus text not visible: {target.focus_text}")
                    try:
                        notes.extend(_run_target_actions(page, target.actions, min(timeout_ms, 60_000)))
                    except Exception as exc:
                        ok = False
                        notes.append(f"action error: {type(exc).__name__}: {exc}")
                    for check in _wait_for_text_checks(page, target.checks, min(timeout_ms, 15_000)):
                        ok = False
                        notes.append(f"missing {check}")
                    page.screenshot(path=str(screenshot_path), full_page=False, timeout=timeout_ms)
                    if not _image_nonblank(screenshot_path):
                        ok = False
                        notes.append("blank screenshot")
                    else:
                        notes.append("nonblank screenshot")
                except Exception as exc:
                    ok = False
                    notes.append(f"capture error: {type(exc).__name__}: {exc}")
                    screenshot_path.write_bytes(b"")
                finally:
                    page.close()
                results.append(
                    BrowserQaResult(
                        target_id=target.target_id,
                        viewport=target.viewport,
                        tickets=target.tickets,
                        url=url,
                        screenshot=screenshot_path.as_posix(),
                        checks=target.checks,
                        ok=ok,
                        notes=tuple(notes),
                    )
                )
        finally:
            if browser is not None:
                browser.close()
            else:
                context.close()
    return results


def _write_outputs(results: list[BrowserQaResult], out_dir: Path, generated_at: str, qa_mode: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": generated_at,
        "qa_mode": qa_mode,
        "results": [
            {
                "target_id": result.target_id,
                "viewport": result.viewport,
                "tickets": list(result.tickets),
                "url": result.url,
                "screenshot": result.screenshot,
                "checks": list(result.checks),
                "setup_actions": list(next(target.setup_actions for target in browser_qa_targets() if target.target_id == result.target_id)),
                "actions": list(next(target.actions for target in browser_qa_targets() if target.target_id == result.target_id)),
                "ok": result.ok,
                "notes": list(result.notes),
            }
            for result in results
        ],
    }
    (out_dir / "browser_qa_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "browser_qa_report.md").write_text(
        build_browser_qa_report(results, generated_at=generated_at),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-ms", type=int, default=120_000)
    parser.add_argument("--settle-ms", type=int, default=5_000)
    parser.add_argument(
        "--qa-mode",
        default=DEFAULT_QA_MODE,
        help="Label recorded in the manifest, for example browser-qa-secret-free when BROWSER_QA_MODE=1 and API keys are unset.",
    )
    parser.add_argument(
        "--browser-channel",
        default=None,
        help="Optional installed browser channel, for example chrome or msedge, to avoid bundled browser downloads.",
    )
    parser.add_argument(
        "--user-data-dir",
        default=None,
        help="Optional persistent browser profile directory, useful for an already-authenticated Cloudflare Access session.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run a visible browser window so an operator can complete Cloudflare Access authentication.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    generated_at = utc_timestamp()
    results = _run_playwright_capture(
        args.base_url,
        out_dir,
        args.timeout_ms,
        args.settle_ms,
        browser_channel=args.browser_channel,
        user_data_dir=args.user_data_dir,
        headed=args.headed,
    )
    _write_outputs(results, out_dir, generated_at, args.qa_mode)
    failed = [result for result in results if not result.ok]
    print(f"browser_qa=written out_dir={out_dir} qa_mode={args.qa_mode} targets={len(results)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
