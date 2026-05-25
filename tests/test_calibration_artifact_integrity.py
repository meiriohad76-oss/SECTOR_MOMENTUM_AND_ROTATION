from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_committed_calibration_candidate_config_matches_both_metadata_hashes():
    candidate_config_path = ROOT / "docs" / "calibration_10y_candidate_config.json"
    backtest_metadata = json.loads((ROOT / "docs" / "backtest_metadata.json").read_text(encoding="utf-8"))
    calibration_metadata = json.loads(
        (ROOT / "docs" / "calibration_10y_metadata.json").read_text(encoding="utf-8")
    )
    candidate_config = json.loads(candidate_config_path.read_text(encoding="utf-8"))

    candidate_hash = hashlib.sha256(candidate_config_path.read_bytes()).hexdigest()

    assert candidate_hash == backtest_metadata["calibration_10y_candidate_config_sha256"]
    assert candidate_hash == calibration_metadata["candidate_config_sha256"]
    assert candidate_config["calibration_split_summary"] == calibration_metadata[
        "calibration_split_summary"
    ]
    assert candidate_config["config_status"] == calibration_metadata["candidate_config_status"]
    assert candidate_config["live_promotion_allowed"] is False
    final_holdout_status = str(candidate_config["config_status"])
    if final_holdout_status.startswith(
        ("passed_final_holdout", "rejected_final_holdout")
    ) and final_holdout_status != "rejected_final_holdout_no_data":
        assert candidate_config["final_holdout_evaluated"] is True
        assert candidate_config["final_holdout_rows_used"] > 0
    else:
        assert candidate_config["final_holdout_evaluated"] is False
