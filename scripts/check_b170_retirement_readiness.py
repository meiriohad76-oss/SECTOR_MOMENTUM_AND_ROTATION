"""Check B-170 Streamlit-to-Next retirement readiness without provider calls."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QA_DIR = ROOT / "docs" / "browser-qa" / "next-handoff" / "latest"
PROFILE_REPORTS = {
    "a": "next_handoff_qa_report_a.json",
    "b": "next_handoff_qa_report_b.json",
    "c": "next_handoff_qa_report.json",
}


def _fetch_text(url: str, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "b170-retirement-readiness/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def _fetch_json(url: str, timeout: float) -> tuple[bool, dict[str, Any], str]:
    status, body = _fetch_text(url, timeout)
    if status != 200:
        return False, {}, f"http_status={status}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return False, {}, f"json_error={exc.__class__.__name__}"
    if not isinstance(payload, dict):
        return False, {}, "json_error=not_object"
    return True, payload, "ok"


def _snapshot_row_count(payload: dict[str, Any]) -> int:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return len(rows)
    summary = payload.get("summary")
    if isinstance(summary, dict):
        count = summary.get("universe_count")
        if isinstance(count, int):
            return count
    return 0


def _selected_ticker_payload(payload: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and str(row.get("ticker", "")).upper() == ticker.upper():
            return row
    return None


def _qa_profile_status(path: Path, min_similarity: float) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "detail": "missing_report",
            "screens": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "path": str(path),
            "detail": f"unreadable_report:{exc.__class__.__name__}",
            "screens": [],
        }
    screens = payload.get("screens", [])
    if not isinstance(screens, list) or not screens:
        return {
            "ok": False,
            "path": str(path),
            "detail": "no_screens",
            "screens": [],
        }
    normalized = []
    ok = True
    details = []
    for screen in screens:
        if not isinstance(screen, dict):
            ok = False
            details.append("invalid_screen")
            continue
        similarity = screen.get("similarity")
        screen_ok = bool(screen.get("ok"))
        missing = screen.get("missing_text") or []
        if not screen_ok:
            ok = False
            details.append(f"{screen.get('screen', 'unknown')}:not_ok")
        if isinstance(missing, list) and missing:
            ok = False
            details.append(f"{screen.get('screen', 'unknown')}:missing_text")
        if isinstance(similarity, (int, float)) and similarity < min_similarity:
            ok = False
            details.append(f"{screen.get('screen', 'unknown')}:similarity<{min_similarity}")
        normalized.append(
            {
                "screen": screen.get("screen", "unknown"),
                "ok": screen_ok,
                "similarity": similarity,
                "missing_text": missing,
            }
        )
    return {
        "ok": ok,
        "path": str(path),
        "detail": "ok" if ok else ",".join(details),
        "screens": normalized,
    }


def build_readiness_report(
    *,
    api_base_url: str,
    next_url: str,
    streamlit_url: str,
    qa_dir: Path,
    selected_ticker: str,
    min_rows: int,
    min_similarity: float,
    timeout: float,
) -> dict[str, Any]:
    api_base = api_base_url.rstrip("/")
    health_ok, health_payload, health_detail = _fetch_json(f"{api_base}/api/v1/health", timeout)
    data_ok, data_payload, data_detail = _fetch_json(f"{api_base}/api/v1/data-health", timeout)
    provider_ok, provider_payload, provider_detail = _fetch_json(f"{api_base}/api/v1/provider-health", timeout)
    snapshot_ok, snapshot_payload, snapshot_detail = _fetch_json(
        f"{api_base}/api/v1/dashboard-snapshot?ticker={selected_ticker}",
        timeout,
    )
    row_count = _snapshot_row_count(snapshot_payload)
    selected_row = _selected_ticker_payload(snapshot_payload, selected_ticker)

    next_status, next_body = _fetch_text(next_url, timeout)
    streamlit_status, streamlit_body = _fetch_text(streamlit_url, timeout)
    qa_profiles = {
        profile: _qa_profile_status(qa_dir / filename, min_similarity)
        for profile, filename in PROFILE_REPORTS.items()
    }

    feature_ok = next_status == 200 and snapshot_ok and row_count >= min_rows and selected_row is not None
    data_ok_all = all((health_ok, data_ok, provider_ok, snapshot_ok)) and row_count >= min_rows and selected_row is not None
    visual_ok = all(profile["ok"] for profile in qa_profiles.values())
    operational_ok = next_status == 200 and streamlit_status == 200 and health_ok
    rollback_ok = streamlit_status == 200
    overall_ok = all((feature_ok, data_ok_all, visual_ok, operational_ok, rollback_ok))

    return {
        "ok": overall_ok,
        "feature_parity": {
            "ok": feature_ok,
            "next_status": next_status,
            "row_count": row_count,
            "selected_ticker_present": selected_row is not None,
        },
        "data_parity": {
            "ok": data_ok_all,
            "health": health_detail,
            "data_health": data_detail,
            "provider_health": provider_detail,
            "snapshot": snapshot_detail,
            "row_count": row_count,
            "selected_ticker": selected_ticker,
            "selected_row_fields": {
                key: selected_row.get(key) if isinstance(selected_row, dict) else None
                for key in ("ticker", "s_score", "f_score", "state", "quadrant", "cmf21", "momentum_pct")
            },
        },
        "visual_parity": {
            "ok": visual_ok,
            "min_similarity": min_similarity,
            "profiles": qa_profiles,
        },
        "operational_parity": {
            "ok": operational_ok,
            "api_health_ok": health_ok,
            "next_status": next_status,
            "streamlit_status": streamlit_status,
        },
        "rollback": {
            "ok": rollback_ok,
            "streamlit_status": streamlit_status,
        },
        "notes": {
            "next_body_sample": next_body[:80],
            "streamlit_body_sample": streamlit_body[:80],
            "no_provider_calls": True,
        },
    }


def _print_line(name: str, payload: dict[str, Any]) -> None:
    detail = " ".join(f"{key}={value}" for key, value in payload.items() if key != "ok")
    print(f"b170_{name} ok={str(bool(payload.get('ok'))).lower()} {detail}".rstrip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--next-url", default="http://127.0.0.1:3000/?presentation=c")
    parser.add_argument("--streamlit-url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--qa-dir", type=Path, default=DEFAULT_QA_DIR)
    parser.add_argument("--selected-ticker", default="XLK")
    parser.add_argument("--min-rows", type=int, default=1)
    parser.add_argument("--min-similarity", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true", help="Print the full JSON report after summary lines.")
    args = parser.parse_args(argv)

    report = build_readiness_report(
        api_base_url=args.api_base_url,
        next_url=args.next_url,
        streamlit_url=args.streamlit_url,
        qa_dir=args.qa_dir,
        selected_ticker=args.selected_ticker,
        min_rows=args.min_rows,
        min_similarity=args.min_similarity,
        timeout=args.timeout,
    )

    _print_line("feature_parity", report["feature_parity"])
    _print_line("data_parity", report["data_parity"])
    _print_line("visual_parity", {"ok": report["visual_parity"]["ok"], "min_similarity": args.min_similarity})
    _print_line("operational_parity", report["operational_parity"])
    _print_line("rollback", report["rollback"])
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
