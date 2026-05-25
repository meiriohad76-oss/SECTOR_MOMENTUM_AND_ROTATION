"""Dashboard-safe artifact status helpers for calibration research."""
from __future__ import annotations

import hashlib
from pathlib import Path


def artifact_hash_matches(path: Path, expected_hash: str | None) -> bool:
    if not path.exists() or not expected_hash:
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash


def shared_artifact_hash(primary_hash: str | None, secondary_hash: str | None) -> str | None:
    if not primary_hash or not secondary_hash:
        return None
    if primary_hash != secondary_hash:
        return "__HASH_MISMATCH__"
    return primary_hash


def baseline_config_status(path: Path, expected_hash: str | None) -> str:
    if not path.exists():
        return "PENDING"
    if artifact_hash_matches(path, expected_hash):
        return "VERIFIED"
    return "UNVERIFIED"


def artifact_presence_status(path: Path) -> str:
    return "READY" if path.exists() else "PENDING"


def artifact_status(path: Path, expected_hash: str | None = None) -> str:
    if not path.exists():
        return "PENDING"
    if expected_hash is None:
        return "READY"
    return "VERIFIED" if artifact_hash_matches(path, expected_hash) else "UNVERIFIED"


def strict_artifact_status(path: Path, expected_hash: str | None = None) -> str:
    if not path.exists():
        return "PENDING"
    if not expected_hash:
        return "UNVERIFIED"
    return "VERIFIED" if artifact_hash_matches(path, expected_hash) else "UNVERIFIED"


def calibration_artifact_status_rows(
    *,
    baseline_config_path: Path,
    report_path: Path,
    summary_path: Path,
    candidates_path: Path,
    candidate_config_path: Path,
    metadata_path: Path,
    baseline_hash: str | None,
    report_hash: str | None = None,
    summary_hash: str | None = None,
    candidates_hash: str | None = None,
    candidate_config_hash: str | None = None,
    metadata_hash: str | None = None,
) -> list[dict[str, str]]:
    return [
        {
            "Artifact": "Frozen baseline config",
            "Path": "docs/calibration_10y_baseline_config.json",
            "Status": baseline_config_status(baseline_config_path, baseline_hash),
        },
        {
            "Artifact": "Calibration report",
            "Path": "docs/calibration_10y_report.md",
            "Status": artifact_status(report_path, report_hash),
        },
        {
            "Artifact": "Calibration summary",
            "Path": "docs/calibration_10y_summary.csv",
            "Status": artifact_status(summary_path, summary_hash),
        },
        {
            "Artifact": "Calibration candidates",
            "Path": "docs/calibration_10y_candidates.csv",
            "Status": artifact_status(candidates_path, candidates_hash),
        },
        {
            "Artifact": "Calibrated candidate config",
            "Path": "docs/calibration_10y_candidate_config.json",
            "Status": artifact_status(candidate_config_path, candidate_config_hash),
        },
        {
            "Artifact": "Calibration metadata",
            "Path": "docs/calibration_10y_metadata.json",
            "Status": artifact_status(metadata_path, metadata_hash),
        },
    ]


def expanded_calibration_artifact_status_rows(
    *,
    report_path: Path,
    candidates_path: Path,
    sector_overrides_path: Path,
    metadata_path: Path,
    report_hash: str | None = None,
    candidates_hash: str | None = None,
    sector_overrides_hash: str | None = None,
    metadata_hash: str | None = None,
) -> list[dict[str, str]]:
    return [
        {
            "Artifact": "Expanded calibration report",
            "Path": "docs/calibration_expanded_report.md",
            "Status": strict_artifact_status(report_path, report_hash),
        },
        {
            "Artifact": "Expanded calibration candidates",
            "Path": "docs/calibration_expanded_candidates.csv",
            "Status": strict_artifact_status(candidates_path, candidates_hash),
        },
        {
            "Artifact": "Sector/class overrides",
            "Path": "docs/calibration_sector_overrides.csv",
            "Status": strict_artifact_status(sector_overrides_path, sector_overrides_hash),
        },
        {
            "Artifact": "Expanded calibration metadata",
            "Path": "docs/calibration_expanded_metadata.json",
            "Status": strict_artifact_status(metadata_path, metadata_hash),
        },
    ]
