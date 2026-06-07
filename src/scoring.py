"""Master composite scoring + state machine.

Formulas track §5 and §6 of sector-rotation-methodology.md exactly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import threading
from typing import Mapping, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .universe import class_of, TOP_N
from .macro import cycle_tilt


ROOT = Path(__file__).resolve().parent.parent
LEGACY_STATE_FILE = ROOT / "state.json"
DEFAULT_STATE_DIR = ROOT / "data"
_STATE_FILE_EXPLICIT = "STATE_FILE" in os.environ
STATE_FILE = Path(os.environ.get("STATE_FILE", DEFAULT_STATE_DIR / "state.json"))
STATE_TRANSITION_JOURNAL = (
    Path(os.environ["STATE_TRANSITION_JOURNAL"])
    if os.environ.get("STATE_TRANSITION_JOURNAL")
    else None
)
_STATE_LOCK = threading.RLock()
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

def _nullable_bool(value) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value):
            return None
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0"}:
        return False
    return None


def _nullable_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if not pd.isna(parsed) else None


def _nullable_int(value) -> int | None:
    number = _nullable_float(value)
    if number is None:
        return None
    return int(number)


def _provider_gate_live(row: pd.Series, field: str) -> bool:
    if field not in row:
        return True
    parsed = _nullable_bool(row.get(field))
    return bool(parsed)


def decide_state(row: pd.Series) -> str:
    """Pure-function state assignment for a ticker given today's indicators.

    Implements §6 of the methodology.  Conservative ordering: check the
    worst states first so we never under-classify a deteriorating sector.
    """
    stage = _nullable_int(row.get("stage"))
    above = _nullable_bool(row.get("above_30wma"))
    slope_pos = _nullable_bool(row.get("ma_slope_pos"))
    mans = _nullable_float(row.get("mansfield_rs"))
    ant = _nullable_int(row.get("antonacci"))
    rrg_q = row.get("rrg_quadrant")
    breadth = _nullable_float(row.get("breadth_50d"))
    cmf = _nullable_float(row.get("cmf21"))
    rvol = _nullable_float(row.get("rvol"))
    nf5d = _nullable_float(row.get("etf_flow_5d_pct"))
    blk = _nullable_float(row.get("block_up_ratio"))
    nf5d_live = _provider_gate_live(row, "etf_flow_5d_pct_live")
    blk_live = _provider_gate_live(row, "block_up_ratio_live")
    obv_div = _nullable_bool(row.get("obv_divergence"))
    dist = _nullable_float(row.get("dist_days_25"))
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
            or (nf5d_live and nf5d is not None and nf5d < exit_thresholds["etf_flow_5d_pct_lt"]) \
            or (blk_live and blk is not None and blk < exit_thresholds["block_up_ratio_lt"]):
        return "EXIT"

    # ---- WARNING ----
    if (rrg_q == warning["rrg_quadrant_eq"]) \
            or (breadth is not None and breadth < warning["breadth_50d_lt"]) \
            or (cmf is not None and cmf < warning["cmf21_lt"]) \
            or (obv_div == warning["obv_divergence_eq"]) \
            or (dist is not None and dist >= warning["dist_days_25_gte"]):
        return "WARNING"

    # ---- STAGE 2 BULLISH (the gate is strict) ----
    if (stage == bullish["stage_eq"]) and (rrg_q == bullish["rrg_quadrant_eq"]) \
            and (breadth is not None and breadth >= bullish["breadth_50d_gte"]) \
            and (cmf is not None and cmf > bullish["cmf21_gt"]) \
            and (not nf5d_live or (nf5d is not None and nf5d >= bullish["etf_flow_5d_pct_gte"])):
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


def _transition_journal_path() -> Path:
    return Path(STATE_TRANSITION_JOURNAL) if STATE_TRANSITION_JOURNAL else STATE_FILE.with_name("state_transitions.jsonl")


def _state_backup_dir() -> Path:
    return STATE_FILE.with_name("state_backups")


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp_path, path)


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _maybe_migrate_legacy_state() -> None:
    if _STATE_FILE_EXPLICIT or STATE_FILE.exists() or not LEGACY_STATE_FILE.exists():
        return
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_STATE_FILE, STATE_FILE)
    except Exception:
        pass


def _backup_existing_state(payload: Mapping[str, object]) -> None:
    if not payload:
        return
    try:
        backup_dir = _state_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        today = _transition_date()
        _atomic_write_json(backup_dir / "state-latest.json", payload)
        _atomic_write_json(backup_dir / f"state-{today}.json", payload)
    except Exception:
        pass


def _normalize_transition(row: Mapping[str, object]) -> dict:
    return {
        "ticker": str(row.get("ticker", "")).upper(),
        "from": str(row.get("from", "")),
        "to": str(row.get("to", "")),
        "date": str(row.get("date", "")),
    }


def _transition_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    normalized = _normalize_transition(row)
    return (
        normalized["ticker"],
        normalized["from"],
        normalized["to"],
        normalized["date"],
    )


def _read_transition_journal() -> list[dict]:
    journal_path = _transition_journal_path()
    if not journal_path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                rows.append(_normalize_transition(parsed))
    except Exception:
        return rows
    return rows


def _append_transition_journal(transitions: list[dict]) -> None:
    if not transitions:
        return
    journal_path = _transition_journal_path()
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    existing_keys = {_transition_key(row) for row in _read_transition_journal()}
    new_rows = [
        _normalize_transition(row)
        for row in transitions
        if _transition_key(row) not in existing_keys
    ]
    if not new_rows:
        return
    with journal_path.open("a", encoding="utf-8") as f:
        for row in new_rows:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _ensure_transition_journal_file() -> None:
    journal_path = _transition_journal_path()
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.touch(exist_ok=True)


def _seed_transition_journal(snapshot_transitions: list[dict]) -> None:
    journal_path = _transition_journal_path()
    if journal_path.exists() or not snapshot_transitions:
        return
    _append_transition_journal(snapshot_transitions)


def _state_payload() -> dict:
    _maybe_migrate_legacy_state()
    return _read_json_file(STATE_FILE)


def _load_state() -> dict:
    return dict(_state_payload().get("by_ticker", {}) or {})


def _save_state(by_ticker: dict, transitions: list[dict]) -> None:
    with _STATE_LOCK:
        existing_payload = _state_payload()
        _backup_existing_state(existing_payload)
        log = list(existing_payload.get("transitions", []) or [])
        _seed_transition_journal(log)
        normalized_transitions = [_normalize_transition(row) for row in transitions]
        _append_transition_journal(normalized_transitions)
        _ensure_transition_journal_file()
        log.extend(normalized_transitions)
        payload = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "by_ticker": by_ticker,
            "transitions": log[-500:],   # cap snapshot; journal remains append-only
            "transition_journal": str(_transition_journal_path()),
        }
        _atomic_write_json(STATE_FILE, payload)
    if transitions:
        _send_transition_alerts(transitions)


def _send_transition_alerts(transitions: list[dict]) -> None:
    try:
        from .alerts import send_transition_alerts

        send_transition_alerts(transitions)
    except Exception:
        pass


def recent_transitions(n: int = 25) -> list[dict]:
    with _STATE_LOCK:
        payload = _state_payload()
        snapshot_transitions = list(payload.get("transitions", []) or [])
        _seed_transition_journal(snapshot_transitions)
        journal_rows = _read_transition_journal()
        source_rows = journal_rows if journal_rows else snapshot_transitions
        return list(reversed(source_rows))[:n]


def state_storage_health() -> dict[str, object]:
    """Return observability for Pi/local state persistence."""
    with _STATE_LOCK:
        payload = _state_payload()
        snapshot_transitions = list(payload.get("transitions", []) or [])
        _seed_transition_journal(snapshot_transitions)
        if STATE_FILE.exists() or payload.get("by_ticker"):
            _ensure_transition_journal_file()
        journal_rows = _read_transition_journal()
        latest_transition = journal_rows[-1] if journal_rows else (snapshot_transitions[-1] if snapshot_transitions else {})
        return {
            "state_file": str(STATE_FILE),
            "state_file_exists": STATE_FILE.exists(),
            "state_updated": payload.get("updated", ""),
            "by_ticker_count": len(payload.get("by_ticker", {}) or {}),
            "snapshot_transition_count": len(snapshot_transitions),
            "transition_journal": str(_transition_journal_path()),
            "transition_journal_exists": _transition_journal_path().exists(),
            "journal_transition_count": len(journal_rows),
            "latest_transition_date": latest_transition.get("date", "") if isinstance(latest_transition, dict) else "",
            "backup_dir": str(_state_backup_dir()),
            "backup_dir_exists": _state_backup_dir().exists(),
        }
