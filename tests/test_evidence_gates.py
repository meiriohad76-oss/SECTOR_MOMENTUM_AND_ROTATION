from __future__ import annotations

import pandas as pd

from src.evidence_gates import evaluate_promotion_gate, format_evidence_gate_report


def test_evidence_gate_blocks_when_no_candidates():
    summary = pd.DataFrame(
        [
            {"variant": "Curve falling defensive", "promotion_label": "needs more testing"},
            {"variant": "Stress rising defensive", "promotion_label": "do not promote"},
        ]
    )

    decision = evaluate_promotion_gate(
        ticket="B-158",
        source="FRED macro",
        summary=summary,
        validation_report_path="docs/fred_macro_validation_report.md",
    )

    assert decision.ticket == "B-158"
    assert decision.source == "FRED macro"
    assert decision.status == "blocked_no_candidates"
    assert decision.candidate_count == 0
    assert decision.candidate_variants == ()
    assert decision.rejected_variants == ("Curve falling defensive", "Stress rising defensive")
    assert decision.blockers == ("No candidate rows were present in the validation summary.",)
    assert decision.live_promotion_allowed is False


def test_evidence_gate_surfaces_candidates_for_review_without_auto_promotion():
    summary = pd.DataFrame(
        [
            {"variant": "Candidate macro rule", "promotion_label": "candidate"},
            {"variant": "Rejected macro rule", "promotion_label": "do not promote"},
        ]
    )

    decision = evaluate_promotion_gate(
        ticket="B-158",
        source="FRED macro",
        summary=summary,
        validation_report_path="docs/fred_macro_validation_report.md",
    )

    assert decision.status == "ready_for_review"
    assert decision.candidate_count == 1
    assert decision.candidate_variants == ("Candidate macro rule",)
    assert decision.rejected_variants == ("Rejected macro rule",)
    assert decision.blockers == ()
    assert decision.live_promotion_allowed is False


def test_evidence_gate_blocks_malformed_summary_without_promotion_label():
    summary = pd.DataFrame([{"variant": "Candidate-looking row"}])

    decision = evaluate_promotion_gate(
        ticket="B-160",
        source="Massive provider data",
        summary=summary,
        validation_report_path="docs/massive_provider_validation_report.md",
    )

    assert decision.status == "blocked_invalid_summary"
    assert decision.candidate_count == 0
    assert decision.blockers == ("Validation summary is missing required column: promotion_label.",)
    assert decision.live_promotion_allowed is False


def test_format_evidence_gate_report_documents_thresholds_and_rollback():
    fred = evaluate_promotion_gate(
        ticket="B-158",
        source="FRED macro",
        summary=pd.DataFrame([{"variant": "Curve falling defensive", "promotion_label": "needs more testing"}]),
        validation_report_path="docs/fred_macro_validation_report.md",
    )
    massive = evaluate_promotion_gate(
        ticket="B-160",
        source="Massive provider data",
        summary=pd.DataFrame([{"variant": "Massive aggregate OHLCV", "promotion_label": "candidate"}]),
        validation_report_path="docs/massive_provider_validation_report.md",
    )

    report = format_evidence_gate_report(
        [fred, massive],
        generated_at_utc="2026-05-22T12:00:00Z",
    )

    assert "# Evidence Gate Report" in report
    assert "Generated UTC: 2026-05-22T12:00:00Z" in report
    assert "B-158" in report
    assert "B-160" in report
    assert "docs/fred_macro_validation_report.md" in report
    assert "docs/massive_provider_validation_report.md" in report
    assert "blocked_no_candidates" in report
    assert "ready_for_review" in report
    assert "OOS Sharpe delta >= 0.10" in report
    assert "No live scoring, veto, alert, recommendation, broker, or Pillar 7 behavior changes are made by this report." in report
    assert "Rollback" in report
