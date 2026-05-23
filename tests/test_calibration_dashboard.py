from __future__ import annotations

import hashlib
import json

from src.calibration_dashboard import calibration_artifact_status_rows


def test_calibration_artifact_status_rows_distinguish_baseline_hash_states(tmp_path):
    baseline = tmp_path / "calibration_10y_baseline_config.json"
    report = tmp_path / "calibration_10y_report.md"
    summary = tmp_path / "calibration_10y_summary.csv"
    candidates = tmp_path / "calibration_10y_candidates.csv"
    metadata = tmp_path / "calibration_10y_metadata.json"

    paths = {
        "baseline_config_path": baseline,
        "report_path": report,
        "summary_path": summary,
        "candidates_path": candidates,
        "metadata_path": metadata,
    }

    pending = calibration_artifact_status_rows(**paths, baseline_hash=None)
    assert pending[0] == {
        "Artifact": "Frozen baseline config",
        "Path": "docs/calibration_10y_baseline_config.json",
        "Status": "PENDING",
    }

    baseline.write_text(json.dumps({"ticket": "B-163"}), encoding="utf-8")
    unverified = calibration_artifact_status_rows(**paths, baseline_hash=None)
    assert unverified[0]["Status"] == "UNVERIFIED"

    expected_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
    report.write_text("# Calibration report", encoding="utf-8")
    verified = calibration_artifact_status_rows(**paths, baseline_hash=expected_hash)

    assert verified[0]["Status"] == "VERIFIED"
    assert verified[1] == {
        "Artifact": "Calibration report",
        "Path": "docs/calibration_10y_report.md",
        "Status": "READY",
    }
    assert verified[2]["Status"] == "PENDING"
