from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.api_backtest_artifacts import build_backtest_artifacts_payload


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_backtest_artifacts_payload_reports_verified_manual_outputs(tmp_path):
    report_hash = _write(tmp_path / "docs" / "backtest_report.md", "# Backtest\n")
    equity_hash = _write(
        tmp_path / "docs" / "backtest_equity.csv",
        "date,methodology,equal_weight\n2026-01-01,1.0,0.9\n",
    )
    states_hash = _write(tmp_path / "docs" / "backtest_states.csv", "date,ticker,state\n2026-01-01,AAA,HOLD\n")
    _write(tmp_path / "docs" / "backtest_methodology_report.md", "# Methodology\n")
    (tmp_path / "docs" / "backtest_metadata.json").write_text(
        json.dumps(
            {
                "report_sha256": report_hash,
                "equity_sha256": equity_hash,
                "states_sha256": states_hash,
                "provider": "massive",
            }
        ),
        encoding="utf-8",
    )

    payload = build_backtest_artifacts_payload(root=tmp_path)

    assert payload["status"] == "ready"
    by_id = {row["id"]: row for row in payload["artifacts"]}
    assert by_id["report"]["status"] == "verified"
    assert by_id["equity"]["status"] == "verified"
    assert by_id["states"]["status"] == "verified"
    assert by_id["report"]["path"] == "docs/backtest_report.md"
    assert payload["report"]["text"].startswith("# Backtest")
    assert payload["report"]["methodology_text"].startswith("# Methodology")
    assert payload["equity"]["row_count"] == 1
    assert payload["equity"]["rows"][0]["methodology"] == 1.0
    assert payload["metadata"]["provider"] == "massive"


def test_backtest_artifacts_payload_fails_closed_for_missing_required_outputs(tmp_path):
    payload = build_backtest_artifacts_payload(root=tmp_path)

    assert payload["status"] == "missing"
    by_id = {row["id"]: row for row in payload["artifacts"]}
    assert by_id["report"]["status"] == "missing"
    assert by_id["equity"]["status"] == "missing"
    assert payload["equity"]["rows"] == []


def test_backtest_artifacts_payload_marks_hash_mismatch_unverified(tmp_path):
    _write(tmp_path / "docs" / "backtest_report.md", "# Backtest\n")
    _write(tmp_path / "docs" / "backtest_equity.csv", "date,methodology\n2026-01-01,1.0\n")
    (tmp_path / "docs" / "backtest_metadata.json").write_text(
        json.dumps({"report_sha256": "0" * 64, "equity_sha256": "1" * 64}),
        encoding="utf-8",
    )

    payload = build_backtest_artifacts_payload(root=tmp_path)

    assert payload["status"] == "unverified"
    by_id = {row["id"]: row for row in payload["artifacts"]}
    assert by_id["report"]["status"] == "unverified"
    assert by_id["equity"]["status"] == "unverified"
