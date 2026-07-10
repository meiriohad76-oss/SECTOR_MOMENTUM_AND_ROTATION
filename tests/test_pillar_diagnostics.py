"""Tests for Task 8: pillar_diagnostics() and write_pillar_correlation_report()."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.scoring import (
    PILLAR_COLUMNS,
    pillar_diagnostics,
    write_pillar_correlation_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scored_df(n: int = 30, seed: int = 42) -> pd.DataFrame:
    """Synthetic scored DataFrame with all 7 pillar columns present."""
    rng = np.random.default_rng(seed)
    tickers = [f"T{i:02d}" for i in range(n)]

    mom_12_1 = rng.normal(0, 10, n)
    # mansfield_rs and rs_ratio are nearly perfectly correlated by construction
    base_rs = rng.normal(0, 5, n)
    mansfield_rs = base_rs + rng.normal(0, 0.05, n)
    rs_ratio = base_rs * 2.1 + 5.0 + rng.normal(0, 0.05, n)
    rs_momentum = rng.normal(0, 3, n)
    F_score = rng.normal(0, 1, n)
    binary_filters = rng.integers(0, 4, n).astype(float)
    cycle_tilt = rng.choice([-1.0, 0.0, 1.0], n)
    # Extra columns that compute_composite() would add
    stage = rng.integers(1, 5, n)
    faber = rng.integers(0, 2, n)
    antonacci = rng.integers(0, 2, n)
    S_score = rng.normal(0, 1, n)

    return pd.DataFrame(
        {
            "mom_12_1": mom_12_1,
            "mansfield_rs": mansfield_rs,
            "rs_ratio": rs_ratio,
            "rs_momentum": rs_momentum,
            "F_score": F_score,
            "binary_filters": binary_filters,
            "cycle_tilt": cycle_tilt,
            "stage": stage,
            "faber": faber,
            "antonacci": antonacci,
            "S_score": S_score,
        },
        index=tickers,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pillar_diagnostics_flags_mansfield_rs_and_rs_ratio_as_correlated():
    """Near-perfect mansfield_rs ↔ rs_ratio correlation must appear in redundant_pairs."""
    df = _make_scored_df()
    result = pillar_diagnostics(df, threshold=0.8)

    flagged = result["redundant_pairs"]
    assert len(flagged) > 0, "Expected at least one redundant pair to be flagged"

    pair_names = {frozenset({p["pillar_a"], p["pillar_b"]}) for p in flagged}
    assert frozenset({"mansfield_rs", "rs_ratio"}) in pair_names, (
        "mansfield_rs ↔ rs_ratio must be in redundant_pairs because they are derived "
        "from the same price/benchmark ratio"
    )


def test_pillar_diagnostics_returns_correlation_matrix_keys():
    """All 7 pillar columns must appear as keys in the correlation matrix."""
    df = _make_scored_df()
    result = pillar_diagnostics(df)

    matrix = result["correlation_matrix"]
    for pillar in PILLAR_COLUMNS:
        assert pillar in matrix, f"Pillar '{pillar}' missing from correlation_matrix keys"
        assert pillar in matrix[pillar], (
            f"Pillar '{pillar}' missing from correlation_matrix['{pillar}'] inner dict"
        )
        assert matrix[pillar][pillar] == pytest.approx(1.0, abs=1e-3), (
            f"Self-correlation of '{pillar}' must be 1.0"
        )


def test_pillar_diagnostics_result_structure():
    """Return value must have all required keys with correct types."""
    df = _make_scored_df()
    result = pillar_diagnostics(df, threshold=0.75)

    assert set(result.keys()) == {"correlation_matrix", "redundant_pairs", "threshold", "pillar_count"}
    assert isinstance(result["correlation_matrix"], dict)
    assert isinstance(result["redundant_pairs"], list)
    assert result["threshold"] == 0.75
    assert result["pillar_count"] == len(PILLAR_COLUMNS)


def test_pillar_diagnostics_redundant_pair_fields():
    """Each redundant pair dict must have the required fields."""
    df = _make_scored_df()
    result = pillar_diagnostics(df, threshold=0.8)

    for pair in result["redundant_pairs"]:
        assert "pillar_a" in pair
        assert "pillar_b" in pair
        assert "spearman_rho" in pair
        assert "abs_rho" in pair
        assert "sub_index" in pair
        assert abs(pair["spearman_rho"]) > 0.8
        assert pair["abs_rho"] == pytest.approx(abs(pair["spearman_rho"]), abs=1e-6)


def test_pillar_diagnostics_high_threshold_returns_no_pairs():
    """With threshold=1.0 (impossible) no pairs should be flagged."""
    df = _make_scored_df()
    result = pillar_diagnostics(df, threshold=1.0)
    assert result["redundant_pairs"] == []


def test_write_pillar_correlation_report_creates_markdown_file(tmp_path):
    """Report file must be created with expected Markdown headers."""
    df = _make_scored_df()
    report_path = str(tmp_path / "pillar_correlation_report.md")
    returned = write_pillar_correlation_report(df, path=report_path)

    assert returned == report_path
    out = Path(report_path)
    assert out.exists(), "Markdown report file was not created"

    content = out.read_text(encoding="utf-8")
    assert "# Pillar Correlation Report" in content
    assert "## Spearman Correlation Matrix" in content
    assert "## Flagged Redundant Pairs" in content
    assert "mansfield_rs" in content
    assert "rs_ratio" in content
    # Must call out the known redundancy
    assert "## Known Redundancy: mansfield_rs" in content


def test_write_pillar_correlation_report_matrix_contains_all_pillars(tmp_path):
    """The correlation table in the report must include all 7 pillar names."""
    df = _make_scored_df()
    report_path = str(tmp_path / "report.md")
    write_pillar_correlation_report(df, path=report_path)

    content = Path(report_path).read_text(encoding="utf-8")
    for pillar in PILLAR_COLUMNS:
        assert pillar in content, f"Pillar '{pillar}' not found in report content"


def test_pillar_diagnostics_builds_binary_filters_when_missing():
    """If binary_filters is absent, diagnostics should derive it from stage/faber/antonacci."""
    df = _make_scored_df()
    df_no_bf = df.drop(columns=["binary_filters"])

    result = pillar_diagnostics(df_no_bf, threshold=0.8)
    # binary_filters should still be in the matrix (derived on the fly)
    assert "binary_filters" in result["correlation_matrix"]
