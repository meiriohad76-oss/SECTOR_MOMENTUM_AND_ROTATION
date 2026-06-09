"""Read-only backtest artifact payloads for the B-170 API migration."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent

ARTIFACTS = {
    "report": ("Backtest summary report", "docs/backtest_report.md", "report_sha256"),
    "methodology_report": ("Methodology narrative report", "docs/backtest_methodology_report.md", None),
    "equity": ("Equity curve CSV", "docs/backtest_equity.csv", "equity_sha256"),
    "states": ("Methodology states CSV", "docs/backtest_states.csv", "states_sha256"),
    "metadata": ("Backtest metadata", "docs/backtest_metadata.json", None),
}


def build_backtest_artifacts_payload(*, root: Path | None = None) -> dict[str, Any]:
    """Return existing manual backtest artifacts without running research jobs."""

    base = root or ROOT
    metadata_path = base / "docs" / "backtest_metadata.json"
    metadata = _read_json(metadata_path)
    artifact_rows = [
        _artifact_status(base, artifact_id, label, relative_path, metadata, hash_key)
        for artifact_id, (label, relative_path, hash_key) in ARTIFACTS.items()
    ]
    report_path = base / "docs" / "backtest_report.md"
    methodology_report_path = base / "docs" / "backtest_methodology_report.md"
    equity_path = base / "docs" / "backtest_equity.csv"
    missing_required = [
        row["id"]
        for row in artifact_rows
        if row["id"] in {"report", "equity", "metadata"} and not row["exists"]
    ]
    unverified_required = [
        row["id"]
        for row in artifact_rows
        if row["id"] in {"report", "equity"} and row["status"] == "unverified"
    ]
    if missing_required:
        status = "missing"
        message = "Required backtest artifacts are missing."
    elif unverified_required:
        status = "unverified"
        message = "Backtest artifacts exist, but one or more hashes do not match metadata."
    else:
        status = "ready"
        message = "Backtest artifacts are available from disk."

    return {
        "api_version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "message": message,
        "artifacts": artifact_rows,
        "report": {
            "text": _read_text(report_path),
            "methodology_text": _read_text(methodology_report_path),
        },
        "equity": _equity_payload(equity_path),
        "metadata": metadata,
    }


def _artifact_status(
    base: Path,
    artifact_id: str,
    label: str,
    relative_path: str,
    metadata: Mapping[str, Any],
    hash_key: str | None,
) -> dict[str, Any]:
    path = base / relative_path
    exists = path.exists()
    digest = _sha256(path) if exists else ""
    expected = str(metadata.get(hash_key) or "") if hash_key else ""
    if not exists:
        status = "missing"
    elif expected and digest != expected:
        status = "unverified"
    elif expected:
        status = "verified"
    else:
        status = "present"
    return {
        "id": artifact_id,
        "label": label,
        "path": relative_path.replace("\\", "/"),
        "exists": exists,
        "status": status,
        "bytes": path.stat().st_size if exists else 0,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if exists else "",
        "sha256": digest,
        "expected_sha256": expected,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _equity_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"row_count": 0, "columns": [], "rows": []}
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return {"row_count": 0, "columns": [], "rows": []}
    rows = [
        {str(key): _json_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    return {"row_count": len(rows), "columns": [str(column) for column in frame.columns], "rows": rows}


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
