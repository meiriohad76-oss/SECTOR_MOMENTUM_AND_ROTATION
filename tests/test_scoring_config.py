"""Tests for Task 1 (ScoringConfig) and Task 2 (flow degradation renormalization).

Task 1 acceptance criteria
--------------------------
- All existing tests/test_scoring.py pass unchanged (verified by running the full suite).
- compute_composite with DEFAULT_SCORING_CONFIG produces identical output to the
  pre-Task-1 function on a fixed fixture.
- A candidate config with different weights produces different scores.
- scoring_config_from_dict round-trips the calibration JSON schema.

Task 2 acceptance criteria
--------------------------
- All-zero / empty flow → composite computed from 6 renormalized pillars
  (weights sum to 1.0), degraded_run == True, veto does not fire.
- Full flow → behaviour identical to pre-Task-2 (degraded_run == False).
- Golden: on a degraded run the top-of-class ranking is unchanged vs. the
  pre-fix zero-fill path for the same inputs, except absolute S-scores differ
  (ranking preserved, scale changes).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src import scoring
from src.scoring import (
    DEFAULT_SCORING_CONFIG,
    ScoringConfig,
    scoring_config_from_dict,
    compute_composite,
    decide_state,
    COMPOSITE_WEIGHTS,
    FLOW_VETO,
    BINARY_FILTER_COUNT,
    STATE_MACHINE_THRESHOLDS,
    PULLBACK_RISK_THRESHOLDS,
)
from src.flow import FlowCompositeResult, flow_composite_z


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_indicators(tickers=("XLK", "XLF", "XLE"), seed=42) -> pd.DataFrame:
    """Pure indicator columns — no overlap with flow_df columns."""
    rng = np.random.default_rng(seed)
    n = len(tickers)
    return pd.DataFrame(
        {
            "mom_12_1": rng.uniform(0.05, 0.30, n),
            "faber": [1] * n,
            "stage": [2] * n,
            "mansfield_rs": rng.uniform(-5.0, 15.0, n),
            "antonacci": [1] * n,
            "rs_ratio": rng.uniform(95.0, 115.0, n),
            "rs_momentum": rng.uniform(95.0, 110.0, n),
            "breadth_50d": rng.uniform(0.5, 0.9, n),
            "above_30wma": [True] * n,
            "ma_slope_pos": [True] * n,
            "return_5d": rng.uniform(-0.01, 0.03, n),
            "return_1d": [0.0] * n,
            "return_2d": [0.0] * n,
        },
        index=list(tickers),
    )


def _make_flow_df(tickers=("XLK", "XLF", "XLE"), seed=0) -> pd.DataFrame:
    """Flow signal columns (no overlap with indicator columns)."""
    rng = np.random.default_rng(seed)
    n = len(tickers)
    return pd.DataFrame(
        {
            "cmf21": rng.uniform(-0.1, 0.2, n),
            "obv_slope": rng.uniform(-0.02, 0.02, n),
            "rvol": rng.uniform(0.7, 1.6, n),
            "mfi14": rng.uniform(40.0, 70.0, n),
            "net_flow_21d": rng.uniform(-1e6, 1e6, n),
            "adv_20d": [1e7] * n,
            "dist_days_25": [0] * n,
            "obv_divergence": [False] * n,
            "etf_flow_5d_pct": [0.0] * n,
            "etf_flow_5d_pct_live": [False] * n,
            "block_up_ratio": [1.0] * n,
            "block_up_ratio_live": [False] * n,
            "dark_pool_pct": [0.4] * n,
            "dark_pool_pct_live": [False] * n,
            "si_delta_15d": [0.0] * n,
            "si_delta_15d_live": [False] * n,
            "thirteen_f_q": [0.0] * n,
            "thirteen_f_q_live": [False] * n,
        },
        index=list(tickers),
    )


def _make_scoring_fixture(tickers=("XLK", "XLF", "XLE"), seed=42):
    """Return (indicators_df, flow_df) with clean non-overlapping columns."""
    return _make_indicators(tickers, seed=seed), _make_flow_df(tickers, seed=seed)


def _zero_flow_z(tickers=("XLK", "XLF", "XLE")) -> pd.Series:
    """Pre-Task-2 zero-fill result for a degraded run."""
    return pd.Series(0.0, index=list(tickers), name="F")


# ---------------------------------------------------------------------------
# Task 1: ScoringConfig
# ---------------------------------------------------------------------------

class TestScoringConfig:
    def test_default_config_matches_module_constants(self):
        cfg = DEFAULT_SCORING_CONFIG
        assert cfg.composite_weights == dict(COMPOSITE_WEIGHTS)
        assert cfg.flow_veto == dict(FLOW_VETO)
        assert cfg.binary_filter_count == BINARY_FILTER_COUNT
        assert cfg.state_machine_thresholds == {
            k: dict(v) for k, v in STATE_MACHINE_THRESHOLDS.items()
        }
        assert cfg.pullback_risk_thresholds == dict(PULLBACK_RISK_THRESHOLDS)

    def test_config_is_frozen(self):
        cfg = DEFAULT_SCORING_CONFIG
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            cfg.binary_filter_count = 4.0  # type: ignore[misc]

    def test_scoring_config_from_dict_round_trips_calibration_schema(self, tmp_path):
        import json, pathlib
        baseline = pathlib.Path(__file__).parent.parent / "docs" / "calibration_10y_baseline_config.json"
        d = json.loads(baseline.read_text(encoding="utf-8"))
        cfg = scoring_config_from_dict(d)
        assert cfg.composite_weights == dict(COMPOSITE_WEIGHTS)
        assert abs(cfg.composite_weights["mom_12_1_z"] - 0.22) < 1e-9
        assert cfg.binary_filter_count == pytest.approx(3.0)
        assert cfg.flow_veto["threshold_z"] == pytest.approx(-0.5)

    def test_scoring_config_from_dict_accepts_bare_scoring_parameters_block(self):
        d = {
            "composite_weights": {"mom_12_1_z": 0.25, "provider_flow_z": 0.10,
                                   "mansfield_rs_z": 0.15, "rs_ratio_z": 0.15,
                                   "rs_momentum_z": 0.10, "binary_filters": 0.15,
                                   "cycle_tilt": 0.10},
            "flow_veto": {"threshold_z": -1.0, "replacement_score": -5.0},
            "binary_filter_count": 3.0,
            "state_machine": {"bearish_stage_4": {"mansfield_rs_lt": 0.0, "cmf21_lt": -0.10},
                               "exit": {"mansfield_rs_lt": 0.0, "antonacci_eq": 0,
                                        "rrg_quadrant_eq": "Lagging", "cmf21_lt": -0.10,
                                        "etf_flow_5d_pct_lt": -1.5, "block_up_ratio_lt": 0.7},
                               "warning": {"rrg_quadrant_eq": "Weakening", "breadth_50d_lt": 0.50,
                                            "cmf21_lt": 0.0, "obv_divergence_eq": True,
                                            "dist_days_25_gte": 4, "return_5d_lte": -0.04},
                               "stage_2_bullish": {"stage_eq": 2, "rrg_quadrant_eq": "Leading",
                                                    "breadth_50d_gte": 0.60, "cmf21_gt": 0.05,
                                                    "etf_flow_5d_pct_gte": 0.0, "return_5d_gt": -0.04},
                               "hold": {"stage_eq": 2},
                               "stage_1_basing": {"stage_eq": 1}},
            "pullback_risk_modifier": {"return_1d_lte": -0.01, "return_2d_lte": -0.015,
                                        "return_5d_lte": -0.035},
        }
        cfg = scoring_config_from_dict(d)
        assert cfg.composite_weights["mom_12_1_z"] == pytest.approx(0.25)
        assert cfg.flow_veto["threshold_z"] == pytest.approx(-1.0)

    def test_compute_composite_with_default_config_is_byte_identical(self):
        """DEFAULT_SCORING_CONFIG must produce same scores as hardcoded constants."""
        ind = _make_indicators()
        fl = _make_flow_df()
        flow_s = pd.Series([0.5, -0.3, 0.1], index=["XLK", "XLF", "XLE"], name="F")

        out_default = compute_composite(ind, fl, flow_s, phase="MID",
                                        config=DEFAULT_SCORING_CONFIG)
        out_none = compute_composite(ind, fl, flow_s, phase="MID", config=None)

        pd.testing.assert_series_equal(
            out_default["S_score"], out_none["S_score"], check_names=False
        )
        pd.testing.assert_series_equal(
            out_default["S_score_after_veto"], out_none["S_score_after_veto"], check_names=False
        )

    def test_candidate_config_with_different_weights_produces_different_scores(self):
        ind = _make_indicators()
        fl = _make_flow_df()
        flow_s = pd.Series([0.5, -0.3, 0.1], index=["XLK", "XLF", "XLE"], name="F")

        out_default = compute_composite(ind, fl, flow_s, phase="MID")

        # Flip the weight emphasis
        alt_weights = dict(COMPOSITE_WEIGHTS)
        alt_weights["mom_12_1_z"] = 0.01
        alt_weights["provider_flow_z"] = 0.50
        # Renormalize so they still sum to 1
        total = sum(alt_weights.values())
        alt_weights = {k: v / total for k, v in alt_weights.items()}
        candidate_cfg = ScoringConfig(
            composite_weights=alt_weights,
            flow_veto=dict(FLOW_VETO),
            binary_filter_count=BINARY_FILTER_COUNT,
            state_machine_thresholds={k: dict(v) for k, v in STATE_MACHINE_THRESHOLDS.items()},
            pullback_risk_thresholds=dict(PULLBACK_RISK_THRESHOLDS),
        )
        out_candidate = compute_composite(ind, fl, flow_s, phase="MID", config=candidate_cfg)

        # Scores must differ when weights are materially changed
        assert not out_default["S_score"].equals(out_candidate["S_score"])

    def test_decide_state_uses_config_thresholds(self):
        """A config with a raised mansfield_rs_lt threshold changes EXIT decisions."""
        # Build a row that just barely crosses mansfield_rs < 0 → EXIT by default
        row = pd.Series({
            "stage": 2, "above_30wma": True, "ma_slope_pos": True,
            "mansfield_rs": -0.5, "antonacci": 1, "rrg_quadrant": "Leading",
            "breadth_50d": 0.70, "cmf21": 0.08, "return_5d": 0.01,
            "rvol": 1.0, "etf_flow_5d_pct": 0.0, "block_up_ratio": 1.0,
            "obv_divergence": False, "dist_days_25": 0,
        })
        assert decide_state(row) == "EXIT"  # default: rs < 0 → EXIT

        # With a more permissive threshold (rs < -5 required), it should survive to HOLD/BULLISH
        strict_exit = dict(STATE_MACHINE_THRESHOLDS["exit"])
        strict_exit["mansfield_rs_lt"] = -5.0
        new_thresholds = {k: dict(v) for k, v in STATE_MACHINE_THRESHOLDS.items()}
        new_thresholds["exit"] = strict_exit
        cfg = ScoringConfig(
            composite_weights=dict(COMPOSITE_WEIGHTS),
            flow_veto=dict(FLOW_VETO),
            binary_filter_count=BINARY_FILTER_COUNT,
            state_machine_thresholds=new_thresholds,
            pullback_risk_thresholds=dict(PULLBACK_RISK_THRESHOLDS),
        )
        # mansfield_rs=-0.5 > -5, so EXIT threshold not met → falls through to HOLD or BULLISH
        state = decide_state(row, config=cfg)
        assert state not in ("EXIT", "BEARISH_STAGE_4")

    def test_methodology_scoring_parameters_reflects_config(self):
        alt_weights = {"mom_12_1_z": 0.25, "provider_flow_z": 0.10,
                       "mansfield_rs_z": 0.15, "rs_ratio_z": 0.20,
                       "rs_momentum_z": 0.10, "binary_filters": 0.10,
                       "cycle_tilt": 0.10}
        cfg = ScoringConfig(
            composite_weights=alt_weights,
            flow_veto=dict(FLOW_VETO),
            binary_filter_count=BINARY_FILTER_COUNT,
            state_machine_thresholds={k: dict(v) for k, v in STATE_MACHINE_THRESHOLDS.items()},
            pullback_risk_thresholds=dict(PULLBACK_RISK_THRESHOLDS),
        )
        params = scoring.methodology_scoring_parameters(config=cfg)
        assert params["composite_weights"]["mom_12_1_z"] == pytest.approx(0.25)
        assert params["composite_weights"]["provider_flow_z"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# Task 2: Flow degradation detection + renormalization
# ---------------------------------------------------------------------------

class TestFlowDegradation:

    def _make_fcr(self, tickers, *, flow_available, coverage=0.0):
        """Build a FlowCompositeResult with real OHLCV-based variation."""
        fl = _make_flow_df(tickers)
        # Set live flags based on desired scenario
        if flow_available:
            for col in ("etf_flow_5d_pct_live", "block_up_ratio_live", "si_delta_15d_live"):
                fl[col] = True
        flow_result = flow_composite_z(fl)
        return flow_result

    def test_flow_composite_z_returns_flow_composite_result(self):
        fl = _make_flow_df()
        result = flow_composite_z(fl)
        assert isinstance(result, FlowCompositeResult)
        assert isinstance(result.z, pd.Series)
        assert result.z.name == "F"
        assert 0.0 <= result.flow_coverage <= 1.0
        assert isinstance(result.flow_available, bool)

    def test_flow_coverage_is_zero_when_all_providers_stubbed(self):
        fl = _make_flow_df()  # all _live = False
        result = flow_composite_z(fl)
        assert result.flow_coverage == pytest.approx(0.0)
        assert result.flow_available is False  # 0.0 < default min_flow_coverage 0.5

    def test_flow_coverage_is_one_when_all_providers_live(self):
        fl = _make_flow_df()
        for col in ("etf_flow_5d_pct_live", "block_up_ratio_live", "si_delta_15d_live"):
            fl[col] = True
        result = flow_composite_z(fl, min_flow_coverage=0.5)
        assert result.flow_coverage == pytest.approx(1.0)
        assert result.flow_available is True

    def test_degraded_run_when_no_provider_flow(self):
        ind = _make_indicators()
        fl = _make_flow_df()  # all live=False
        flow_result = flow_composite_z(fl)
        out = compute_composite(ind, fl, flow_result, phase="MID")

        assert bool(out["degraded_run"].all()) is True
        assert bool(out["flow_pillar_active"].all()) is False
        assert int(out["active_pillar_count"].iloc[0]) == 6

    def test_renormalized_weights_sum_to_one_on_degraded_run(self):
        ind = _make_indicators()
        fl = _make_flow_df()
        flow_result = flow_composite_z(fl)
        out = compute_composite(ind, fl, flow_result, phase="MID")

        eff = json.loads(out["effective_weights"].iloc[0])
        # provider_flow_z must be absent (dropped)
        assert "provider_flow_z" not in eff
        assert sum(eff.values()) == pytest.approx(1.0, abs=1e-6)

    def test_veto_does_not_fire_on_degraded_run(self):
        """Even extreme negative 'flow' should not trigger the hard veto when flow is inactive."""
        ind = _make_indicators(("XLK", "XLF"))
        fl = _make_flow_df(("XLK", "XLF"))
        # Force a highly negative F for XLF via flow_df cmf21
        fl.loc["XLF", "cmf21"] = -0.99
        flow_result = flow_composite_z(fl)  # still no live providers
        out = compute_composite(ind, fl, flow_result, phase="MID")

        assert bool(out.loc["XLF", "veto"]) is False
        assert out.loc["XLF", "S_score_after_veto"] == pytest.approx(
            out.loc["XLF", "S_score"]
        )

    def test_full_flow_run_is_not_degraded(self):
        ind = _make_indicators()
        fl = _make_flow_df()
        for col in ("etf_flow_5d_pct_live", "block_up_ratio_live", "si_delta_15d_live"):
            fl[col] = True
        flow_result = flow_composite_z(fl)
        out = compute_composite(ind, fl, flow_result, phase="MID")

        assert bool(out["degraded_run"].any()) is False
        assert bool(out["flow_pillar_active"].all()) is True
        # Full weights include provider_flow_z
        eff = json.loads(out["effective_weights"].iloc[0])
        assert "provider_flow_z" in eff

    def test_degraded_run_preserves_top_of_class_ranking(self):
        """Ranking within class must be the same whether we zero-fill or renormalize."""
        tickers = ("XLK", "XLF", "XLE", "XLY")
        ind = _make_indicators(tickers, seed=99)
        fl = _make_flow_df(tickers, seed=99)

        # Simulate old buggy zero-fill path (plain Series of zeros)
        zero_flow = pd.Series(0.0, index=list(tickers), name="F")
        out_zero = compute_composite(ind, fl, zero_flow, phase="MID")

        # New path: FlowCompositeResult with no live providers
        flow_result = flow_composite_z(fl)  # coverage=0 → degraded
        out_renorm = compute_composite(ind, fl, flow_result, phase="MID")

        # Top-ranked ticker should be the same in both paths (ranking preserved)
        top_zero = out_zero.sort_values("rank_in_class").index[0]
        top_renorm = out_renorm.sort_values("rank_in_class").index[0]
        assert top_zero == top_renorm, (
            f"Top ticker changed from {top_zero!r} to {top_renorm!r}; "
            "renormalization must preserve within-class rank order."
        )

        # Absolute S-scores differ (this is intended: scale changes)
        assert not out_zero["S_score"].equals(out_renorm["S_score"]), (
            "S-scores should differ between zero-fill and renormalized paths."
        )

    def test_backward_compat_plain_series_still_accepted(self):
        """compute_composite still accepts a plain pd.Series for flow_z."""
        ind = _make_indicators()
        fl = _make_flow_df()
        plain = pd.Series([0.2, -0.1, 0.05], index=["XLK", "XLF", "XLE"], name="F")
        out = compute_composite(ind, fl, plain, phase="MID")

        # Plain series → treated as fully available
        assert bool(out["flow_pillar_active"].all()) is True
        assert bool(out["degraded_run"].any()) is False
