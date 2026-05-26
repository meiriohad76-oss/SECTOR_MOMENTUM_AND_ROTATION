"""Master composite scoring + state machine.

Formulas track §5 and §6 of sector-rotation-methodology.md exactly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Mapping, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .universe import class_of, TOP_N
from .macro import cycle_tilt


STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).resolve().parent.parent / "state.json"))
EASTERN_TZ = ZoneInfo("America/New_York")

STATES = ["STAGE_2_BULLISH", "HOLD", "WARNING", "EXIT", "BEARISH_STAGE_4", "STAGE_1_BASING"]
COMPOSITE_WEIGHTS = {
    "mom_12_1_z": 0.22,
    "mansfield_rs_z": 0.12,
    "rs_ratio_z": 0.15,
    "rs_momentum_z": 0.08,
    "binary_filters": 0.12,
    "cycle_tilt": 0.08,
    "provider_flow_z": 0.23,
}
BINARY_FILTER_COUNT = 3.0
FLOW_VETO = {"threshold_z": -0.5, "replacement_score": -9.99}
STATE_MACHINE_THRESHOLDS = {
    "bearish_stage_4": {
        "mansfield_rs_lt": 0.0,
        "cmf21_lt": -0.10,
    },
    "exit": {
        "mansfield_rs_lt": 0.0,
        "antonacci_eq": 0,
        "rrg_quadrant_eq": "Lagging",
        "cmf21_lt": -0.10,
        "etf_flow_5d_pct_lt": -1.5,
        "block_up_ratio_lt": 0.7,
    },
    "warning": {
        "rrg_quadrant_eq": "Weakening",
        "breadth_50d_lt": 0.50,
        "cmf21_lt": 0.0,
        "obv_divergence_eq": True,
        "dist_days_25_gte": 4,
    },
    "stage_2_bullish": {
        "stage_eq": 2,
        "rrg_quadrant_eq": "Leading",
        "breadth_50d_gte": 0.60,
        "cmf21_gt": 0.05,
        "etf_flow_5d_pct_gte": 0.0,
    },
    "hold": {"stage_eq": 2},
    "stage_1_basing": {"stage_eq": 1},
}


def methodology_scoring_parameters() -> dict:
    return {
        "composite_weights": dict(COMPOSITE_WEIGHTS),
        "binary_filter_count": BINARY_FILTER_COUNT,
        "flow_veto": dict(FLOW_VETO),
        "rank_method": "min",
        "rank_ascending": False,
        "selection_top_n_by_class": dict(sorted(TOP_N.items())),
        "state_order": list(STATES),
        "state_machine": {
            state: dict(thresholds)
            for state, thresholds in STATE_MACHINE_THRESHOLDS.items()
        },
    }


def _z(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    std = s.std(ddof=0)
    if std == 0 or pd.isna(std):
        return s * 0.0
    return (s - s.mean()) / std


def compute_composite(
    indicators_df: pd.DataFrame,
    flow_df: pd.DataFrame,
    flow_z: pd.Series,
    phase: str,
    class_overrides: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Master composite S_i per §5.  Cross-sectional z-scoring is done within
    each universe class so we don't compare a country ETF against a US sector."""
    df = indicators_df.copy()
    df = df.join(flow_df, how="left")
    df["F_score"] = flow_z

    # Universe class for grouped z-scoring
    class_overrides = class_overrides or {}
    df["class"] = [class_overrides.get(str(t), class_of(str(t))) for t in df.index]
    # Cycle tilt only meaningful for US sectors
    df["cycle_tilt"] = [cycle_tilt(t, phase) for t in df.index]

    out_parts = []
    for cls, sub in df.groupby("class"):
        if cls == "Benchmark":
            continue
        sub = sub.copy()
        # binary filters: TS_signal + Stage2 + Antonacci
        stage2 = (sub["stage"] == 2).astype(int)
        filters = (sub["faber"].fillna(0).astype(int)
                   + stage2
                   + sub["antonacci"].fillna(0).astype(int))
        filters_norm = filters / BINARY_FILTER_COUNT
        z_m121 = _z(sub["mom_12_1"])
        z_mans = _z(sub["mansfield_rs"])
        z_rsr = _z(sub["rs_ratio"])
        z_rsm = _z(sub["rs_momentum"])
        z_F = _z(sub["F_score"])
        sub["S_score"] = (
            COMPOSITE_WEIGHTS["mom_12_1_z"] * z_m121
            + COMPOSITE_WEIGHTS["mansfield_rs_z"] * z_mans
            + COMPOSITE_WEIGHTS["rs_ratio_z"] * z_rsr
            + COMPOSITE_WEIGHTS["rs_momentum_z"] * z_rsm
            + COMPOSITE_WEIGHTS["binary_filters"] * filters_norm
            + COMPOSITE_WEIGHTS["cycle_tilt"] * sub["cycle_tilt"]
            + COMPOSITE_WEIGHTS["provider_flow_z"] * z_F
        )
        # Hard veto: F_i < -0.5σ kills the ranking even if S is high
        sub["veto"] = (z_F < FLOW_VETO["threshold_z"]).fillna(False)
        sub["S_score_after_veto"] = sub["S_score"].where(
            ~sub["veto"],
            other=FLOW_VETO["replacement_score"],
        )
        sub["rank_in_class"] = sub["S_score_after_veto"].rank(
            ascending=False,
            method="min",
        )
        sub["top_n_target"] = TOP_N.get(cls, 0)
        sub["selected"] = sub["rank_in_class"] <= sub["top_n_target"]
        out_parts.append(sub)
    out = pd.concat(out_parts).sort_values(["class", "rank_in_class"])
    return out


