"""Master composite scoring + state machine.

Formulas track §5 and §6 of sector-rotation-methodology.md exactly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .universe import class_of, TOP_N
from .macro import cycle_tilt


STATE_FILE = Path(__file__).resolve().parent.parent / "state.json"

STATES = ["STAGE_2_BULLISH", "HOLD", "WARNING", "EXIT", "BEARISH_STAGE_4", "STAGE_1_BASING"]


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
) -> pd.DataFrame:
    """Master composite S_i per §5.  Cross-sectional z-scoring is done within
    each universe class so we don't compare a country ETF against a US sector."""
    df = indicators_df.copy()
    df = df.join(flow_df, how="left")
    df["F_score"] = flow_z

    # Universe class for grouped z-scoring
    df["class"] = [class_of(t) for t in df.index]
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
        filters_norm = filters / 3.0
        z_m121 = _z(sub["mom_12_1"])
        z_mans = _z(sub["mansfield_rs"])
        z_rsr = _z(sub["rs_ratio"])
        z_rsm = _z(sub["rs_momentum"])
        z_F = _z(sub["F_score"])
        sub["S_score"] = (
            0.22 * z_m121
            + 0.12 * z_mans
            + 0.15 * z_rsr
            + 0.08 * z_rsm
            + 0.12 * filters_norm
            + 0.08 * sub["cycle_tilt"]
            + 0.23 * z_F
        )
        # Hard veto: F_i < -0.5σ kills the ranking even if S is high
        sub["veto"] = (z_F < -0.5).fillna(False)
        sub["S_score_after_veto"] = sub["S_score"].where(~sub["veto"], other=-9.99)
        sub["rank_in_class"] = sub["S_score_after_veto"].rank(ascending=False, method="min")
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

    # ---- BEARISH (Stage 4) ----
    if (above is False) and (slope_pos is False) and (mans is not None and mans < 0) \
            and (cmf is not None and cmf < -0.10):
        return "BEARISH_STAGE_4"

    # ---- EXIT ----
    if (above is False) \
            or (mans is not None and mans < 0) \
            or (ant == 0) \
            or (rrg_q == "Lagging") \
            or (cmf is not None and cmf < -0.10) \
            or (nf5d is not None and nf5d < -1.5) \
            or (blk is not None and blk < 0.7):
        return "EXIT"

    # ---- WARNING ----
    if (rrg_q == "Weakening") \
            or (breadth is not None and breadth < 0.50) \
            or (cmf is not None and cmf < 0) \
            or (obv_div is True) \
            or (dist is not None and dist >= 4):
        return "WARNING"

    # ---- STAGE 2 BULLISH (the gate is strict) ----
    if (stage == 2) and (rrg_q == "Leading") \
            and (breadth is not None and breadth >= 0.60) \
            and (cmf is not None and cmf > 0.05) \
            and (nf5d is not None and nf5d >= 0):
        return "STAGE_2_BULLISH"

    # ---- HOLD (Stage 2 intact but not strict-Bullish gate) ----
    if stage == 2:
        return "HOLD"

    # ---- STAGE 1 BASING ----
    if stage == 1:
        return "STAGE_1_BASING"

    return "HOLD"


def apply_state_machine(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'state' column. Reads + writes state.json so transitions persist."""
    prior = _load_state()
    df = scored_df.copy()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
