"""Lightweight rendered-browser smoke for a running dashboard URL.

This complements the core Pi deploy gate. The core gate proves process,
state, provider, and Cloudflare health without browser dependencies; this
script proves the Streamlit app actually renders key dashboard sections when
Playwright and a browser are available.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.browser_qa import missing_text_checks  # noqa: E402


DEFAULT_EXPECTED_TEXT = (
    "text:SENTIMENT BOARD",
    "text:BLUF",
    "text:Data and dashboard health",
)
LOADING_MARKERS = (
    "LOADING MARKET DATA",
    "COMPUTING INDICATORS",
    "PREPARING DASHBOARD DATA",
    "FETCHING",
)


def _target_state_from_text(body_text: str, checks: tuple[str, ...]) -> tuple[bool, str, tuple[str, ...]]:
    upper = body_text.upper().replace("\xa0", " ")
    if "CLOUDFLARE ACCESS" in upper or "SIGN IN - CLOUDFLARE ACCESS" in upper:
        return False, "cloudflare_access_wall", checks
    if "TRACEBACK" in upper or "UNCAUGHT EXCEPTION" in upper or "UNCAUGHTEXCEPTION" in upper:
        return False, "streamlit_error_page", checks
    missing = missing_text_checks(body_text, checks)
    if not missing:
        return True, "rendered_dashboard", ()
    return False, "missing_rendered_text", missing


def _body_text(page) -> str:
    return page.evaluate("() => document.body ? document.body.innerText : ''")


def _visible_loading_markers(page) -> tuple[str, ...]:
    script = """
    (markers) => {
      const text = document.body ? document.body.innerText.toUpperCase() : '';
      return markers.filter((marker) => text.includes(marker));
    }
    """
    return tuple(page.evaluate(script, list(LOADING_MARKERS)))


def _run_rendered_smoke(
    *,
    url: str,
    checks: tuple[str, ...],
    timeout_ms: int,
    settle_ms: int,
    browser_channel: str | None,
    user_data_dir: str | None,
    headed: bool,
) -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {
            "ok": False,
            "state": "playwright_missing",
            "detail": str(exc),
        }

    deadline = time.monotonic() + timeout_ms / 1000
    with sync_playwright() as playwright:
        browser = None
        context = None
        page = None
        try:
            if user_data_dir:
                context = (
                    playwright.chromium.launch_persistent_context(
                        user_data_dir,
                        headless=not headed,
                        channel=browser_channel,
                        timeout=timeout_ms,
                    )
                    if browser_channel
                    else playwright.chromium.launch_persistent_context(
                        user_data_dir,
                        headless=not headed,
                        timeout=timeout_ms,
                    )
                )
            else:
                browser = (
                    playwright.chromium.launch(channel=browser_channel, headless=not headed, timeout=timeout_ms)
                    if browser_channel
                    else playwright.chromium.launch(headless=not headed, timeout=timeout_ms)
                )
                context = browser
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(settle_ms)
            last_state = "pending"
            last_missing: tuple[str, ...] = checks
            while time.monotonic() < deadline:
                blockers = _visible_loading_markers(page)
                body = _body_text(page)
                ok, state, missing = _target_state_from_text(body, checks)
                last_state = state
                last_missing = missing
                if ok and not blockers:
                    return {
                        "ok": True,
                        "state": state,
                        "detail": f"matched={len(checks)} url_host={urlparse(url).netloc or 'local'}",
                        "missing": [],
                    }
                page.wait_for_timeout(500)
            return {
                "ok": False,
                "state": last_state,
                "detail": "render timeout",
                "missing": list(last_missing),
            }
        except Exception as exc:
            return {
                "ok": False,
                "state": "browser_error",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        finally:
            try:
                if page is not None:
                    page.close()
            finally:
                if browser is not None:
                    browser.close()
                elif context is not None:
                    context.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--expect-text", action="append", default=[])
    parser.add_argument("--timeout-ms", type=int, default=90_000)
    parser.add_argument("--settle-ms", type=int, default=2_000)
    parser.add_argument("--browser-channel", default="")
    parser.add_argument("--user-data-dir", default="")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="Exit 0 when Playwright/browser setup is unavailable; rendered content failures still exit non-zero.",
    )
    return parser.parse_args(argv)


def _run_rendered_smoke_worker(queue: mp.Queue, kwargs: dict[str, object]) -> None:
    try:
        queue.put(_run_rendered_smoke(**kwargs))
    except Exception as exc:
        queue.put({"ok": False, "state": "browser_error", "detail": f"{type(exc).__name__}: {exc}"})


def _run_rendered_smoke_with_deadline(**kwargs) -> dict[str, object]:
    timeout_ms = int(kwargs.get("timeout_ms") or 90_000)
    queue: mp.Queue = mp.Queue()
    process = mp.Process(target=_run_rendered_smoke_worker, args=(queue, kwargs), daemon=True)
    process.start()
    process.join(timeout_ms / 1000 + 5)
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        result = {
            "ok": False,
            "state": "browser_timeout",
            "detail": f"browser smoke exceeded {timeout_ms}ms",
        }
    elif not queue.empty():
        result = dict(queue.get())
    else:
        result = {
            "ok": False,
            "state": "browser_error",
            "detail": f"browser smoke exited with code {process.exitcode}",
        }
    queue.close()
    queue.join_thread()
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checks = tuple(args.expect_text or DEFAULT_EXPECTED_TEXT)
    runner = _run_rendered_smoke_with_deadline if __name__ == "__main__" else _run_rendered_smoke
    result = runner(
        url=args.url,
        checks=checks,
        timeout_ms=args.timeout_ms,
        settle_ms=args.settle_ms,
        browser_channel=args.browser_channel or None,
        user_data_dir=args.user_data_dir or None,
        headed=bool(args.headed),
    )
    print(
        "rendered_dashboard_smoke "
        f"ok={str(bool(result.get('ok'))).lower()} "
        f"state={result.get('state')} "
        f"detail={result.get('detail')}"
    )
    print(json.dumps(result, sort_keys=True))
    unavailable = result.get("state") in {"playwright_missing", "browser_error", "browser_timeout"}
    if result.get("ok") or (args.allow_unavailable and unavailable):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
