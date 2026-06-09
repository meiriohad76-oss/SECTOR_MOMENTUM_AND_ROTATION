from __future__ import annotations

import json
from pathlib import Path

from scripts import check_b170_retirement_readiness as readiness


def _write_qa_reports(path: Path, *, ok: bool = True, similarity: float = 0.86) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for filename in readiness.PROFILE_REPORTS.values():
        (path / filename).write_text(
            json.dumps(
                {
                    "screens": [
                        {
                            "screen": "overview",
                            "ok": ok,
                            "similarity": similarity,
                            "missing_text": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )


def test_b170_retirement_readiness_report_passes_with_local_evidence(tmp_path, monkeypatch):
    qa_dir = tmp_path / "qa"
    _write_qa_reports(qa_dir)

    def fake_fetch_json(url: str, timeout: float):
        if url.endswith("/api/v1/dashboard-snapshot?ticker=XLK"):
            return True, {
                "summary": {"universe_count": 2},
                "rows": [
                    {
                        "ticker": "XLK",
                        "s_score": 0.5,
                        "f_score": 0.1,
                        "state": "STAGE_2_BULLISH",
                        "quadrant": "Leading",
                        "cmf21": 0.07,
                        "momentum_pct": 0.2,
                    },
                    {"ticker": "XLE"},
                ],
            }, "ok"
        return True, {"ok": True}, "ok"

    monkeypatch.setattr(readiness, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(readiness, "_fetch_text", lambda url, timeout: (200, "dashboard"))

    report = readiness.build_readiness_report(
        api_base_url="http://127.0.0.1:8000",
        next_url="http://127.0.0.1:3000/?presentation=c",
        streamlit_url="http://127.0.0.1:8501/?ticker=XLK",
        qa_dir=qa_dir,
        selected_ticker="XLK",
        min_rows=2,
        min_similarity=0.8,
        timeout=1,
    )

    assert report["ok"] is True
    assert report["data_parity"]["selected_row_fields"]["ticker"] == "XLK"
    assert report["visual_parity"]["profiles"]["a"]["ok"] is True
    assert report["notes"]["no_provider_calls"] is True


def test_b170_retirement_readiness_fails_closed_when_visual_evidence_missing(tmp_path, monkeypatch):
    qa_dir = tmp_path / "missing-qa"
    monkeypatch.setattr(readiness, "_fetch_json", lambda url, timeout: (True, {"rows": [{"ticker": "XLK"}]}, "ok"))
    monkeypatch.setattr(readiness, "_fetch_text", lambda url, timeout: (200, "dashboard"))

    report = readiness.build_readiness_report(
        api_base_url="http://127.0.0.1:8000",
        next_url="http://127.0.0.1:3000/?presentation=c",
        streamlit_url="http://127.0.0.1:8501/?ticker=XLK",
        qa_dir=qa_dir,
        selected_ticker="XLK",
        min_rows=1,
        min_similarity=0.0,
        timeout=1,
    )

    assert report["ok"] is False
    assert report["visual_parity"]["ok"] is False
    assert report["visual_parity"]["profiles"]["a"]["detail"] == "missing_report"


def test_b170_retirement_readiness_cli_returns_nonzero_for_failed_gate(tmp_path, monkeypatch, capsys):
    qa_dir = tmp_path / "qa"
    _write_qa_reports(qa_dir, similarity=0.5)
    monkeypatch.setattr(readiness, "_fetch_json", lambda url, timeout: (True, {"rows": [{"ticker": "XLK"}]}, "ok"))
    monkeypatch.setattr(readiness, "_fetch_text", lambda url, timeout: (200, "dashboard"))

    exit_code = readiness.main(["--qa-dir", str(qa_dir), "--min-similarity", "0.8"])
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "b170_visual_parity ok=false" in captured


def test_b170_retirement_readiness_is_referenced_by_deploy_docs():
    root = Path(__file__).resolve().parent.parent
    pi_docs = (root / "docs" / "DEPLOY_RASPBERRY_PI.md").read_text(encoding="utf-8")
    cloudflare_docs = (root / "docs" / "DEPLOY_CLOUDFLARE_TUNNEL.md").read_text(encoding="utf-8")

    assert "scripts/check_b170_retirement_readiness.py" in pi_docs
    assert "scripts/check_b170_retirement_readiness.py" in cloudflare_docs
