"""Fail-closed promotion evidence gates for research validation reports.

This module only evaluates already-generated validation summaries. It does not
fetch provider data and it does not change live scoring, alerts, or recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


CANDIDATE_LABEL = "candidate"
PROMOTION_CRITERIA = (
    "at least 20 active out-of-sample rebalances",
    "OOS Sharpe delta >= 0.10",
    "OOS CAGR delta >= 0",
    "OOS drawdown delta >= 0",
    "full-period Sharpe delta >= 0",
)


@dataclass(frozen=True)
class PromotionGateDecision:
    ticket: str
    source: str
    status: str
    validation_report_path: str
    candidate_count: int
    candidate_variants: tuple[str, ...]
    rejected_variants: tuple[str, ...]
    blockers: tuple[str, ...]
    live_promotion_allowed: bool = False


def _variant_name(row: pd.Series, fallback: str) -> str:
    for key in ("variant", "rule", "series_id", "provider"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


def _variant_names(frame: pd.DataFrame) -> tuple[str, ...]:
    return tuple(_variant_name(row, f"row {idx}") for idx, row in frame.iterrows())


def evaluate_promotion_gate(
    *,
    ticket: str,
    source: str,
    summary: pd.DataFrame,
    validation_report_path: str,
) -> PromotionGateDecision:
    if "promotion_label" not in summary.columns:
        return PromotionGateDecision(
            ticket=str(ticket),
            source=str(source),
            status="blocked_invalid_summary",
            validation_report_path=str(validation_report_path),
            candidate_count=0,
            candidate_variants=(),
            rejected_variants=(),
            blockers=("Validation summary is missing required column: promotion_label.",),
        )

    labels = summary["promotion_label"].fillna("").astype(str).str.strip().str.lower()
    candidate_rows = summary[labels == CANDIDATE_LABEL]
    rejected_rows = summary[labels != CANDIDATE_LABEL]
    candidate_variants = _variant_names(candidate_rows)
    rejected_variants = _variant_names(rejected_rows)
    if not candidate_variants:
        return PromotionGateDecision(
            ticket=str(ticket),
            source=str(source),
            status="blocked_no_candidates",
            validation_report_path=str(validation_report_path),
            candidate_count=0,
            candidate_variants=(),
            rejected_variants=rejected_variants,
            blockers=("No candidate rows were present in the validation summary.",),
        )
    return PromotionGateDecision(
        ticket=str(ticket),
        source=str(source),
        status="ready_for_review",
        validation_report_path=str(validation_report_path),
        candidate_count=len(candidate_variants),
        candidate_variants=candidate_variants,
        rejected_variants=rejected_variants,
        blockers=(),
    )


def _csv_list(values: Iterable[str]) -> str:
    items = [str(value) for value in values if str(value).strip()]
    return ", ".join(items) if items else "-"


def promotion_gate_decisions_frame(decisions: Iterable[PromotionGateDecision]) -> pd.DataFrame:
    """Return dashboard-safe promotion gate rows without enabling live promotion."""
    rows = [
        {
            "Ticket": decision.ticket,
            "Source": decision.source,
            "Status": decision.status,
            "Validation Report": decision.validation_report_path,
            "Candidates": decision.candidate_count,
            "Candidate Variants": _csv_list(decision.candidate_variants),
            "Blockers": _csv_list(decision.blockers),
            "Live Promotion Allowed": bool(decision.live_promotion_allowed),
        }
        for decision in decisions
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "Ticket",
            "Source",
            "Status",
            "Validation Report",
            "Candidates",
            "Candidate Variants",
            "Blockers",
            "Live Promotion Allowed",
        ],
    )


def format_evidence_gate_report(
    decisions: Iterable[PromotionGateDecision],
    *,
    generated_at_utc: str,
) -> str:
    rows = list(decisions)
    lines = [
        "# Evidence Gate Report",
        "",
        f"Generated UTC: {generated_at_utc}",
        "",
        (
            "No live scoring, veto, alert, recommendation, broker, or Pillar 7 behavior changes are made by this report."
        ),
        "",
        "## Promotion Criteria",
        "",
    ]
    lines.extend(f"- {criterion}" for criterion in PROMOTION_CRITERIA)
    lines.extend(
        [
            "",
            "## Gate Decisions",
            "",
            "| Ticket | Source | Status | Validation Report | Candidates | Candidate Variants | Blockers |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    for decision in rows:
        lines.append(
            f"| {decision.ticket} | "
            f"{decision.source} | "
            f"{decision.status} | "
            f"{decision.validation_report_path} | "
            f"{decision.candidate_count} | "
            f"{_csv_list(decision.candidate_variants)} | "
            f"{_csv_list(decision.blockers)} |"
        )
    lines.extend(
        [
            "",
            "## Rejected Or Unready Variants",
            "",
        ]
    )
    for decision in rows:
        lines.append(f"- {decision.ticket}: {_csv_list(decision.rejected_variants)}")
    lines.extend(
        [
            "",
            "## Rollback",
            "",
            (
                "Rollback for any future promoted rule is to remove the promoted criteria change, rerun the "
                "validation report, and confirm the gate returns to `blocked_no_candidates` or `ready_for_review` "
                "without altering live behavior from this report alone."
            ),
            "",
            "## Decision",
            "",
            "Only tickets with `ready_for_review` may proceed to a separate reviewed promotion patch. "
            "Tickets with `blocked_no_candidates` or `blocked_invalid_summary` remain research-only.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
