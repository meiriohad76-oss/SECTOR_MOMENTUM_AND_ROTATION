"""Content-aware deployment smoke gate for local and protected dashboard routes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.live_smoke import classify_local_dashboard_response, classify_protected_dashboard_response


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fetch(url: str, timeout: float) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(url, headers={"User-Agent": "sector-dashboard-deploy-smoke/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), dict(response.headers), response.read(120_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(120_000).decode("utf-8", errors="replace")
        return int(exc.code), dict(exc.headers), body
    except Exception as exc:
        return 0, {}, f"{type(exc).__name__}: {exc}"


def _state_file_smoke(path: str, *, min_tickers: int, max_age_seconds: int) -> tuple[bool, str, str]:
    state_path = Path(path)
    if not state_path.exists() or state_path.stat().st_size <= 0:
        return False, "missing", str(state_path)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return False, "unreadable", type(exc).__name__
    by_ticker = payload.get("by_ticker", {}) if isinstance(payload, dict) else {}
    ticker_count = len(by_ticker) if isinstance(by_ticker, dict) else 0
    updated = str(payload.get("updated", "") if isinstance(payload, dict) else "")
    parsed_updated = _parse_utc(updated)
    age_seconds = None
    if parsed_updated is not None:
        age_seconds = int((datetime.now(timezone.utc) - parsed_updated).total_seconds())
    if ticker_count < min_tickers:
        return False, "thin_state", f"tickers={ticker_count} min={min_tickers}"
    if age_seconds is None:
        return False, "missing_updated", f"updated={updated or 'missing'}"
    if age_seconds < 0:
        return False, "future_updated", f"age_seconds={age_seconds}"
    if age_seconds > max_age_seconds:
        return False, "stale_state", f"age_seconds={age_seconds} max={max_age_seconds}"
    return True, "fresh_state", f"tickers={ticker_count} age_seconds={age_seconds}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dashboard-url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--public-dashboard-url", default="")
    parser.add_argument("--expect-cloudflare-access", action="store_true")
    parser.add_argument(
        "--require-local-dashboard-markers",
        action="store_true",
        help="Fail unless the local route contains dashboard section markers, not only the Streamlit shell.",
    )
    parser.add_argument("--state-file", default="", help="Optional dashboard state JSON to validate after refresh.")
    parser.add_argument("--min-state-tickers", type=int, default=80)
    parser.add_argument("--max-state-age-seconds", type=int, default=300)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    exit_code = 0
    status, _headers, body = _fetch(args.local_dashboard_url, args.timeout)
    local = classify_local_dashboard_response(
        status_code=status,
        text=body,
        require_dashboard_markers=args.require_local_dashboard_markers,
    )
    print(f"local_dashboard_smoke ok={str(local.ok).lower()} state={local.state} detail={local.detail}")
    if not local.ok:
        exit_code = 1

    if args.state_file:
        ok, state, detail = _state_file_smoke(
            args.state_file,
            min_tickers=args.min_state_tickers,
            max_age_seconds=args.max_state_age_seconds,
        )
        print(f"dashboard_state_smoke ok={str(ok).lower()} state={state} detail={detail}")
        if not ok:
            exit_code = 1

    if args.public_dashboard_url:
        status, headers, body = _fetch(args.public_dashboard_url, args.timeout)
        protected = classify_protected_dashboard_response(status_code=status, headers=headers, text=body)
        expected = "cloudflare_access_challenge" if args.expect_cloudflare_access else "authenticated_dashboard"
        print(
            "public_dashboard_smoke "
            f"ok={str(protected.ok).lower()} state={protected.state} expected={expected} detail={protected.detail}"
        )
        if not protected.ok:
            exit_code = 1
        if args.expect_cloudflare_access and protected.state != "cloudflare_access_challenge":
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
