"""Tests for compute_class_rotation (Task 7).

Verifies that the cross-class rotation view:
  - correctly ranks a "hot" class above a "cold" class
  - excludes tickers whose class resolves to "Benchmark"
  - returns all required output columns
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scoring import compute_class_rotation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_indicators(tickers: list[str], mom_12_1: list[float], mansfield_rs: list[float]) -> pd.DataFrame:
    """Minimal indicators DataFrame with only the columns compute_class_rotation needs."""
    return pd.DataFrame(
        {
            "mom_12_1": mom_12_1,
            "mansfield_rs": mansfield_rs,
        },
        index=tickers,
    )


def _make_flow(tickers: list[str], breadth_50d: list[float], cmf21: list[float], net_flow_21d: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "breadth_50d": breadth_50d,
            "cmf21": cmf21,
            "net_flow_21d": net_flow_21d,
        },
        index=tickers,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compute_class_rotation_ranks_hot_class_above_cold():
    """Class A (high momentum / breadth / flow) must rank above class B (low values)."""
    tickers = ["HOT1", "HOT2", "COLD1", "COLD2"]
    # Class A → hot; Class B → cold (via class_overrides)
    class_overrides = {
        "HOT1": "Class A",
        "HOT2": "Class A",
        "COLD1": "Class B",
        "COLD2": "Class B",
    }

    indicators = _make_indicators(
        tickers,
        mom_12_1=[0.30, 0.25, -0.10, -0.15],       # Class A: strong positive; Class B: negative
        mansfield_rs=[5.0, 4.0, -3.0, -4.0],
    )
    flow = _make_flow(
        tickers,
        breadth_50d=[0.80, 0.75, 0.30, 0.25],
        cmf21=[0.20, 0.15, -0.10, -0.12],
        net_flow_21d=[1_000_000, 800_000, -500_000, -600_000],
    )

    result = compute_class_rotation(indicators, flow, class_overrides=class_overrides)

    assert "Class A" in result.index
    assert "Class B" in result.index
    assert result.loc["Class A", "rank"] < result.loc["Class B", "rank"], (
        f"Expected Class A (rank {result.loc['Class A', 'rank']}) to rank above "
        f"Class B (rank {result.loc['Class B', 'rank']})"
    )


def test_compute_class_rotation_excludes_benchmark_class():
    """Tickers whose class is 'Benchmark' must not appear in the output index."""
    tickers = ["SPY", "ACWI", "HOT1"]
    class_overrides = {
        "SPY": "Benchmark",
        "ACWI": "Benchmark",
        "HOT1": "Class A",
    }

    indicators = _make_indicators(
        tickers,
        mom_12_1=[0.10, 0.08, 0.25],
        mansfield_rs=[1.0, 0.5, 4.0],
    )
    flow = _make_flow(
        tickers,
        breadth_50d=[0.55, 0.50, 0.80],
        cmf21=[0.05, 0.03, 0.20],
        net_flow_21d=[100_000, 80_000, 500_000],
    )

    result = compute_class_rotation(indicators, flow, class_overrides=class_overrides)

    assert "Benchmark" not in result.index, "Benchmark class must be excluded from rotation output"
    assert "Class A" in result.index


def test_class_rotation_columns_present():
    """All required output columns must be present."""
    tickers = ["T1", "T2"]
    class_overrides = {"T1": "Group X", "T2": "Group Y"}

    indicators = _make_indicators(
        tickers,
        mom_12_1=[0.10, -0.05],
        mansfield_rs=[2.0, -1.0],
    )
    flow = _make_flow(
        tickers,
        breadth_50d=[0.60, 0.40],
        cmf21=[0.08, -0.03],
        net_flow_21d=[200_000, -100_000],
    )

    result = compute_class_rotation(indicators, flow, class_overrides=class_overrides)

    required = {"agg_momentum", "agg_breadth", "agg_cmf", "agg_mansfield_rs", "agg_net_flow_21d", "class_score", "rank"}
    missing = required - set(result.columns)
    assert not missing, f"Missing columns: {missing}"


def test_class_rotation_rank_is_integer_starting_at_one():
    """rank column must be integer and the best class has rank == 1."""
    tickers = ["A1", "A2", "B1", "B2", "C1"]
    class_overrides = {
        "A1": "Alpha", "A2": "Alpha",
        "B1": "Beta", "B2": "Beta",
        "C1": "Gamma",
    }
    indicators = _make_indicators(
        tickers,
        mom_12_1=[0.20, 0.18, 0.05, 0.03, -0.08],
        mansfield_rs=[4.0, 3.5, 1.0, 0.5, -2.0],
    )
    flow = _make_flow(
        tickers,
        breadth_50d=[0.75, 0.70, 0.55, 0.50, 0.35],
        cmf21=[0.15, 0.12, 0.02, 0.01, -0.05],
        net_flow_21d=[1_000_000, 900_000, 100_000, 80_000, -50_000],
    )

    result = compute_class_rotation(indicators, flow, class_overrides=class_overrides)

    assert result["rank"].min() == 1
    assert set(result["rank"].tolist()) == {1, 2, 3}
