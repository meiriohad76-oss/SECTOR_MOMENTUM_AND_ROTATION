from __future__ import annotations

import pandas as pd

from scripts import evaluate_evidence_gates


def test_evaluate_evidence_gates_script_writes_fail_closed_report(tmp_path, monkeypatch):
    fred_summary_path = tmp_path / "fred_macro_validation_summary.csv"
    massive_summary_path = tmp_path / "massive_provider_validation_summary.csv"
    report_path = tmp_path / "evidence_gate_report.md"
    fred_summary_path.write_text(
        "variant,promotion_label\n"
        "Curve falling defensive,needs more testing\n",
        encoding="utf-8",
    )
    massive_summary_path.write_text(
        "variant,promotion_label\n"
        "Massive aggregate OHLCV,needs more testing\n"
        "Block-trade upside ratio >= 1.25,do not promote\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluate_evidence_gates, "FRED_VALIDATION_SUMMARY_PATH", fred_summary_path)
    monkeypatch.setattr(evaluate_evidence_gates, "MASSIVE_VALIDATION_SUMMARY_PATH", massive_summary_path)
    monkeypatch.setattr(evaluate_evidence_gates, "EVIDENCE_GATE_REPORT_PATH", report_path)

    assert evaluate_evidence_gates.main([]) == 0

    report = report_path.read_text(encoding="utf-8")
    assert "B-158" in report
    assert "B-160" in report
    assert "blocked_no_candidates" in report
    assert "No candidate rows were present" in report
    assert "No live scoring" in report


def test_read_validation_summary_returns_empty_frame_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing.csv"

    summary = evaluate_evidence_gates._read_validation_summary(missing_path)

    assert isinstance(summary, pd.DataFrame)
    assert summary.empty


def test_path_label_uses_repo_relative_posix_paths():
    path = evaluate_evidence_gates.ROOT / "docs" / "fred_macro_validation_report.md"

    assert evaluate_evidence_gates._path_label(path) == "docs/fred_macro_validation_report.md"
