from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_surfaces_calibration_artifacts_without_running_calibration():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        'CALIBRATION_BASELINE_CONFIG_PATH = APP_ROOT / "docs" / '
        '"calibration_10y_baseline_config.json"'
    ) in app_source
    assert 'CALIBRATION_REPORT_PATH = APP_ROOT / "docs" / "calibration_10y_report.md"' in app_source
    assert 'CALIBRATION_SUMMARY_PATH = APP_ROOT / "docs" / "calibration_10y_summary.csv"' in app_source
    assert (
        'CALIBRATION_CANDIDATES_PATH = APP_ROOT / "docs" / '
        '"calibration_10y_candidates.csv"'
    ) in app_source
    assert (
        'CALIBRATION_CANDIDATE_CONFIG_PATH = APP_ROOT / "docs" / '
        '"calibration_10y_candidate_config.json"'
    ) in app_source
    assert (
        'CALIBRATION_METADATA_PATH = APP_ROOT / "docs" / '
        '"calibration_10y_metadata.json"'
    ) in app_source
    assert 'CALIBRATION_EXPANDED_REPORT_PATH = APP_ROOT / "docs" / "calibration_expanded_report.md"' in app_source
    assert (
        'CALIBRATION_EXPANDED_CANDIDATES_PATH = APP_ROOT / "docs" / '
        '"calibration_expanded_candidates.csv"'
    ) in app_source
    assert (
        'CALIBRATION_SECTOR_OVERRIDES_PATH = APP_ROOT / "docs" / '
        '"calibration_sector_overrides.csv"'
    ) in app_source
    assert (
        'CALIBRATION_EXPANDED_METADATA_PATH = APP_ROOT / "docs" / '
        '"calibration_expanded_metadata.json"'
    ) in app_source
    assert "def render_calibration_lab():" in app_source
    assert "Calibration lab" in app_source
    assert "Expanded calibration" in app_source
    assert "sector-specific" in app_source
    assert "B-163" in app_source
    assert (
        "from src.calibration_dashboard import ("
        in app_source
        and "calibration_artifact_status_rows"
        in app_source
        and "expanded_calibration_artifact_status_rows"
        in app_source
        and "shared_artifact_hash"
        in app_source
    )
    assert "baseline_config_exists = CALIBRATION_BASELINE_CONFIG_PATH.exists()" in app_source
    assert "calibration_artifact_status_rows(" in app_source
    assert "candidate_config_hash = shared_artifact_hash(" in app_source
    assert 'baseline_status = status_rows[0]["Status"]' in app_source
    assert 'baseline_verified = baseline_status == "VERIFIED"' in app_source
    assert 'candidate_status = status_rows[3]["Status"]' in app_source
    assert 'candidate_config_status = status_rows[4]["Status"]' in app_source
    assert 'metadata_status = status_rows[5]["Status"]' in app_source
    assert 'metadata_status == "VERIFIED"' in app_source
    assert 'candidate_status == "VERIFIED"' in app_source
    assert 'candidate_config_status == "VERIFIED"' in app_source
    assert "history_window_status" in app_source
    assert "Minimum accepted" in app_source
    assert "Effective calibration" in app_source
    assert "Hash status" in app_source
    assert "UNVERIFIED" in app_source
    assert "_read_csv_artifact(CALIBRATION_SUMMARY_PATH)" in app_source
    assert "_read_csv_artifact(CALIBRATION_CANDIDATES_PATH)" in app_source
    assert "CALIBRATION_CANDIDATE_CONFIG_PATH.read_text" in app_source
    assert "CALIBRATION_REPORT_PATH.read_text" in app_source
    assert "CALIBRATION_EXPANDED_REPORT_PATH.read_text" in app_source
    assert 'expanded_metadata_hash = metadata.get("calibration_expanded_metadata_sha256")' in app_source
    assert "expanded_report_status == \"VERIFIED\"" in app_source
    assert "_read_csv_artifact(CALIBRATION_EXPANDED_CANDIDATES_PATH)" in app_source
    assert "_read_csv_artifact(CALIBRATION_SECTOR_OVERRIDES_PATH)" in app_source
    assert "CALIBRATION_BASELINE_CONFIG_PATH" in app_source
    assert "calibration_label_metrics(" not in app_source
    assert "calibration_candidate_search(" not in app_source
    assert "run_backtest.main(" not in app_source


def test_calibration_lab_renders_between_backtest_and_evidence_gates():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    render_order = [
        '_render_timed("render_backtest_lab", render_backtest_lab)',
        '_render_timed("render_calibration_lab", render_calibration_lab)',
        '_render_timed("render_evidence_gate_lab", render_evidence_gate_lab)',
        '_render_timed("render_debrief_lab", render_debrief_lab)',
    ]
    positions = [app_source.index(call) for call in render_order]

    assert positions == sorted(positions)