# -------- State machine -----------------------------------------------------------

def decide_state(row: pd.Series) -> str:
    """Pure-function state assignment for a ticker given today's indicators.

    Implements §6 of the methodology.  Conservative ordering: check the
    worst states first so we never under-classify a deteriorating sector.
    """
    stage = row.get("stage")
    above = row.get("above_30wma")
    slope_pos = row.get("ma_slope_pos")
    mans = row.get("mansfield_rs")
    ant = row.get("antonacci")
    rrg_q = row.get("rrg_quadrant")
    breadth = row.get("breadth_50d")
    cmf = row.get("cmf21")
    rvol = row.get("rvol")
    nf5d = row.get("etf_flow_5d_pct")
    blk = row.get("block_up_ratio")
    obv_div = row.get("obv_divergence")
    dist = row.get("dist_days_25")
    bearish = STATE_MACHINE_THRESHOLDS["bearish_stage_4"]
    exit_thresholds = STATE_MACHINE_THRESHOLDS["exit"]
    warning = STATE_MACHINE_THRESHOLDS["warning"]
    bullish = STATE_MACHINE_THRESHOLDS["stage_2_bullish"]

    # ---- BEARISH (Stage 4) ----
    if (above is False) and (slope_pos is False) \
            and (mans is not None and mans < bearish["mansfield_rs_lt"]) \
            and (cmf is not None and cmf < bearish["cmf21_lt"]):
        return "BEARISH_STAGE_4"

    # ---- EXIT ----
    if (above is False) \
            or (mans is not None and mans < exit_thresholds["mansfield_rs_lt"]) \
            or (ant == exit_thresholds["antonacci_eq"]) \
            or (rrg_q == exit_thresholds["rrg_quadrant_eq"]) \
            or (cmf is not None and cmf < exit_thresholds["cmf21_lt"]) \
            or (nf5d is not None and nf5d < exit_thresholds["etf_flow_5d_pct_lt"]) \
            or (blk is not None and blk < exit_thresholds["block_up_ratio_lt"]):
        return "EXIT"

    # ---- WARNING ----
    if (rrg_q == warning["rrg_quadrant_eq"]) \
            or (breadth is not None and breadth < warning["breadth_50d_lt"]) \
            or (cmf is not None and cmf < warning["cmf21_lt"]) \
            or (obv_div is warning["obv_divergence_eq"]) \
            or (dist is not None and dist >= warning["dist_days_25_gte"]):
        return "WARNING"

    # ---- STAGE 2 BULLISH (the gate is strict) ----
    if (stage == bullish["stage_eq"]) and (rrg_q == bullish["rrg_quadrant_eq"]) \
            and (breadth is not None and breadth >= bullish["breadth_50d_gte"]) \
            and (cmf is not None and cmf > bullish["cmf21_gt"]) \
            and (nf5d is not None and nf5d >= bullish["etf_flow_5d_pct_gte"]):
        return "STAGE_2_BULLISH"

    # ---- HOLD (Stage 2 intact but not strict-Bullish gate) ----
    if stage == STATE_MACHINE_THRESHOLDS["hold"]["stage_eq"]:
        return "HOLD"

    # ---- STAGE 1 BASING ----
    if stage == STATE_MACHINE_THRESHOLDS["stage_1_basing"]["stage_eq"]:
        return "STAGE_1_BASING"

    return "HOLD"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _transition_date(now: datetime | None = None) -> str:
    current = now or _now_utc()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(EASTERN_TZ).date().isoformat()


def apply_state_machine(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'state' column. Reads + writes state.json so transitions persist."""
    prior = _load_state()
    df = scored_df.copy()
    today = _transition_date()
    new_states = []
    transitions = []
    for tkr, row in df.iterrows():
        s = decide_state(row)
        old = prior.get(tkr, {}).get("state")
        if old and old != s:
            transitions.append({"ticker": tkr, "from": old, "to": s, "date": today})
        new_states.append(s)
    df["state"] = new_states
    df["prior_state"] = [prior.get(t, {}).get("state") for t in df.index]
    _save_state({tkr: {"state": s, "date": today} for tkr, s in zip(df.index, new_states)}, transitions)
    return df


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f).get("by_ticker", {})
        except Exception:
            return {}
    return {}


def _save_state(by_ticker: dict, transitions: list[dict]) -> None:
    payload = {"updated": datetime.now(timezone.utc).isoformat(), "by_ticker": by_ticker}
    # keep a small rolling alert log
    log = []
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                log = json.load(f).get("transitions", [])
        except Exception:
            log = []
    log.extend(transitions)
    payload["transitions"] = log[-500:]   # cap to last 500 transitions
    with open(STATE_FILE, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    if transitions:
        _send_transition_alerts(transitions)


def _send_transition_alerts(transitions: list[dict]) -> None:
    try:
        from .alerts import send_transition_alerts

        send_transition_alerts(transitions)
    except Exception:
        pass


def recent_transitions(n: int = 25) -> list[dict]:
    if not STATE_FILE.exists():
        return []
    try:
        with open(STATE_FILE, "r") as f:
            d = json.load(f)
        return list(reversed(d.get("transitions", [])))[:n]
    except Exception:
        return []
