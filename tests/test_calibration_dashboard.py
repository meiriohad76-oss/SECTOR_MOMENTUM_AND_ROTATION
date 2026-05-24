from __future__ import annotations

import hashlib
import json

from src.calibration_dashboard import calibration_artifact_status_rows, shared_artifact_hash


def test_calibration_artifact_status_rows_distinguish_baseline_hash_states(tmp_path):
    baseline = tmp_path / "calibration_10y_baseline_config.json"
    report = tmp_path / "calibration_10y_report.md"
    summary = tmp_path / "calibration_10y_summary.csv"
    candidates = tmp_path / "calibration_10y_candidates.csv"
    candidate_config = tmp_path / "calibration_10y_candidate_config.json"
    metadata = tmp_path / "calibration_10y_metadata.json"

    paths = {
        "baseline_config_path": baseline,
        "report_path": report,
        "summary_path": summary,
        "candidates_path": candidates,
        "candidate_config_path": candidate_config,
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


def test_calibration_artifact_status_rows_verify_candidate_hash(tmp_path):
    baseline = tmp_path / "calibration_10y_baseline_config.json"
    report = tmp_path / "calibration_10y_report.md"
    summary = tmp_path / "calibration_10y_summary.csv"
    candidates = tmp_path / "calibration_10y_candidates.csv"
    candidate_config = tmp_path / "calibration_10y_candidate_config.json"
    metadata = tmp_path / "calibration_10y_metadata.json"
    candidates.write_text("candidate_id\nbaseline\n", encoding="utf-8")

    rows = calibration_artifact_status_rows(
        baseline_config_path=baseline,
        report_path=report,
        summary_path=summary,
        candidates_path=candidates,
        candidate_config_path=candidate_config,
        metadata_path=metadata,
        baseline_hash=None,
        candidates_hash="not-the-current-hash",
    )

    assert rows[3] == {
        "Artifact": "Calibration candidates",
        "Path": "docs/calibration_10y_candidates.csv",
        "Status": "UNVERIFIED",
    }

    expected_hash = hashlib.sha256(candidates.read_bytes()).hexdigest()
    verified = calibration_artifact_status_rows(
        baseline_config_path=baseline,
        report_path=report,
        summary_path=summary,
        candidates_path=candidates,
        candidate_config_path=candidate_config,
        metadata_path=metadata,
        baseline_hash=None,
        candidates_hash=expected_hash,
    )

    assert verified[3]["Status"] == "VERIFIED"


def test_calibration_artifact_status_rows_verify_candidate_config_hash(tmp_path):
    baseline = tmp_path / "calibration_10y_baseline_config.json"
    report = tmp_path / "calibration_10y_report.md"
    summary = tmp_path / "calibration_10y_summary.csv"
    candidates = tmp_path / "calibration_10y_candidates.csv"
    candidate_config = tmp_path / "calibration_10y_candidate_config.json"
    metadata = tmp_path / "calibration_10y_metadata.json"
    candidate_config.write_text(json.dumps({"slice": "B-163.7"}), encoding="utf-8")

    rows = calibration_artifact_status_rows(
        baseline_config_path=baseline,
        report_path=report,
        summary_path=summary,
        candidates_path=candidates,
        candidate_config_path=candidate_config,
        metadata_path=metadata,
        baseline_hash=None,
        candidate_config_hash="not-the-current-hash",
    )

    assert rows[4] == {
        "Artifact": "Calibrated candidate config",
        "Path": "docs/calibration_10y_candidate_config.json",
        "Status": "UNVERIFIED",
    }

    expected_hash = hashlib.sha256(candidate_config.read_bytes()).hexdigest()
    verified = calibration_artifact_status_rows(
        baseline_config_path=baseline,
        report_path=report,
        summary_path=summary,
        candidates_path=candidates,
        candidate_config_path=candidate_config,
        metadata_path=metadata,
        baseline_hash=None,
        candidate_config_hash=expected_hash,
    )

    assert verified[4]["Status"] == "VERIFIED"


def test_shared_artifact_hash_requires_both_metadata_hashes_to_agree():
    expected_hash = "a" * 64

    assert shared_artifact_hash(expected_hash, expected_hash) == expected_hash
    assert shared_artifact_hash(expected_hash, "b" * 64) == "__HASH_MISMATCH__"
    assert shared_artifact_hash(expected_hash, None) is None
    assert shared_artifact_hash(None, expected_hash) is None
