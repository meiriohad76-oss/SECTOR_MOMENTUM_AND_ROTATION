"""Serve read-only dashboard API payloads for local Next screenshot QA.

This helper exists so B-170 browser QA can run even on a workstation where the
optional FastAPI dependency is not installed. It uses the same pure payload
builders as `src.api_server` and never imports Streamlit or fetches providers.
Production API deployment should still use `uvicorn src.api_server:create_app`.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import uuid
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api_dashboard_snapshot import build_latest_dashboard_snapshot_payload  # noqa: E402
from src.api_data_health import build_provider_data_health_payload  # noqa: E402
from src.api_status import build_persisted_status_payload  # noqa: E402


PILLAR_KEYS_FOR_NEXT_QA = {
    "breadth_50d",
    "cmf21",
    "cycle_tilt",
    "mansfield_rs",
    "mom_12_1",
    "rs_momentum",
    "rs_ratio",
}

PAYLOAD_KEYS_FOR_NEXT_QA = {
    "above_30wma",
    "antonacci",
    "etf_flow_5d_pct",
    "faber",
    "ma_slope_pos",
    "obv_divergence",
    "rank_in_class",
    "stage",
}


def _compact_snapshot_payload(payload: dict) -> dict:
    """Keep the QA payload strict and small while preserving the Next UI contract."""

    def compact_row(row: dict, *, include_payload: bool = False) -> dict:
        compact = dict(row)
        pillars = compact.get("pillar_scores")
        if isinstance(pillars, dict):
            compact["pillar_scores"] = {
                key: pillars.get(key)
                for key in sorted(PILLAR_KEYS_FOR_NEXT_QA)
                if key in pillars
            }
        row_payload = compact.get("payload") if include_payload else {}
        if include_payload and isinstance(row_payload, dict):
            compact["payload"] = {
                key: row_payload.get(key)
                for key in sorted(PAYLOAD_KEYS_FOR_NEXT_QA)
                if key in row_payload
            }
        else:
            compact["payload"] = {}
        return compact

    def compact_rows(rows: object, limit: int | None = None) -> list[dict]:
        if not isinstance(rows, list):
            return []
        compacted = [compact_row(dict(row)) for row in rows if isinstance(row, dict)]
        return compacted[:limit] if limit is not None else compacted

    compact = dict(payload)
    compact["rows"] = compact_rows(payload.get("rows"), limit=90)
    compact["focus"] = compact_row(dict(payload["focus"]), include_payload=True) if isinstance(payload.get("focus"), dict) else None
    compact["decisions"] = [
        {**dict(row), "payload": {}}
        for row in payload.get("decisions", [])
        if isinstance(row, dict)
    ][:12]
    screens = dict(payload.get("screens", {}) or {})
    overview = dict(screens.get("overview", {}) or {})
    overview["leaders"] = compact_rows(overview.get("leaders"), limit=1)
    overview["risks"] = compact_rows(overview.get("risks"), limit=1)
    overview["actions"] = compact["decisions"][:8]
    deepdive = dict(screens.get("deepdive", {}) or {})
    deepdive["focus"] = compact["focus"]
    deepdive["peer_rows"] = []
    rotation = dict(screens.get("rotation", {}) or {})
    rotation["sectors"] = compact_rows(rotation.get("sectors"), limit=20)
    rotation["leaders"] = []
    rotation["laggards"] = []
    compact["screens"] = {"overview": overview, "deepdive": deepdive, "rotation": rotation}
    return compact


class NextQaApiHandler(BaseHTTPRequestHandler):
    server_version = "NextQaApi/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - stdlib signature
        return

    def _write_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urlparse(self.path)
        if parsed.path in {"/api/v1/health", "/api/v1/status"}:
            self._write_json(200, build_persisted_status_payload())
            return
        if parsed.path in {"/api/v1/data-health", "/api/v1/provider-health"}:
            payload = build_provider_data_health_payload()
            if parsed.path == "/api/v1/provider-health":
                payload = {
                    **payload,
                    "lanes": [
                        lane
                        for lane in payload.get("lanes", [])
                        if str(lane.get("lane_id", "")).startswith("provider_")
                    ],
                }
            self._write_json(200, payload)
            return
        if parsed.path == "/api/v1/dashboard-snapshot":
            query = parse_qs(parsed.query)
            ticker = (query.get("ticker") or [None])[0]
            payload = build_latest_dashboard_snapshot_payload(focus_ticker=ticker)
            self._write_json(200, _compact_snapshot_payload(payload))
            return
        # Refresh job status poll — return "succeeded" immediately so the
        # Server Action completes and revalidates the page without waiting.
        if parsed.path.startswith("/api/v1/refresh/"):
            job_id = parsed.path.split("/api/v1/refresh/", 1)[1].strip("/")
            self._write_json(200, {
                "job_id": job_id,
                "lane_id": "all",
                "status": "succeeded",
                "progress_pct": 100,
                "message": "QA stub: refresh complete (read persisted data from disk)",
                "error": "",
                "status_url": f"/api/v1/refresh/{job_id}",
                "events_url": f"/api/v1/refresh/{job_id}/events",
            })
            return
        self._write_json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        """Handle POST /api/v1/refresh — return a stub job so the RefreshButton works locally."""
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/refresh":
            # Read and discard request body
            length = int(self.headers.get("Content-Length", 0))
            if length:
                self.rfile.read(length)
            job_id = uuid.uuid4().hex
            self._write_json(202, {
                "job_id": job_id,
                "lane_id": "all",
                "status": "queued",
                "progress_pct": 0,
                "message": "QA stub: refresh queued (no live provider fetch in QA mode)",
                "error": "",
                "status_url": f"/api/v1/refresh/{job_id}",
                "events_url": f"/api/v1/refresh/{job_id}/events",
            })
            return
        self._write_json(404, {"detail": "not found"})

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib signature
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), NextQaApiHandler)
    print(f"next_qa_api=serving host={args.host} port={args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
