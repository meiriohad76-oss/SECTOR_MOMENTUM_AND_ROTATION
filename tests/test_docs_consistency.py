"""Task 11 — docs/CLAUDE.md pillar consistency tests.

Asserts that:
- The weights listed in CLAUDE.md match DEFAULT_SCORING_CONFIG exactly.
- docs/sector-rotation-methodology.md references the degraded-run section.
- methodology_scoring_parameters() reflects DEFAULT_SCORING_CONFIG keys/weights.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── helper ────────────────────────────────────────────────────────────────────

def _parse_claude_md_weights() -> dict[str, float]:
    """Extract {key: weight} from the Seven pillars table in CLAUDE.md."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    # Match table rows of the form: | # | `key` | description | **weight%** |
    # e.g.  | 1 | `provider_flow_z` | Provider-sourced ... | **23%** |
    pattern = re.compile(
        r"\|\s*\d+\s*\|\s*`(\w+)`\s*\|[^|]*\|\s*\*\*(\d+)%\*\*\s*\|"
    )
    weights: dict[str, float] = {}
    for key, pct in pattern.findall(text):
        weights[key] = float(pct) / 100.0
    return weights


# ── Task 11: CLAUDE.md ↔ DEFAULT_SCORING_CONFIG ───────────────────────────────

class TestClaudeMdPillarConsistency:
    def test_claude_md_pillar_table_present(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Seven pillars" in text or "seven pillars" in text.lower()
        assert "DEFAULT_SCORING_CONFIG" in text or "provider_flow_z" in text

    def test_claude_md_weights_sum_to_one(self):
        weights = _parse_claude_md_weights()
        assert weights, "No weights found in CLAUDE.md — table format may have changed"
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, (
            f"CLAUDE.md weights sum to {total:.4f}, expected 1.0 ± 0.01"
        )

    def test_claude_md_weights_match_default_scoring_config(self):
        from src.scoring import DEFAULT_SCORING_CONFIG

        doc_weights = _parse_claude_md_weights()
        assert doc_weights, "No weights parsed from CLAUDE.md"

        config_weights = dict(DEFAULT_SCORING_CONFIG.composite_weights)

        for key, doc_w in doc_weights.items():
            assert key in config_weights, (
                f"CLAUDE.md lists pillar '{key}' but it is not in "
                f"DEFAULT_SCORING_CONFIG.composite_weights"
            )
            assert abs(config_weights[key] - doc_w) < 0.005, (
                f"Weight mismatch for '{key}': "
                f"CLAUDE.md={doc_w:.3f}, config={config_weights[key]:.3f}"
            )

    def test_claude_md_does_not_use_cmf21_as_top_level_pillar(self):
        """cmf21 is a sub-component of provider_flow_z, not a standalone 23% pillar."""
        doc_weights = _parse_claude_md_weights()
        assert "cmf21" not in doc_weights, (
            "cmf21 should not appear as a top-level pillar in CLAUDE.md; "
            "it is a sub-component of provider_flow_z"
        )

    def test_claude_md_binary_filters_not_breadth_50d_as_pillar(self):
        """breadth_50d is a gate input, not a composite-weight pillar."""
        doc_weights = _parse_claude_md_weights()
        assert "breadth_50d" not in doc_weights, (
            "breadth_50d should not appear as a composite-weight pillar in CLAUDE.md; "
            "it is used only in STATE_MACHINE_THRESHOLDS (gates)"
        )
        # binary_filters IS the 12% pillar
        assert "binary_filters" in doc_weights, (
            "binary_filters (Faber + Stage2 + Antonacci) should appear as the 12% pillar"
        )

    def test_methodology_scoring_parameters_reflects_config(self):
        from src.scoring import DEFAULT_SCORING_CONFIG, methodology_scoring_parameters

        params = methodology_scoring_parameters()
        config_weights = dict(DEFAULT_SCORING_CONFIG.composite_weights)
        param_weights = dict(params.get("composite_weights", {}))

        for key, cw in config_weights.items():
            assert key in param_weights, (
                f"methodology_scoring_parameters() missing pillar '{key}'"
            )
            assert abs(param_weights[key] - cw) < 1e-9, (
                f"Weight mismatch for '{key}' in methodology_scoring_parameters()"
            )


# ── Task 11: methodology doc has degraded-run section ─────────────────────────

class TestMethodologyDocDegradedRun:
    def _text(self):
        return (ROOT / "docs" / "sector-rotation-methodology.md").read_text(encoding="utf-8")

    def test_degraded_run_section_present(self):
        assert "degraded" in self._text().lower(), (
            "docs/sector-rotation-methodology.md must have a degraded-run section"
        )

    def test_min_flow_coverage_documented(self):
        assert "min_flow_coverage" in self._text(), (
            "min_flow_coverage config knob must be documented in methodology.md"
        )

    def test_renormalize_not_zero_fill_documented(self):
        text = self._text()
        assert "renormali" in text.lower() or "renormalize" in text.lower(), (
            "Renormalization behavior (not zero-fill) must be documented"
        )

    def test_eligibility_gate_documented(self):
        text = self._text()
        assert "ELIGIBLE_STATES" in text or "eligibility" in text.lower(), (
            "Eligibility gate must be documented in methodology.md"
        )

    def test_four_pillar_candidate_noted(self):
        text = self._text()
        assert "4-pillar" in text or "four-pillar" in text or "four pillar" in text.lower(), (
            "4-pillar consolidation candidate must be noted in methodology.md"
        )
