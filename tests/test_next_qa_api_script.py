from __future__ import annotations

from scripts import serve_next_qa_api


class _HandlerProbe(serve_next_qa_api.NextQaApiHandler):
    def __init__(self, path: str):
        self.path = path
        self.payload = None
        self.status = None

    def _write_json(self, status: int, payload: dict) -> None:
        self.status = status
        self.payload = payload


def test_next_qa_api_serves_read_only_health_payload(monkeypatch):
    monkeypatch.setattr(serve_next_qa_api, "build_persisted_status_payload", lambda: {"kind": "health"})

    handler = _HandlerProbe("/api/v1/health")
    handler.do_GET()

    assert handler.status == 200
    assert handler.payload == {"kind": "health"}


def test_next_qa_api_serves_dashboard_snapshot_with_ticker(monkeypatch):
    calls = []

    def snapshot(**kwargs):
        calls.append(kwargs)
        return {"kind": "snapshot"}

    monkeypatch.setattr(serve_next_qa_api, "build_latest_dashboard_snapshot_payload", snapshot)

    handler = _HandlerProbe("/api/v1/dashboard-snapshot?ticker=XLK")
    handler.do_GET()

    assert handler.status == 200
    assert handler.payload["kind"] == "snapshot"
    assert handler.payload["rows"] == []
    assert handler.payload["screens"] == {"overview": {"leaders": [], "risks": [], "actions": []}, "deepdive": {"focus": None, "peer_rows": []}, "rotation": {"sectors": [], "leaders": [], "laggards": []}}
    assert calls == [{"focus_ticker": "XLK"}]


def test_next_qa_api_compacts_snapshot_payload_for_browser_transport():
    payload = {
        "rows": [
            {
                "ticker": "XLK",
                "pillar_scores": {"mom_12_1": 1.0, "rs_ratio": 101, "large_blob": "x" * 100},
                "payload": {"raw": "x" * 1000},
            }
        ]
        * 40,
        "focus": {
            "ticker": "XLK",
            "pillar_scores": {"cmf21": 0.1, "ignored": 9},
            "payload": {"raw": "x"},
        },
        "decisions": [{"ticker": "XLK", "payload": {"raw": "x"}}],
        "screens": {
            "overview": {"leaders": [], "risks": []},
            "deepdive": {"peer_rows": []},
            "rotation": {"sectors": [], "leaders": [], "laggards": []},
        },
    }

    compact = serve_next_qa_api._compact_snapshot_payload(payload)

    assert compact["rows"][0]["payload"] == {}
    assert compact["decisions"][0]["payload"] == {}
    assert compact["rows"][0]["pillar_scores"] == {"mom_12_1": 1.0, "rs_ratio": 101}
    assert compact["focus"]["pillar_scores"] == {"cmf21": 0.1}
    assert len(compact["rows"]) == 20


def test_next_qa_api_provider_health_filters_provider_lanes(monkeypatch):
    monkeypatch.setattr(
        serve_next_qa_api,
        "build_provider_data_health_payload",
        lambda: {"lanes": [{"lane_id": "provider_flow"}, {"lane_id": "market_ohlcv"}]},
    )

    handler = _HandlerProbe("/api/v1/provider-health")
    handler.do_GET()

    assert handler.status == 200
    assert handler.payload == {"lanes": [{"lane_id": "provider_flow"}]}


def test_next_qa_api_is_not_imported_by_production_app():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    app_source = (root / "app.py").read_text(encoding="utf-8")
    api_source = (root / "src" / "api_server.py").read_text(encoding="utf-8")

    assert "serve_next_qa_api" not in app_source
    assert "serve_next_qa_api" not in api_source
