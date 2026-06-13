from __future__ import annotations

import pandas as pd

from src.calibration_research import calibration_candidate_guardrail, sector_override_guardrail


def _base_config(**overrides):
    config = {
        "research_only": True,
        "config_status": "blocked_final_holdout_not_evaluated",
        "final_holdout_evaluated": False,
        "final_holdout_rows_used": 0,
        "live_promotion_allowed": False,
        "selected_candidate": {
            "promotion_label": "needs more testing",
            "live_promotion_allowed": False,
        },
        "safety": {
            "candidate_promotion": "separate_ticket_required",
        },
    }
    config.update(overrides)
    return config


def test_calibration_candidate_guardrail_passes_blocked_research_config():
    guardrail = calibration_candidate_guardrail(_base_config())

    assert guardrail["status"] == "pass_display_only"
    assert guardrail["live_promotion_allowed"] is False
    assert guardrail["requires_separate_ticket"] is True
    assert guardrail["reasons"] == []


def test_calibration_candidate_guardrail_fails_candidate_without_holdout():
    guardrail = calibration_candidate_guardrail(
        _base_config(
            config_status="passed_final_holdout_research_candidate",
            selected_candidate={
                "promotion_label": "candidate",
                "live_promotion_allowed": False,
            },
        )
    )

    assert guardrail["status"] == "fail_closed"
    assert "candidate_without_final_holdout" in guardrail["reasons"]
    assert "passed_status_without_final_holdout" in guardrail["reasons"]


def test_calibration_candidate_guardrail_fails_any_live_promotion_flag():
    guardrail = calibration_candidate_guardrail(
        _base_config(
            live_promotion_allowed=True,
            selected_candidate={
                "promotion_label": "needs more testing",
                "live_promotion_allowed": True,
            },
        )
    )

    assert guardrail["status"] == "fail_closed"
    assert "config_live_promotion_true" in guardrail["reasons"]
    assert "selected_candidate_live_promotion_true" in guardrail["reasons"]


def test_sector_override_guardrail_passes_research_only_us_sector_override():
    overrides = pd.DataFrame(
        [
            {
                "sector": "XLK",
                "promotion_label": "sector_candidate",
                "live_promotion_allowed": False,
                "promotion_requires": "separate_reviewed_live_promotion_ticket",
                "sector_weight_multiplier": 1.05,
            }
        ]
    )

    guardrail = sector_override_guardrail(overrides)

    assert guardrail["status"] == "pass_display_only"
    assert guardrail["override_count"] == 1
    assert guardrail["reasons"] == []


def test_sector_override_guardrail_fails_unsafe_override():
    overrides = pd.DataFrame(
        [
            {
                "sector": "NOTASECTOR",
                "promotion_label": "sector_candidate",
                "live_promotion_allowed": True,
                "promotion_requires": "none",
                "sector_weight_multiplier": 1.5,
            }
        ]
    )

    guardrail = sector_override_guardrail(overrides)

    assert guardrail["status"] == "fail_closed"
    assert "non_us_sector_override" in guardrail["reasons"]
    assert "override_live_promotion_true" in guardrail["reasons"]
    assert "missing_separate_review_requirement" in guardrail["reasons"]
    assert "weight_multiplier_out_of_bounds" in guardrail["reasons"]
