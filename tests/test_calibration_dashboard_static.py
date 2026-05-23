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
        'CALIBRATION_METADATA_PATH = APP_ROOT / "docs" / '
        '"calibration_10y_metadata.json"'
    ) in app_source
    assert "def render_calibration_lab():" in app_source
    assert "Calibration lab" in app_source
    assert "B-163" in app_source
    assert "baseline_config_exists = CALIBRATION_BASELINE_CONFIG_PATH.exists()" in app_source
    assert "baseline_verified = bool(baseline_hash) and _artifact_hash_matches(" in app_source
    assert "Hash status" in app_source
    assert "UNVERIFIED" in app_source
    assert "_read_csv_artifact(CALIBRATION_SUMMARY_PATH)" in app_source
    assert "_read_csv_artifact(CALIBRATION_CANDIDATES_PATH)" in app_source
    assert "CALIBRATION_REPORT_PATH.read_text" in app_source
    assert "CALIBRATION_BASELINE_CONFIG_PATH" in app_source
    assert "calibration_label_metrics(" not in app_source
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
