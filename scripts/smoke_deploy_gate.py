"""Content-aware deployment smoke gate for local and protected dashboard routes."""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.live_smoke import classify_local_dashboard_response, classify_protected_dashboard_response


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dashboard-url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--public-dashboard-url", default="")
    parser.add_argument("--expect-cloudflare-access", action="store_true")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    exit_code = 0
    status, _headers, body = _fetch(args.local_dashboard_url, args.timeout)
    local = classify_local_dashboard_response(status_code=status, text=body)
    print(f"local_dashboard_smoke ok={str(local.ok).lower()} state={local.state} detail={local.detail}")
    if not local.ok:
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
