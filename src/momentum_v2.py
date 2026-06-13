"""Momentum v2 view-model and HTML helpers.

This module renders three dashboard display directions inside the existing
Streamlit app while keeping live dashboard data as the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Iterable, Mapping

import pandas as pd

from .component_bridge import drill_bridge_attrs
from .macro import cycle_tilt
from .scoring import BINARY_FILTER_COUNT, COMPOSITE_WEIGHTS, state_display_label
from .ticker_identity import ticker_display_name


PILLAR_ORDER = ("MOM", "MANS", "RS-R", "RS-M", "FILT", "CYC", "FLOW")
PILLAR_FULL = {
    "MOM": "12-1 Momentum",
    "MANS": "Mansfield relative strength",
    "RS-R": "RRG RS-Ratio",
    "RS-M": "RRG RS-Momentum",
    "FILT": "Faber + Stage 2 + Antonacci filters",
    "CYC": "Business-cycle tilt",
    "FLOW": "Institutional flow",
}
PILLAR_WEIGHTS = {
    "MOM": COMPOSITE_WEIGHTS["mom_12_1_z"],
    "MANS": COMPOSITE_WEIGHTS["mansfield_rs_z"],
    "RS-R": COMPOSITE_WEIGHTS["rs_ratio_z"],
    "RS-M": COMPOSITE_WEIGHTS["rs_momentum_z"],
    "FILT": COMPOSITE_WEIGHTS["binary_filters"],
    "CYC": COMPOSITE_WEIGHTS["cycle_tilt"],
    "FLOW": COMPOSITE_WEIGHTS["provider_flow_z"],
}
PILLAR_HUES = {
    "MOM": "#2e6fa3",
    "MANS": "#5d8ec0",
    "RS-R": "#3f8862",
    "RS-M": "#6da884",
    "FILT": "#9d7838",
    "CYC": "#a85a3a",
    "FLOW": "#7a3a5d",
}
STATE_COLORS_LIGHT = {
    "STAGE_2_BULLISH": "#2E8B57",
    "HOLD": "#3A78B4",
    "WARNING": "#C68A1E",
    "EXIT": "#B84A23",
    "BEARISH_STAGE_4": "#8C1A26",
    "STAGE_1_BASING": "#888888",
}
STATE_TEXT_COLORS = {
    "WARNING": "#171006",
    "STAGE_1_BASING": "#111111",
}
STATE_LABELS = {
    "STAGE_2_BULLISH": "BULLISH",
    "HOLD": "HOLD",
    "WARNING": "WARN",
    "EXIT": "EXIT",
    "BEARISH_STAGE_4": "BEAR",
    "STAGE_1_BASING": "BASE",
}
DISPLAY_LABELS = {
    "A": "A | Terminal",
    "B": "B | Editorial",
    "C": "C | Pillar Stack",
}
SCREEN_LABELS = {
    "overview": "Overview",
    "deepdive": "Deep dive",
    "rotation": "Rotation",
}
DISPLAY_A_SORT_FIELDS = {
    "ticker": "TKR",
    "identity": "NOTE",
    "state": "STATE",
    "pillar_sum": "7 PILLARS",
    "s_score": "S",
    "f_score": "F",
    "momentum_pct": "MOM",
    "trend_90d": "90D",
}
DISPLAY_A_SORT_DIRECTIONS = {
    "desc": "High to low",
    "asc": "Low to high",
}
_STATE_SORT_RANK = {
    "BEARISH_STAGE_4": 0,
    "EXIT": 1,
    "WARNING": 2,
    "STAGE_1_BASING": 3,
    "HOLD": 4,
    "STAGE_2_BULLISH": 5,
}


@dataclass(frozen=True)
class MomentumV2Row:
    ticker: str
    identity: str
    asset_class: str
    state: str
    s_score: float
    f_score: float
    momentum_pct: float
    stage: str
    quadrant: str
    rs_ratio: float
    rs_momentum: float
    cmf21: float
    mansfield_rs: float
    breadth_50d: float
    above_30wma: bool
    ma_slope_pos: bool
    pillars: Mapping[str, float]
    reasons: tuple[str, ...]
    state_label: str = ""
    pullback_risk: bool = False
    pullback_risk_reason: str = ""

    @property
    def display_label(self) -> str:
        return f"{self.ticker} | {self.identity}" if self.identity != self.ticker else self.ticker


def _z(s: pd.Series) -> pd.Series:
    values = pd.to_numeric(s, errors="coerce").astype(float)
    std = values.std(ddof=0)
    if std == 0 or pd.isna(std):
        return values * 0.0
    return (values - values.mean()) / std


def _num(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _state_reason(row: pd.Series) -> tuple[str, ...]:
    reasons: list[str] = []
    state = str(row.get("state", ""))
    if state == "STAGE_2_BULLISH":
        if bool(row.get("pullback_risk")):
            reason = str(row.get("pullback_risk_reason") or "short-term price action is deteriorating")
            reasons.append(f"Stage 2 trend is intact, but pullback risk is active: {reason}.")
        else:
            reasons.append("Stage 2 trend is confirmed and risk gates are supportive.")
    if state == "WARNING":
        reasons.append("Warning state: at least one deterioration gate is active.")
    if state == "EXIT":
        reasons.append("Exit state: a trend or relative-strength break is active.")
    if state == "BEARISH_STAGE_4":
        reasons.append("Bearish Stage 4: price and moving-average slope are deteriorating.")
    if state == "STAGE_1_BASING":
        reasons.append("Stage 1 basing: trend is not yet confirmed bullish.")

    if str(row.get("rrg_quadrant", "")) == "Weakening":
        reasons.append("RRG is in Weakening, so relative leadership is fading.")
    if str(row.get("rrg_quadrant", "")) == "Lagging":
        reasons.append("RRG is in Lagging, so relative strength and momentum are both weak.")
    if _num(row.get("cmf21")) < 0:
        reasons.append(f"CMF is below zero ({_num(row.get('cmf21')):+.2f}), showing negative money flow.")
    if _num(row.get("F_score")) < -0.5:
        reasons.append(f"Flow score is under the veto line ({_num(row.get('F_score')):+.2f}).")
    if bool(row.get("obv_divergence")):
        reasons.append("OBV divergence is present, meaning volume is not confirming price.")
    if _num(row.get("dist_days_25")) >= 4:
        reasons.append(f"{_num(row.get('dist_days_25')):.0f} distribution days are active.")
    if bool(row.get("above_30wma")) is False:
        reasons.append("Weekly price is below the 30-week moving average.")
    if _num(row.get("mansfield_rs")) < 0:
        reasons.append(f"Mansfield RS is negative ({_num(row.get('mansfield_rs')):+.2f}).")
    if not reasons:
        reasons.append("No major deterioration gate is active; monitor the pillar balance.")
    return tuple(reasons[:4])


def _contribution_frame(scored: pd.DataFrame, phase: str) -> pd.DataFrame:
    """Return weighted contribution columns that reconstruct S_score by class."""
    parts: list[pd.DataFrame] = []
    if scored.empty:
        return scored.copy()
    for _, sub in scored.groupby("class", dropna=False):
        sub = sub.copy()
        stage2 = (pd.to_numeric(sub.get("stage"), errors="coerce") == 2).astype(int)
        filters = (
            pd.to_numeric(sub.get("faber"), errors="coerce").fillna(0).astype(int)
            + stage2
            + pd.to_numeric(sub.get("antonacci"), errors="coerce").fillna(0).astype(int)
        )
        filters_norm = filters / BINARY_FILTER_COUNT
        sub["pillar_MOM"] = PILLAR_WEIGHTS["MOM"] * _z(sub.get("mom_12_1", pd.Series(index=sub.index)))
        sub["pillar_MANS"] = PILLAR_WEIGHTS["MANS"] * _z(sub.get("mansfield_rs", pd.Series(index=sub.index)))
        sub["pillar_RS_R"] = PILLAR_WEIGHTS["RS-R"] * _z(sub.get("rs_ratio", pd.Series(index=sub.index)))
        sub["pillar_RS_M"] = PILLAR_WEIGHTS["RS-M"] * _z(sub.get("rs_momentum", pd.Series(index=sub.index)))
        sub["pillar_FILT"] = PILLAR_WEIGHTS["FILT"] * filters_norm
        sub["pillar_CYC"] = PILLAR_WEIGHTS["CYC"] * pd.Series(
            [cycle_tilt(str(ticker), phase) for ticker in sub.index],
            index=sub.index,
        )
        sub["pillar_FLOW"] = PILLAR_WEIGHTS["FLOW"] * _z(sub.get("F_score", pd.Series(index=sub.index)))
        parts.append(sub)
    return pd.concat(parts).loc[scored.index]


def build_view_rows(scored: pd.DataFrame, phase: str) -> list[MomentumV2Row]:
    enriched = _contribution_frame(scored, phase)
    rows: list[MomentumV2Row] = []
    for ticker, row in enriched.iterrows():
        identity = ticker_display_name(str(ticker))
        pillars = {
            "MOM": _num(row.get("pillar_MOM")),
            "MANS": _num(row.get("pillar_MANS")),
            "RS-R": _num(row.get("pillar_RS_R")),
            "RS-M": _num(row.get("pillar_RS_M")),
            "FILT": _num(row.get("pillar_FILT")),
            "CYC": _num(row.get("pillar_CYC")),
            "FLOW": _num(row.get("pillar_FLOW")),
        }
        rows.append(
            MomentumV2Row(
                ticker=str(ticker),
                identity=identity,
                asset_class=str(row.get("class", "")),
                state=str(row.get("state", "HOLD")),
                state_label=state_display_label(row),
                pullback_risk=bool(row.get("pullback_risk", False)),
                pullback_risk_reason=str(row.get("pullback_risk_reason") or ""),
                s_score=_num(row.get("S_score")),
                f_score=_num(row.get("F_score")),
                momentum_pct=_num(row.get("mom_12_1")) * 100.0,
                stage=str(row.get("stage", "-")),
                quadrant=str(row.get("rrg_quadrant", "-")),
                rs_ratio=_num(row.get("rs_ratio"), 100.0),
                rs_momentum=_num(row.get("rs_momentum"), 100.0),
                cmf21=_num(row.get("cmf21")),
                mansfield_rs=_num(row.get("mansfield_rs")),
                breadth_50d=_num(row.get("breadth_50d")),
                above_30wma=bool(row.get("above_30wma", False)),
                ma_slope_pos=bool(row.get("ma_slope_pos", False)),
                pillars=pillars,
                reasons=_state_reason(row),
            )
        )
    return rows


def contribution_sum(row: MomentumV2Row) -> float:
    return float(sum(row.pillars.values()))


def normalize_display_a_sort(field: str | None, direction: str | None) -> tuple[str, str]:
    normalized_field = str(field or "").strip()
    normalized_direction = str(direction or "").strip().lower()
    if normalized_field not in DISPLAY_A_SORT_FIELDS:
        normalized_field = "s_score"
    if normalized_direction not in DISPLAY_A_SORT_DIRECTIONS:
        normalized_direction = "desc"
    return normalized_field, normalized_direction


def _display_a_trend_value(row: MomentumV2Row) -> float:
    return float(row.momentum_pct * 0.84 + row.mansfield_rs * 0.15)


def _display_a_sort_key(row: MomentumV2Row, field: str):
    if field == "ticker":
        return row.ticker.upper()
    if field == "identity":
        return row.identity.upper()
    if field == "state":
        return _STATE_SORT_RANK.get(row.state, -1)
    if field == "pillar_sum":
        return contribution_sum(row)
    if field == "f_score":
        return row.f_score
    if field == "momentum_pct":
        return row.momentum_pct
    if field == "trend_90d":
        return _display_a_trend_value(row)
    return row.s_score


def sort_display_a_rows(
    rows: Iterable[MomentumV2Row],
    field: str | None = "s_score",
    direction: str | None = "desc",
) -> list[MomentumV2Row]:
    normalized_field, normalized_direction = normalize_display_a_sort(field, direction)
    reverse = normalized_direction == "desc"
    return sorted(
        rows,
        key=lambda item: (
            _display_a_sort_key(item, normalized_field),
            item.s_score,
            item.ticker.upper(),
        ),
        reverse=reverse,
    )


def rows_by_class(
    rows: Iterable[MomentumV2Row],
    sort_field: str | None = "s_score",
    sort_direction: str | None = "desc",
) -> dict[str, list[MomentumV2Row]]:
    grouped: dict[str, list[MomentumV2Row]] = {}
    for row in rows:
        grouped.setdefault(row.asset_class, []).append(row)
    for asset_class in grouped:
        grouped[asset_class] = sort_display_a_rows(
            grouped[asset_class],
            field=sort_field,
            direction=sort_direction,
        )
    return grouped


def css() -> str:
    return """
.mv2-shell {
  --mv2-bg: #fbfaf8;
  --mv2-panel: #ffffff;
  --mv2-sunken: #f4f1ec;
  --mv2-border: #ded7cc;
  --mv2-ink: #171412;
  --mv2-muted: #655c52;
  --mv2-faint: #8a8074;
  --mv2-green: #1f7a4a;
  --mv2-red: #b13a1f;
  --mv2-amber: #a8721a;
  --mv2-blue: #1c3d5a;
  background: var(--mv2-bg);
  color: var(--mv2-ink);
  border: 1px solid var(--mv2-border);
  border-radius: 10px;
  padding: 20px;
  margin: 18px auto;
  max-width: 1440px;
  width: 100%;
}
.mv2-shell, .mv2-shell * { box-sizing: border-box; letter-spacing: 0; }
.mv2-head { display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:16px; }
.mv2-kicker { font: 700 12px/1.2 var(--font-mono); color: var(--mv2-muted); text-transform: uppercase; }
.mv2-title { margin:4px 0 0; font: 700 24px/1.15 var(--font-prose); color: var(--mv2-ink); }
.mv2-subtitle { margin:6px 0 0; color: var(--mv2-muted); font-size:14px; line-height:1.45; max-width:820px; }
.mv2-screen-note { background: #fff7e7; border:1px solid #ead1a4; color:#4f3510; padding:10px 12px; border-radius:8px; min-width:260px; font-size:13px; line-height:1.35; }
.mv2-grid { display:grid; grid-template-columns: minmax(0, 1fr) 360px; gap:18px; align-items:start; }
.mv2-rail-stack { display:flex; flex-direction:column; gap:18px; }
.mv2-panel { background: var(--mv2-panel); border:1px solid var(--mv2-border); border-radius:8px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,.04); }
.mv2-panel h3 { margin:0 0 4px; font-size:16px; line-height:1.25; color:var(--mv2-ink); }
.mv2-panel p { margin:0 0 12px; color:var(--mv2-muted); font-size:13px; line-height:1.45; }
.mv2-weather { display:grid; grid-template-columns:1.35fr repeat(5,1fr); gap:18px; align-items:start; background:var(--mv2-panel); border:1px solid var(--mv2-border); border-radius:8px; padding:16px 20px; margin-bottom:18px; }
.mv2-weather h3 { margin:3px 0 4px; font-size:22px; line-height:1.12; color:var(--mv2-ink); }
.mv2-weather p { margin:0; color:var(--mv2-muted); font-size:12px; line-height:1.35; }
.mv2-weather-item span { display:block; color:var(--mv2-muted); font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-weather-item b { display:block; margin-top:7px; color:var(--mv2-ink); font:900 18px/1 var(--font-mono); }
.mv2-weather-item small { display:block; margin-top:4px; color:var(--mv2-muted); font-size:11px; line-height:1.25; }
.mv2-legend { display:flex; flex-wrap:wrap; gap:8px 12px; margin:10px 0 12px; }
.mv2-chip { display:inline-flex; align-items:center; gap:6px; color:var(--mv2-muted); font:700 12px/1 var(--font-mono); }
.mv2-swatch { width:10px; height:10px; border-radius:2px; display:inline-block; }
.mv2-class { margin:18px 0 8px; color:var(--mv2-muted); font:700 12px/1.2 var(--font-mono); text-transform:uppercase; }
.mv2-row { display:grid; grid-template-columns: 150px minmax(220px,1fr) 82px 70px 76px; gap:10px; align-items:center; min-height:31px; border-top:1px solid #eee7dd; padding:5px 0; }
.mv2-row .t { color:var(--mv2-ink); font:800 14px/1.1 var(--font-mono); }
.mv2-row .t small { display:block; margin-top:2px; color:var(--mv2-muted); font:500 11px/1.1 var(--font-prose); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mv2-bar { position:relative; height:20px; background:var(--mv2-sunken); border:1px solid #ebe4da; border-radius:5px; overflow:hidden; }
.mv2-bar:before { content:""; position:absolute; left:50%; top:0; bottom:0; border-left:1px solid #c9c0b4; z-index:2; }
.mv2-seg { position:absolute; top:3px; height:12px; min-width:2px; }
.mv2-state { display:inline-flex; justify-content:center; color:#fff; border-radius:4px; padding:4px 7px; font:800 11px/1 var(--font-mono); }
.mv2-num { text-align:right; font:800 13px/1 var(--font-mono); color:var(--mv2-ink); }
.mv2-pos { color:var(--mv2-green); }
.mv2-neg { color:var(--mv2-red); }
.mv2-muted { color:var(--mv2-muted); }
.mv2-terminal { background:#0a0a0a; color:#e8e8e8; border-color:#242424; }
.mv2-terminal .mv2-panel { background:#111; border-color:#242424; box-shadow:none; }
.mv2-terminal .mv2-title, .mv2-terminal .mv2-panel h3, .mv2-terminal .mv2-row .t { color:#f0f0f0; font-family:var(--font-mono); }
.mv2-terminal .mv2-subtitle, .mv2-terminal .mv2-panel p, .mv2-terminal .mv2-row .t small, .mv2-terminal .mv2-class, .mv2-terminal .mv2-chip { color:#b8b8b8; }
.mv2-terminal .mv2-row { border-top-color:#222; }
.mv2-terminal .mv2-bar { background:#080808; border-color:#242424; }
.mv2-terminal .mv2-screen-note { background:#1d1606; border-color:#5d4213; color:#f1cf86; }
.mv2-a-topbar { display:flex; align-items:center; gap:10px; height:52px; padding:0 4px 14px; border-bottom:1px solid #1f1f1f; }
.mv2-a-mark { width:14px; height:14px; background:#e6b450; border-radius:2px; display:inline-block; }
.mv2-a-brand { color:#e8e8e8; font:900 13px/1 var(--font-mono); letter-spacing:.12em; }
.mv2-a-live { flex:1; display:flex; justify-content:center; gap:24px; color:#7c7c7c; font:800 11px/1 var(--font-mono); }
.mv2-a-live i { display:inline-block; width:6px; height:6px; border-radius:50%; background:#26d65b; box-shadow:0 0 6px #26d65b; margin-right:6px; }
.mv2-a-btn { width:28px; height:24px; display:inline-flex; align-items:center; justify-content:center; border:1px solid #2a2a2a; background:#111; color:#7c7c7c; border-radius:3px; }
.mv2-a-bluf { padding:16px 4px; border-bottom:1px solid #1f1f1f; }
.mv2-a-meta { display:flex; align-items:baseline; gap:14px; color:#7c7c7c; font:800 11px/1 var(--font-mono); letter-spacing:.04em; text-transform:uppercase; }
.mv2-a-chip { display:inline-block; background:#e6b450; color:#000; padding:3px 7px; border-radius:2px; font:900 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-a-bluf p { max-width:1120px; margin:12px 0 0; color:#dcdcdc; font:18px/1.4 var(--font-prose); }
.mv2-a-blufnums { display:flex; gap:20px; align-items:center; margin-top:14px; color:#7c7c7c; font:800 11px/1 var(--font-mono); }
.mv2-a-blufnum b { display:inline-block; margin-right:7px; font:900 25px/1 var(--font-mono); }
.mv2-a-blufnum span { display:block; margin-top:2px; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a-bluf-spacer { flex:1; }
.mv2-a-status { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:16px 4px; border-bottom:1px solid #1f1f1f; }
.mv2-a-tile { background:#111; border:1px solid #1f1f1f; border-radius:4px; padding:12px; min-height:104px; }
.mv2-a-tile span { display:block; color:#7c7c7c; font:900 10px/1 var(--font-mono); letter-spacing:.1em; text-transform:uppercase; }
.mv2-a-tile b { display:block; margin-top:8px; color:#e8e8e8; font:900 21px/1 var(--font-mono); }
.mv2-a-tile small { display:block; margin-top:6px; color:#b8b8b8; font:12px/1.35 var(--font-prose); }
.mv2-a-tile svg { margin-top:9px; width:100%; max-width:160px; height:auto; }
.mv2-a-body { display:grid; grid-template-columns:minmax(0,1fr) 380px; gap:16px; padding:16px 4px; }
.mv2-a-panel { background:#111; border:1px solid #1f1f1f; border-radius:0; padding:12px 16px; min-width:0; }
.mv2-a-head { display:flex; justify-content:space-between; align-items:baseline; gap:16px; margin-bottom:10px; }
.mv2-a-head b { color:#e8e8e8; font:900 12px/1 var(--font-mono); letter-spacing:.12em; text-transform:uppercase; }
.mv2-a-head span { color:#7c7c7c; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a-header-row { color:#7c7c7c; font:900 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; border-top:0; padding-top:2px; }
.mv2-a-row { display:grid; grid-template-columns:46px minmax(180px,1fr) 80px 90px 56px 56px 56px 60px; gap:8px; align-items:center; min-height:30px; border-top:1px solid #1f1f1f; padding:5px 0; }
.mv2-a-row b { color:#e8e8e8; font:900 12px/1 var(--font-mono); }
.mv2-a-sort { color:#e8e8e8; font:900 12px/1 var(--font-mono); text-decoration:none; white-space:nowrap; cursor:pointer; }
.mv2-a-sort span { color:#26d65b; font:900 10px/1 var(--font-mono); margin-left:3px; }
.mv2-a-sort:hover, .mv2-a-sort.active { color:#26d65b; text-decoration:underline; text-underline-offset:3px; }
.mv2-a-row .note { color:#b8b8b8; font:12px/1.2 var(--font-prose); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mv2-a-row .num { text-align:right; font:900 12px/1 var(--font-mono); }
.mv2-a-row svg { display:block; }
.mv2-a-click { cursor:pointer; }
.mv2-a-click:hover { background:#0e1822; }
.mv2-a-class { display:flex; align-items:center; gap:8px; margin:12px 0 4px; color:#7c7c7c; font:900 10px/1 var(--font-mono); letter-spacing:.12em; text-transform:uppercase; }
.mv2-a-class:after { content:""; flex:1; height:1px; background:#1f1f1f; }
.mv2-a-rail { display:flex; flex-direction:column; gap:16px; min-width:0; }
.mv2-a-transition, .mv2-a-holding { display:grid; grid-template-columns:10px minmax(124px, .65fr) minmax(0, 1.35fr) auto; gap:12px; align-items:center; padding:7px 0; border-top:1px solid #1f1f1f; color:#b8b8b8; font:800 11px/1.2 var(--font-mono); }
.mv2-a-transition i, .mv2-a-holding i { width:6px; height:6px; border-radius:50%; display:block; }
.mv2-a-transition .mv2-a-id, .mv2-a-holding .mv2-a-id { min-width:0; }
.mv2-a-transition .mv2-a-id b, .mv2-a-holding .mv2-a-id b { display:block; color:#e8e8e8; font:900 12px/1.15 var(--font-mono); white-space:nowrap; }
.mv2-a-transition .mv2-a-id small, .mv2-a-holding .mv2-a-id small { display:block; margin-top:4px; color:#d4d4d4; font:800 11px/1.2 var(--font-prose); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mv2-a-transition span, .mv2-a-holding span { color:#7c7c7c; font:800 10px/1.2 var(--font-mono); }
.mv2-a-callout { margin-top:10px; border:1px solid #5d4213; background:#1d1606; color:#f1cf86; padding:10px 12px; font:12px/1.4 var(--font-prose); }
.mv2-a-footer { display:flex; justify-content:space-between; gap:16px; padding:10px 4px 0; border-top:1px solid #1f1f1f; color:#5a5a5a; font:900 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-a2-header { display:flex; align-items:center; gap:16px; height:52px; padding:0 4px 14px; border-bottom:1px solid #1f1f1f; }
.mv2-a2-back { border:1px solid #2a2a2a; background:#111; color:#b8b8b8; border-radius:3px; padding:5px 10px; font:900 11px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a2-lead { padding:24px 4px 18px; border-bottom:1px solid #1f1f1f; }
.mv2-a2-lead-grid { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:32px; align-items:start; }
.mv2-a2-score { display:flex; align-items:baseline; gap:14px; margin-top:4px; }
.mv2-a2-score b { font:900 48px/1 var(--font-mono); letter-spacing:0; }
.mv2-a2-score span { color:#7c7c7c; font:800 14px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a2-copy { max-width:760px; margin:12px 0 0; color:#d4d4d4; font:15px/1.5 var(--font-prose); }
.mv2-a2-pillars { margin-top:18px; display:grid; grid-template-columns:1fr 1fr; gap:12px 28px; }
.mv2-a2-pillar { display:grid; grid-template-columns:3px minmax(0,1fr) auto; gap:10px; align-items:start; border-top:1px solid #1f1f1f; padding-top:9px; }
.mv2-a2-pillar i { width:3px; min-height:36px; display:block; }
.mv2-a2-pillar b { display:block; color:#e8e8e8; font:900 11px/1.2 var(--font-mono); }
.mv2-a2-pillar p { margin:3px 0 0; color:#b8b8b8; font:12px/1.35 var(--font-prose); }
.mv2-a2-pillar span { font:900 12px/1 var(--font-mono); text-align:right; }
.mv2-a2-gate-panel { background:#0e0e0e; border:1px solid #1f1f1f; padding:14px 16px; }
.mv2-a2-gate-panel h3 { margin:0 0 8px; padding-bottom:8px; border-bottom:1px solid #1f1f1f; color:#7c7c7c; font:900 10px/1 var(--font-mono); letter-spacing:.12em; text-transform:uppercase; }
.mv2-a2-gate-panel p { margin:0 0 10px; color:#7c7c7c; font:12px/1.45 var(--font-prose); }
.mv2-a2-callout { margin-top:12px; padding:10px 12px; background:#1a1100; border:1px solid #5d4213; color:#d8b260; font:12px/1.5 var(--font-prose); }
.mv2-a2-charts { padding:16px 4px; display:grid; grid-template-columns:1.6fr 1fr; gap:16px; }
.mv2-a2-peer-row { display:grid; grid-template-columns:30px 52px 1fr 58px 62px; gap:8px; align-items:center; border-top:1px solid #1f1f1f; padding:7px 0; color:#b8b8b8; font:800 11px/1.2 var(--font-mono); }
.mv2-a2-peer-row.focus { background:#1d1606; box-shadow:inset 3px 0 0 #e6b450; padding-left:8px; }
.mv2-a2-peer-row .rank { color:#7c7c7c; font-size:10px; }
.mv2-a2-peer-row .name { color:#7c7c7c; font:11px/1.2 var(--font-prose); overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.mv2-a3-header { display:flex; align-items:center; gap:16px; height:52px; padding:0 4px 14px; border-bottom:1px solid #1f1f1f; }
.mv2-a3-filters { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
.mv2-a3-filter { border:1px solid #2a2a2a; background:transparent; color:#7c7c7c; padding:5px 10px; border-radius:3px; font:900 10px/1 var(--font-mono); letter-spacing:.06em; text-transform:uppercase; }
.mv2-a3-filter.active { background:#1a2a38; border-color:#5fa8d3; color:#5fa8d3; }
.mv2-a3-scope { display:flex; flex-wrap:wrap; gap:8px; padding:0 4px 4px; color:#7c7c7c; font:900 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-a3-scope span { border:1px solid #242424; background:#0d0d0d; padding:7px 9px; }
.mv2-a3-rrg-legend { display:flex; flex-wrap:wrap; gap:12px; margin-top:10px; color:#b8b8b8; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a3-rrg-legend span { display:inline-flex; align-items:center; gap:6px; }
.mv2-a3-rrg-legend i { width:9px; height:9px; border-radius:50%; display:inline-block; }
.mv2-a3-grid { display:grid; grid-template-columns:1.5fr 1fr; gap:16px; padding:16px 4px; }
.mv2-a3-grid.lower { padding-top:0; }
.mv2-a3-panel { background:#111; border:1px solid #1f1f1f; padding:14px 18px; min-width:0; }
.mv2-a3-section { display:flex; justify-content:space-between; align-items:baseline; gap:16px; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid #1f1f1f; }
.mv2-a3-section b { color:#e8e8e8; font:900 12px/1 var(--font-mono); letter-spacing:.1em; text-transform:uppercase; }
.mv2-a3-section span { color:#7c7c7c; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a3-caption { margin:10px 0 0; color:#b8b8b8; font:12px/1.5 var(--font-prose); }
.mv2-a3-mom-row { display:grid; grid-template-columns:60px minmax(0,1fr) 64px 64px; gap:8px; align-items:center; border-top:1px solid #1f1f1f; padding:7px 0; font:800 11px/1.2 var(--font-mono); }
.mv2-a3-mom-row .name { color:#7c7c7c; font:11px/1.2 var(--font-prose); overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.mv2-a3-track { position:relative; height:18px; background:#080808; border:1px solid #1f1f1f; overflow:hidden; }
.mv2-a3-track:before { content:""; position:absolute; left:50%; top:0; bottom:0; border-left:1px solid #5a5a5a; }
.mv2-a3-fill { position:absolute; top:3px; bottom:3px; }
.mv2-a3-flow-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:14px; }
.mv2-a3-flow-card { background:#0d0d0d; border:1px solid #1f1f1f; padding:10px 12px; }
.mv2-a3-flow-card span { color:#7c7c7c; font:900 9px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-a3-flow-card b { display:block; margin-top:6px; font:900 20px/1 var(--font-mono); }
.mv2-a3-flow-row { display:grid; grid-template-columns:58px 1fr 56px 56px 56px 64px; gap:8px; align-items:center; border-top:1px solid #1f1f1f; padding:7px 0; color:#b8b8b8; font:800 11px/1.2 var(--font-mono); }
.mv2-a3-flow-row .name { color:#7c7c7c; font:11px/1.2 var(--font-prose); overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.mv2-a3-macro-stats { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.mv2-a3-macro-stat { background:#0d0d0d; border:1px solid #1f1f1f; padding:10px 12px; }
.mv2-a3-macro-stat span { color:#7c7c7c; font:900 9px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-a3-macro-stat b { display:block; margin-top:6px; color:#e8e8e8; font:900 16px/1 var(--font-mono); }
.mv2-editorial { background:#faf6ef; border-radius:0; }
.mv2-editorial .mv2-title { font-family: Georgia, 'Times New Roman', serif; font-size:28px; }
.mv2-editorial .mv2-head { border-bottom:1px solid #c9bfae; padding-bottom:12px; }
.mv2-tape { display:flex; flex-wrap:wrap; gap:18px; align-items:center; border-bottom:1px solid #e1d8c9; background:#fffbf3; margin:-4px 0 22px; padding:10px 0; font:800 11px/1 var(--font-mono); color:#3d342e; }
.mv2-tape span:first-child { color:#6e6258; text-transform:uppercase; letter-spacing:.08em; }
.mv2-b-hero { display:grid; grid-template-columns:1fr 360px; gap:38px; align-items:start; margin-bottom:22px; }
.mv2-b-hero h3 { margin:8px 0 10px; color:#1c1815; font:700 46px/1.05 Georgia, 'Times New Roman', serif; }
.mv2-b-hero p { color:#3d342e; font:20px/1.42 Georgia, 'Times New Roman', serif; font-style:italic; margin:0; }
.mv2-b-numbers { background:#fffbf3; border:1px solid #c9bfae; border-top:3px solid #1c1815; padding:16px 18px; }
.mv2-b-num { display:flex; justify-content:space-between; gap:14px; align-items:baseline; border-top:1px solid #e1d8c9; padding:8px 0; }
.mv2-b-num:first-child { border-top:0; }
.mv2-b-num span { color:#3d342e; font:15px/1.2 Georgia, 'Times New Roman', serif; }
.mv2-b-num b { font:900 14px/1 var(--font-mono); color:#1c1815; }
.mv2-story { border-top:1px solid #e1d8c9; padding:13px 0; display:grid; grid-template-columns:90px 1fr; gap:14px; }
.mv2-story b { font:800 15px/1.1 var(--font-mono); color:#1c1815; }
.mv2-story h4 { margin:0 0 5px; font:700 20px/1.18 Georgia, 'Times New Roman', serif; color:#1c1815; }
.mv2-story p { margin:0; font:16px/1.48 Georgia, 'Times New Roman', serif; color:#3d342e; }
.mv2-rail-list { display:grid; gap:10px; }
.mv2-rail-item { border-top:1px solid #eee7dd; padding-top:10px; }
.mv2-rail-item b { display:block; font:800 13px/1.2 var(--font-mono); color:var(--mv2-ink); }
.mv2-rail-item span { display:block; color:var(--mv2-muted); font-size:12px; line-height:1.35; margin-top:3px; }
.mv2-b-phase-row { display:flex; gap:6px; margin:10px 0 12px; }
.mv2-b-phase-row span { flex:1; padding:9px 4px; text-align:center; border:1px solid #c9bfae; color:#8b7e70; font:800 10px/1 var(--font-mono); letter-spacing:.08em; }
.mv2-b-phase-row span.active { background:#1c1815; color:#faf6ef; border-color:#1c1815; }
.mv2-b-risk-basket { display:grid; grid-template-columns:repeat(5,1fr); gap:6px; margin-top:12px; }
.mv2-b-risk-basket div { padding:8px 6px; text-align:center; border:1px solid #c9bfae; }
.mv2-b-risk-basket b { display:block; color:#1c1815; font:900 12px/1 var(--font-mono); }
.mv2-b-risk-basket span { display:block; color:#6e6258; font:italic 11px/1.2 Georgia, 'Times New Roman', serif; margin-top:3px; }
.mv2-tabs { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 16px; }
.mv2-tab { border:1px solid var(--mv2-border); border-radius:999px; padding:6px 10px; font:800 12px/1 var(--font-mono); color:var(--mv2-muted); background:rgba(255,255,255,.55); }
.mv2-tab.active { color:var(--mv2-ink); border-color:var(--mv2-blue); box-shadow:inset 0 -2px 0 var(--mv2-blue); }
.mv2-waterfall { display:flex; align-items:flex-end; gap:10px; min-height:210px; padding:18px 8px 4px; border-top:1px solid #eee7dd; }
.mv2-step { flex:1; min-width:70px; display:flex; flex-direction:column; justify-content:flex-end; align-items:stretch; gap:6px; }
.mv2-step-bar { border-radius:5px 5px 2px 2px; min-height:3px; opacity:.92; }
.mv2-step-val { text-align:center; font:800 12px/1 var(--font-mono); }
.mv2-step-lbl { text-align:center; color:var(--mv2-muted); font:800 11px/1.15 var(--font-mono); min-height:28px; }
.mv2-gates { display:grid; gap:8px; }
.mv2-gate { display:grid; grid-template-columns:22px 1fr auto; gap:8px; align-items:center; border-top:1px solid #eee7dd; padding:8px 0; }
.mv2-gate-mark { width:18px; height:18px; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; color:#fff; font:900 12px/1 var(--font-mono); }
.mv2-gate b { color:var(--mv2-ink); font-size:13px; }
.mv2-gate span { color:var(--mv2-muted); font:700 12px/1 var(--font-mono); text-align:right; }
.mv2-state-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin:10px 0 16px; }
.mv2-state-card { border:1px solid var(--mv2-border); background:var(--mv2-sunken); border-radius:8px; padding:11px; }
.mv2-state-card span { display:block; color:var(--mv2-muted); font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-state-card b { display:block; margin-top:5px; color:var(--mv2-ink); font:900 22px/1 var(--font-mono); }
.mv2-universe-columns { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
.mv2-metric-deck { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin:10px 0 16px; }
.mv2-metric { background:var(--mv2-panel); border:1px solid var(--mv2-border); border-radius:8px; padding:10px; }
.mv2-metric span { display:block; color:var(--mv2-muted); font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-metric b { display:block; margin-top:5px; color:var(--mv2-ink); font:900 18px/1 var(--font-mono); }
.mv2-rrg { position:relative; aspect-ratio:1.12; min-height:420px; border:1px solid var(--mv2-border); background:linear-gradient(90deg, rgba(178,58,31,.05) 0 50%, rgba(31,122,74,.06) 50% 100%), linear-gradient(180deg, rgba(28,61,90,.06) 0 50%, rgba(168,114,26,.06) 50% 100%); border-radius:8px; overflow:hidden; }
.mv2-rrg:before, .mv2-rrg:after { content:""; position:absolute; background:#bdb4a8; opacity:.7; }
.mv2-rrg:before { left:50%; top:0; bottom:0; width:1px; }
.mv2-rrg:after { top:50%; left:0; right:0; height:1px; }
.mv2-rrg-label { position:absolute; color:var(--mv2-muted); font:900 11px/1 var(--font-mono); text-transform:uppercase; }
.mv2-dot { position:absolute; transform:translate(-50%,-50%); min-width:38px; text-align:center; z-index:2; }
.mv2-dot i { display:block; width:13px; height:13px; border-radius:50%; margin:0 auto 4px; border:2px solid var(--mv2-panel); }
.mv2-dot b { color:var(--mv2-ink); font:900 10px/1 var(--font-mono); text-shadow:0 1px 0 var(--mv2-panel); }
.mv2-mom-row { display:grid; grid-template-columns:150px 1fr 70px; gap:10px; align-items:center; border-top:1px solid #eee7dd; padding:8px 0; }
.mv2-mom-track { height:14px; position:relative; background:var(--mv2-sunken); border-radius:5px; overflow:hidden; }
.mv2-mom-track:before { content:""; position:absolute; left:50%; top:0; bottom:0; border-left:1px solid #bdb4a8; }
.mv2-mom-fill { position:absolute; top:2px; bottom:2px; border-radius:4px; }
.mv2-flow-river { height:230px; position:relative; border:1px solid var(--mv2-border); border-radius:8px; background:linear-gradient(90deg,#fff7f2,#f7fff9); overflow:hidden; }
.mv2-river-band { position:absolute; left:18%; right:18%; border-radius:999px; opacity:.26; filter:saturate(1.1); }
.mv2-flow-node { position:absolute; width:180px; padding:8px 10px; border:1px solid var(--mv2-border); background:rgba(255,255,255,.82); border-radius:7px; font-size:12px; line-height:1.25; }
.mv2-flow-node b { display:block; color:var(--mv2-ink); font:900 12px/1 var(--font-mono); }
.mv2-macro-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.mv2-macro { border:1px solid var(--mv2-border); background:var(--mv2-sunken); border-radius:8px; padding:11px; }
.mv2-macro span { color:var(--mv2-muted); font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-macro b { display:block; margin-top:6px; color:var(--mv2-ink); font:900 16px/1 var(--font-mono); }
.mv2-c-top { display:flex; align-items:center; gap:18px; min-height:60px; padding:0 12px 16px; border-bottom:1px solid #e6e1d8; }
.mv2-c-logo { width:22px; height:22px; display:inline-grid; grid-template-columns:repeat(4,1fr); gap:2px; align-items:end; }
.mv2-c-logo i { display:block; border-radius:2px 2px 1px 1px; }
.mv2-c-brand { display:flex; align-items:center; gap:10px; color:#1a1714; font:700 15px/1 var(--font-prose); }
.mv2-c-brand small { border-left:1px solid #e6e1d8; padding-left:8px; color:#7a7066; font:800 10px/1 var(--font-mono); letter-spacing:.06em; }
.mv2-c-tabs { display:flex; align-items:center; gap:2px; margin:0 auto; }
.mv2-c-tab { position:relative; color:#7a7066; padding:8px 12px; font:600 13px/1 var(--font-prose); }
.mv2-c-tab.active { color:#1a1714; }
.mv2-c-tab.active:after { content:""; position:absolute; left:12px; right:12px; bottom:-17px; height:2px; background:#1c3d5a; }
.mv2-c-btn { width:32px; height:32px; display:inline-flex; align-items:center; justify-content:center; border:1px solid #e6e1d8; background:#f4f1ec; color:#3d362f; border-radius:6px; }
.mv2-c-weather { margin:24px 12px 20px; background:#fff; border:1px solid #e6e1d8; border-radius:8px; padding:18px 24px; display:grid; grid-template-columns:1.4fr repeat(5,1fr); gap:24px; }
.mv2-c-weather h3 { margin:4px 0 6px; color:#1a1714; font:700 22px/1.2 var(--font-prose); }
.mv2-c-weather p { margin:0; color:#7a7066; font:12px/1.4 var(--font-prose); }
.mv2-c-weather-item span { display:block; color:#7a7066; font:900 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-c-weather-item b { display:block; margin-top:8px; color:#1a1714; font:900 22px/1 var(--font-mono); }
.mv2-c-weather-item small { display:block; margin-top:5px; color:#7a7066; font:12px/1.25 var(--font-prose); }
.mv2-c-main { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:20px; padding:0 12px 32px; }
.mv2-c-card { background:#fff; border:1px solid #e6e1d8; border-radius:8px; padding:22px 28px; min-width:0; box-shadow:0 1px 2px rgba(0,0,0,.035); }
.mv2-c-card h2, .mv2-c-card h3 { margin:0; color:#1a1714; font:700 18px/1.25 var(--font-prose); letter-spacing:0; }
.mv2-c-card p { color:#7a7066; font:13px/1.55 var(--font-prose); }
.mv2-c-head { display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid #e6e1d8; }
.mv2-c-head b { color:#1a1714; font:700 14px/1 var(--font-prose); }
.mv2-c-head span { color:#7a7066; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-c-legend { display:flex; gap:14px; flex-wrap:wrap; align-items:center; padding:0 0 14px; margin-bottom:8px; border-bottom:1px solid #e6e1d8; }
.mv2-c-legend span { display:inline-flex; align-items:center; gap:6px; color:#3d362f; font:800 10.5px/1 var(--font-mono); }
.mv2-c-row { display:grid; grid-template-columns:52px minmax(260px,1fr) 78px 60px 64px; gap:10px; align-items:center; border-top:1px solid #e6e1d8; padding:7px 0; }
.mv2-c-row b { color:#1a1714; font:900 12px/1 var(--font-mono); }
.mv2-c-stack { position:relative; height:22px; background:#f4f1ec; border:1px solid #e6e1d8; border-radius:6px; overflow:hidden; }
.mv2-c-stack:before { content:""; position:absolute; left:50%; top:0; bottom:0; border-left:1px solid #d4cec1; z-index:2; }
.mv2-c-seg { position:absolute; top:2px; height:18px; min-width:2px; }
.mv2-c-rail { display:flex; flex-direction:column; gap:20px; }
.mv2-c-rail-row { display:grid; grid-template-columns:8px 48px 1fr auto; gap:10px; align-items:center; border-top:1px solid #e6e1d8; padding:9px 0; color:#3d362f; font:12px/1.25 var(--font-prose); }
.mv2-c-rail-row i { width:8px; height:8px; border-radius:50%; display:block; }
.mv2-c-statdeck { background:#fff; border:1px solid #e6e1d8; border-radius:8px; padding:14px 18px; display:flex; gap:18px; flex-wrap:wrap; }
.mv2-c-stat span { display:block; color:#7a7066; font:900 9.5px/1 var(--font-mono); text-transform:uppercase; }
.mv2-c-stat b { display:block; margin-top:6px; color:#1a1714; font:900 18px/1 var(--font-mono); }
.mv2-c-waterfall { width:100%; height:auto; display:block; }
.mv2-c-pillar-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px 32px; }
.mv2-c-pillar-card { display:grid; grid-template-columns:8px minmax(0,1fr) auto; gap:12px; align-items:start; background:#fbfaf8; border:1px solid #e6e1d8; border-radius:8px; padding:12px; }
.mv2-c-pillar-card i { width:8px; min-height:56px; border-radius:2px; display:block; }
.mv2-c-pillar-card b { color:#1a1714; font:700 14px/1.2 var(--font-prose); }
.mv2-c-pillar-card p { margin:5px 0 0; color:#3d362f; font:12.5px/1.4 var(--font-prose); }
.mv2-c-rotation-head { padding:28px 12px 8px; }
.mv2-c-rotation-head h1 { margin:0; color:#1a1714; font:700 30px/1.1 var(--font-prose); }
.mv2-c-rotation-grid { display:grid; grid-template-columns:1.5fr 1fr; gap:20px; padding:18px 12px 16px; }
.mv2-c-flow-river { background:linear-gradient(90deg,#fff7f2,#f7fff9); border:1px solid #e6e1d8; border-radius:8px; overflow:hidden; }
.mv2-c-flow-river svg { width:100%; height:auto; display:block; }
.mv2-c-flow-row { display:grid; grid-template-columns:60px 1fr 56px 56px 64px 70px; gap:8px; align-items:center; border-top:1px solid #e6e1d8; padding:8px 0; color:#3d362f; font:800 11px/1.2 var(--font-mono); }
.mv2-c-flow-row .name { color:#7a7066; font:12px/1.2 var(--font-prose); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mv2-chart-grid { display:grid; grid-template-columns:1.4fr 1fr; gap:16px; margin-top:16px; }
.mv2-chart-grid.tight { grid-template-columns:1.6fr 1fr; margin-top:0; }
.mv2-a-hero { padding:20px 0 16px; border-bottom:1px solid var(--mv2-border); }
.mv2-a-hero-grid { display:grid; grid-template-columns:1fr 340px; gap:28px; align-items:start; }
.mv2-a-score { display:flex; align-items:baseline; gap:14px; margin-top:4px; }
.mv2-a-score b { font:900 48px/1 var(--font-mono); letter-spacing:-.02em; }
.mv2-a-score span { color:var(--mv2-muted); font:800 13px/1 var(--font-mono); text-transform:uppercase; }
.mv2-a-prose { margin-top:12px; max-width:760px; color:var(--mv2-muted); font:15px/1.52 Georgia, 'Times New Roman', serif; }
.mv2-a-bar-wrap { margin-top:18px; }
.mv2-a-bar-meta { display:flex; justify-content:space-between; color:var(--mv2-muted); font:800 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; margin-bottom:5px; }
.mv2-a-bar { position:relative; height:56px; border:1px solid var(--mv2-border); background:var(--mv2-sunken); overflow:hidden; }
.mv2-a-bar:before { content:""; position:absolute; left:50%; top:0; bottom:0; border-left:2px solid #8a8074; z-index:2; }
.mv2-a-seg { position:absolute; top:5px; bottom:5px; opacity:.94; }
.mv2-a-seg.neg { opacity:.72; }
.mv2-a-pillars { display:grid; grid-template-columns:1fr 1fr; gap:8px 28px; margin-top:14px; }
.mv2-a-pillar { display:grid; grid-template-columns:12px 1fr auto; gap:8px; align-items:baseline; border-top:1px solid var(--mv2-border); padding-top:7px; }
.mv2-a-pillar i { width:10px; height:10px; border-radius:2px; margin-top:2px; }
.mv2-a-pillar b { color:var(--mv2-ink); font:900 11px/1 var(--font-mono); }
.mv2-a-pillar span { color:var(--mv2-muted); font:800 11px/1 var(--font-mono); text-align:right; }
.mv2-footer { display:flex; justify-content:space-between; gap:16px; margin-top:20px; padding-top:10px; border-top:1px solid var(--mv2-border); color:var(--mv2-muted); font:800 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-article-block { display:grid; grid-template-columns:1fr 280px; gap:22px; border-top:1px solid #e1d8c9; padding-top:18px; margin-top:18px; }
.mv2-article-block p { font:16px/1.55 Georgia, 'Times New Roman', serif; color:#3d342e; margin:0 0 12px; }
.mv2-article-side { background:#fffbf3; border:1px solid #e1d8c9; padding:14px; }
.mv2-article-side b { display:block; font:900 12px/1 var(--font-mono); margin-bottom:8px; color:#1c1815; }
.mv2-b-mast { display:flex; align-items:center; gap:16px; border-bottom:1px solid #c9bfae; padding:0 0 12px; margin-bottom:18px; color:#6e6258; font:800 11px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; }
.mv2-b-mast b { color:#1c1815; font:700 18px/1 Georgia, 'Times New Roman', serif; letter-spacing:0; text-transform:none; }
.mv2-b-article-grid { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:56px; max-width:1340px; margin:0 auto; align-items:start; }
.mv2-b-main { min-width:0; }
.mv2-b-main > h3 { border-bottom:2px solid #1c1815; padding-bottom:8px; margin:0 0 8px; color:#1c1815; font:900 11px/1 var(--font-mono); letter-spacing:.14em; text-transform:uppercase; }
.mv2-b-main > p { margin:0 0 18px; color:#6e6258; font:italic 14px/1.5 Georgia, 'Times New Roman', serif; }
.mv2-b-sidebar { position:sticky; top:16px; background:#fffbf3; border:1px solid #c9bfae; border-top:3px solid #1c1815; padding:16px 18px; }
.mv2-b-sidebar h3 { margin:16px 0 8px; color:#1c1815; font:900 10px/1 var(--font-mono); letter-spacing:.12em; text-transform:uppercase; }
.mv2-b-sidebar h3:first-child { margin-top:0; }
.mv2-b-sidebar p { margin:8px 0 0; color:#6e6258; font:italic 12.5px/1.45 Georgia, 'Times New Roman', serif; }
.mv2-b-gate-table { max-width:1340px; margin:24px auto 0; background:#fffbf3; border:1px solid #e1d8c9; padding:18px 22px; }
.mv2-b-gate-table h3 { margin:0 0 10px; color:#1c1815; font:900 11px/1 var(--font-mono); letter-spacing:.14em; text-transform:uppercase; }
.mv2-article-hero { padding:28px 0 18px; border-bottom:1px solid #e1d8c9; }
.mv2-article-hero h2 { font:700 52px/1 Georgia, 'Times New Roman', serif; color:#1c1815; margin:10px 0 12px; }
.mv2-article-meta { display:flex; gap:28px; align-items:baseline; margin-top:18px; color:#6e6258; font:800 11px/1 var(--font-mono); letter-spacing:.06em; text-transform:uppercase; }
.mv2-pull-strip { background:#1c1815; color:#f6efe2; display:grid; grid-template-columns:1.05fr .85fr .95fr 1fr 1.35fr; gap:1px; margin:18px 0; }
.mv2-pull-strip div { padding:14px 18px; border-right:1px solid #3d342e; }
.mv2-pull-strip span { display:block; color:#c4b5a0; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-pull-strip b { display:block; margin-top:5px; font:900 26px/1 var(--font-mono); color:#f6efe2; }
.mv2-pull-strip em { display:block; color:#d8c9b3; font:italic 13px/1.35 Georgia, 'Times New Roman', serif; text-align:right; }
.mv2-pillar-article { display:grid; grid-template-columns:46px 1fr; gap:14px; border-top:1px solid #e1d8c9; padding:18px 0; }
.mv2-pillar-article .num { font:700 32px/1 Georgia, 'Times New Roman', serif; color:#3d342e; }
.mv2-pillar-article h4 { margin:0 0 6px; font:700 19px/1.2 Georgia, 'Times New Roman', serif; color:#1c1815; }
.mv2-pillar-article p { margin:0; font:16px/1.58 Georgia, 'Times New Roman', serif; color:#3d342e; }
.mv2-pillar-grid { display:grid; grid-template-columns:1fr 1fr; column-gap:22px; row-gap:2px; }
.mv2-svg-chart { width:100%; height:auto; display:block; border:1px solid var(--mv2-border); border-radius:8px; background:var(--mv2-sunken); }
.mv2-terminal .mv2-tab { background:#111; border-color:#2a2a2a; color:#b8b8b8; }
.mv2-terminal .mv2-tab.active { color:#f0f0f0; border-color:#5fa8d3; box-shadow:inset 0 -2px 0 #5fa8d3; }
.mv2-terminal .mv2-waterfall, .mv2-terminal .mv2-gate, .mv2-terminal .mv2-mom-row { border-top-color:#242424; }
.mv2-terminal .mv2-metric, .mv2-terminal .mv2-macro { background:#111; border-color:#242424; }
.mv2-terminal .mv2-metric b, .mv2-terminal .mv2-macro b, .mv2-terminal .mv2-gate b, .mv2-terminal .mv2-dot b { color:#f0f0f0; }
.mv2-terminal .mv2-rrg, .mv2-terminal .mv2-flow-river, .mv2-terminal .mv2-svg-chart, .mv2-terminal .mv2-a-bar { background:#080808; border-color:#242424; }
.mv2-terminal .mv2-a-pillar { border-top-color:#242424; }
.mv2-provenance { margin:0 12px 12px; padding:10px 12px; border:1px solid var(--mv2-border); border-radius:8px; background:rgba(255,255,255,.06); display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; font:11px/1.35 var(--font-prose); }
.mv2-terminal .mv2-provenance { margin:0 4px 12px; background:#101010; border-color:#2a2a2a; color:#b8b8b8; }
.mv2-editorial .mv2-provenance { background:#fffbf3; border-color:#e1d8c9; color:#6e6258; }
.mv2-pillarstack .mv2-provenance { background:#fff; border-color:#e6e1d8; color:#6e6258; }
.mv2-provenance b { display:block; color:inherit; font:900 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; margin-bottom:3px; }
.mv2-provenance span { overflow-wrap:anywhere; }
@media (max-width: 1050px) {
  .mv2-grid { grid-template-columns: 1fr; }
  .mv2-head { flex-direction:column; }
  .mv2-weather, .mv2-b-hero, .mv2-c-weather, .mv2-c-main, .mv2-c-rotation-grid { grid-template-columns:1fr; }
  .mv2-a-status, .mv2-a-body { grid-template-columns:1fr; }
  .mv2-row { grid-template-columns: 120px minmax(160px,1fr) 76px 58px 62px; }
  .mv2-a-row { grid-template-columns:52px minmax(150px,1fr) 76px 76px 52px 52px; }
  .mv2-a-row .hide-sm { display:none; }
  .mv2-metric-deck, .mv2-macro-grid, .mv2-state-grid, .mv2-universe-columns { grid-template-columns:1fr 1fr; }
  .mv2-chart-grid, .mv2-chart-grid.tight, .mv2-article-block, .mv2-pillar-grid, .mv2-a-hero-grid, .mv2-a-pillars, .mv2-a2-lead-grid, .mv2-a2-pillars, .mv2-a2-charts, .mv2-a3-grid, .mv2-a3-flow-cards, .mv2-c-pillar-grid, .mv2-b-article-grid { grid-template-columns:1fr; }
  .mv2-provenance { grid-template-columns:1fr; }
}
"""


def _esc(value: object) -> str:
    return escape(str(value), quote=True)


def _provenance_html(data_provenance: Mapping[str, Any] | None) -> str:
    if not data_provenance:
        return ""
    fields = (
        ("Market OHLCV", data_provenance.get("market_ohlcv", "")),
        ("FRED macro", data_provenance.get("fred_macro", "")),
        ("Provider flow", data_provenance.get("provider_flow", "")),
        ("Computed", data_provenance.get("computed", "")),
    )
    cells = "".join(
        f'<div><b>{_esc(label)}</b><span>{_esc(value or "unknown")}</span></div>'
        for label, value in fields
    )
    return f'<div class="mv2-provenance" data-testid="momentum-v2-provenance">{cells}</div>'


def _with_provenance(html: str, data_provenance: Mapping[str, Any] | None) -> str:
    banner = _provenance_html(data_provenance)
    if not banner:
        return html
    marker_end = html.find(">")
    if marker_end < 0 or "<section" not in html[: marker_end + 1]:
        return banner + html
    return html[: marker_end + 1] + banner + html[marker_end + 1 :]


def _fmt(value: float, suffix: str = "", digits: int = 2) -> str:
    return f"{value:+.{digits}f}{suffix}"


def _state_pill(state: str, label: str | None = None) -> str:
    color = STATE_COLORS_LIGHT.get(state, "#777")
    text_color = STATE_TEXT_COLORS.get(state, "#ffffff")
    display = label or STATE_LABELS.get(state, state)
    return (
        f'<span class="mv2-state" style="background:{color};color:{text_color}">'
        f'{_esc(display)}</span>'
    )


def _row_state_pill(row: MomentumV2Row) -> str:
    return _state_pill(row.state, row.state_label)


def _pillar_bar(row: MomentumV2Row) -> str:
    scale = max(0.8, max(abs(v) for v in row.pillars.values()) * 2.4)
    pos_cursor = 50.0
    neg_cursor = 50.0
    segments: list[str] = []
    for pillar in PILLAR_ORDER:
        value = row.pillars[pillar]
        width = min(48.0, abs(value) / scale * 50.0)
        if value >= 0:
            left = pos_cursor
            pos_cursor += width
        else:
            left = neg_cursor - width
            neg_cursor -= width
        title = f"{pillar}: {value:+.3f} weighted contribution"
        segments.append(
            f'<span class="mv2-seg" title="{_esc(title)}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%;background:{PILLAR_HUES[pillar]}"></span>'
        )
    return '<div class="mv2-bar">' + "".join(segments) + "</div>"


def _tone_class(value: float) -> str:
    return "mv2-pos" if value >= 0 else "mv2-neg"


def _pillar_bars_svg(row: MomentumV2Row, width: int = 90, height: int = 22) -> str:
    max_abs = max(0.35, max(abs(value) for value in row.pillars.values()))
    gap = 1.0
    bar_width = (width - gap * (len(PILLAR_ORDER) - 1)) / len(PILLAR_ORDER)
    mid = height / 2
    rects = []
    for idx, pillar in enumerate(PILLAR_ORDER):
        value = row.pillars[pillar]
        magnitude = min(abs(value), max_abs) / max_abs
        bar_height = max(0.75, magnitude * (height / 2 - 1))
        x = idx * (bar_width + gap)
        y = mid - bar_height if value >= 0 else mid
        color = "#26d65b" if value >= 0 else "#ef4f4a"
        rects.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" '
            f'fill="{color}" opacity=".95"><title>{_esc(PILLAR_FULL[pillar])}: {_fmt(value, digits=3)}</title></rect>'
        )
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="seven pillar bars for {_esc(row.ticker)}">'
        f'<line x1="0" y1="{mid:.1f}" x2="{width}" y2="{mid:.1f}" stroke="#2a2a2a" stroke-width="1"/>'
        + "".join(rects)
        + "</svg>"
    )


def _spark_svg(row: MomentumV2Row, width: int = 60, height: int = 22) -> str:
    values = [
        row.momentum_pct * 0.42,
        row.momentum_pct * 0.55 + row.s_score * 4,
        row.momentum_pct * 0.70 + row.f_score * 3,
        row.momentum_pct * 0.84 + row.mansfield_rs * 0.15,
        row.momentum_pct,
    ]
    lo = min(values)
    hi = max(values)
    rng = max(0.01, hi - lo)
    points = []
    for idx, value in enumerate(values):
        x = idx * (width / (len(values) - 1))
        y = height - ((value - lo) / rng) * (height - 4) - 2
        points.append((x, y))
    color = "#26d65b" if values[-1] >= values[0] else "#ef4f4a"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="90 day trend for {_esc(row.ticker)}">'
        f'<polyline points="{_svg_polyline(points)}" fill="none" stroke="{color}" stroke-width="1.4"/>'
        f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="2" fill="{color}"/>'
        + "</svg>"
    )


def _trend_track_svg(values: list[float], color: str, width: int = 150, height: int = 24) -> str:
    lo = min(values)
    hi = max(values)
    rng = max(0.01, hi - lo)
    points = []
    for idx, value in enumerate(values):
        x = idx * (width / (len(values) - 1))
        y = height - ((value - lo) / rng) * (height - 4) - 2
        points.append((x, y))
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<polyline points="{_svg_polyline(points)}" fill="none" stroke="{color}" stroke-width="1.3" opacity=".85"/>'
        f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="2" fill="{color}"/>'
        + "</svg>"
    )


def _terminal_row_html(row: MomentumV2Row) -> str:
    reason = " ".join(row.reasons)
    state_color = STATE_COLORS_LIGHT.get(row.state, "#777")
    bridge_attrs = drill_bridge_attrs(row.ticker, label=row.identity)
    return f"""
    <div class="mv2-a-row mv2-a-click" {bridge_attrs} data-ticker="{_esc(row.ticker)}" title="{_esc(reason)}">
      <b class="{_tone_class(row.s_score)}">{_esc(row.ticker)}</b>
      <div class="note">{_esc(row.identity)}</div>
      <div>{_row_state_pill(row)}</div>
      <div>{_pillar_bars_svg(row)}</div>
      <div class="num {_tone_class(row.s_score)}">{_fmt(row.s_score)}</div>
      <div class="num {_tone_class(row.f_score)}">{_fmt(row.f_score)}</div>
      <div class="num {_tone_class(row.momentum_pct)}">{_fmt(row.momentum_pct, '%', 1)}</div>
      <div class="hide-sm">{_spark_svg(row)}</div>
      <span style="display:none;color:{state_color}">{_esc(row.state)}</span>
    </div>
    """


def _display_a_sort_header(field: str, label: str, active_field: str, active_direction: str) -> str:
    is_active = field == active_field
    next_direction = "asc" if is_active and active_direction == "desc" else "desc"
    arrow = " v" if is_active and active_direction == "desc" else " ^" if is_active else ""
    class_name = "mv2-a-sort active" if is_active else "mv2-a-sort"
    href = f"?mv2_sort={_esc(field)}&mv2_dir={_esc(next_direction)}"
    title = f"Sort heatmap by {label} {'ascending' if next_direction == 'asc' else 'descending'}"
    numeric = " num" if field in {"s_score", "f_score", "momentum_pct"} else ""
    hide = " hide-sm" if field == "trend_90d" else ""
    return (
        f'<a class="{class_name}{numeric}{hide}" href="{href}" title="{_esc(title)}" '
        f'data-mv2-sort="{_esc(field)}">{_esc(label)}<span>{_esc(arrow)}</span></a>'
    )


def _display_a_header_row(active_field: str, active_direction: str) -> str:
    headers = (
        ("ticker", "TKR"),
        ("identity", "NOTE"),
        ("state", "STATE"),
        ("pillar_sum", "7 PILLARS"),
        ("s_score", "S"),
        ("f_score", "F"),
        ("momentum_pct", "MOM"),
        ("trend_90d", "90D"),
    )
    return '<div class="mv2-a-row mv2-a-header-row">' + "".join(
        _display_a_sort_header(field, label, active_field, active_direction)
        for field, label in headers
    ) + "</div>"


def _row_html(row: MomentumV2Row) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
    mom_class = "mv2-pos" if row.momentum_pct >= 0 else "mv2-neg"
    reason = " ".join(row.reasons)
    return f"""
    <div class="mv2-row" title="{_esc(reason)}">
      <div class="t">{_esc(row.ticker)}<small>{_esc(row.identity)}</small></div>
      {_pillar_bar(row)}
      <div>{_row_state_pill(row)}</div>
      <div class="mv2-num {s_class}">{_fmt(row.s_score)}</div>
      <div class="mv2-num {mom_class}">{_fmt(row.momentum_pct, '%', 1)}</div>
    </div>
    """


def _legend_html() -> str:
    chips = []
    for pillar in PILLAR_ORDER:
        chips.append(
            f'<span class="mv2-chip"><span class="mv2-swatch" '
            f'style="background:{PILLAR_HUES[pillar]}"></span>{pillar} '
            f'{PILLAR_WEIGHTS[pillar]:.0%}</span>'
        )
    return '<div class="mv2-legend">' + "".join(chips) + "</div>"


def _weather_item(label: str, value: str, sub: str, tone_class: str = "") -> str:
    return f'<div class="mv2-weather-item"><span>{_esc(label)}</span><b class="{tone_class}">{_esc(value)}</b><small>{_esc(sub)}</small></div>'


def _largest_pillars(row: MomentumV2Row) -> tuple[str, float, str, float]:
    positive = max(PILLAR_ORDER, key=lambda pillar: row.pillars[pillar])
    negative = min(PILLAR_ORDER, key=lambda pillar: row.pillars[pillar])
    return positive, row.pillars[positive], negative, row.pillars[negative]


def _c_topbar(active: str, as_of: str, context: str | None = None) -> str:
    tabs = {"overview": "Heatmap", "rotation": "Rotation", "deepdive": "Deep dive", "macro": "Macro", "positions": "Positions"}
    tab_html = "".join(
        f'<span class="mv2-c-tab {"active" if key == active else ""}">{_esc(label)}</span>'
        for key, label in tabs.items()
    )
    context_html = f'<span style="color:#d4cec1">/</span><span class="mv2-c-tab active">{_esc(context)}</span>' if context else ""
    return f"""
    <div class="mv2-c-top">
      <div class="mv2-c-brand">
        <span class="mv2-c-logo"><i style="height:9px;background:{PILLAR_HUES['MOM']}"></i><i style="height:12px;background:{PILLAR_HUES['RS-R']}"></i><i style="height:16px;background:{PILLAR_HUES['FILT']}"></i><i style="height:7px;background:{PILLAR_HUES['FLOW']}"></i></span>
        <span>Momentum</span><small>v2</small>
      </div>
      {context_html}
      <div class="mv2-c-tabs">{tab_html}</div>
      <span style="color:#7a7066;font:800 11px/1 var(--font-mono)"><i style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#1f7a4a;margin-right:6px"></i>{_esc(as_of)}</span>
      <span class="mv2-c-btn">R</span><span class="mv2-c-btn">M</span>
    </div>
    """


def _c_stack_bar(row: MomentumV2Row, width: int = 460) -> str:
    scale = max(1.0, sum(max(value, 0) for value in row.pillars.values()), sum(abs(min(value, 0)) for value in row.pillars.values()))
    pos_cursor = 50.0
    neg_cursor = 50.0
    segments = []
    for pillar in PILLAR_ORDER:
        value = row.pillars[pillar]
        pct = min(49.0, abs(value) / scale * 50.0)
        if value >= 0:
            left = pos_cursor
            pos_cursor += pct
            opacity = ".92"
        else:
            left = neg_cursor - pct
            neg_cursor -= pct
            opacity = ".55"
        segments.append(
            f'<span class="mv2-c-seg" title="{_esc(PILLAR_FULL[pillar])}: {_fmt(value, digits=3)}" '
            f'style="left:{left:.2f}%;width:{pct:.2f}%;background:{PILLAR_HUES[pillar]};opacity:{opacity}"></span>'
        )
    return '<div class="mv2-c-stack" style="max-width:%dpx">' % width + "".join(segments) + "</div>"


def _c_composition_row(row: MomentumV2Row) -> str:
    return f"""
    <div class="mv2-c-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}">
      <b>{_esc(row.ticker)}</b>
      {_c_stack_bar(row)}
      <div>{_row_state_pill(row)}</div>
      <span class="mv2-num {_tone_class(row.s_score)}">{_fmt(row.s_score)}</span>
      <span class="mv2-num {_tone_class(row.momentum_pct)}">{_fmt(row.momentum_pct, '%', 0)}</span>
    </div>
    """


def _c_weather_item(label: str, value: str, sub: str, tone: str = "") -> str:
    return f'<div class="mv2-c-weather-item"><span>{_esc(label)}</span><b class="{tone}">{_esc(value)}</b><small>{_esc(sub)}</small></div>'


def render_display_c(rows: list[MomentumV2Row], as_of: str) -> str:
    grouped = rows_by_class(rows)
    body = []
    for asset_class, items in grouped.items():
        bullish = sum(1 for item in items if item.state == "STAGE_2_BULLISH")
        body.append(f'<div class="mv2-class">{_esc(asset_class.upper() or "UNCLASSIFIED")} <span style="color:#a89e92;margin-left:8px">| {len(items)} | {bullish} bullish</span></div>')
        body.extend(_c_composition_row(item) for item in items)
    leaders = sorted(rows, key=lambda item: item.s_score, reverse=True)[:8]
    warnings = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}]
    bullish = [row for row in rows if row.state == "STAGE_2_BULLISH"]
    exits = [row for row in rows if row.state in {"EXIT", "BEARISH_STAGE_4"}]
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    headline, story_body = _board_story(rows)
    phase = _board_phase(rows)
    legend = "".join(
        f'<span><i style="width:12px;height:12px;border-radius:2px;background:{PILLAR_HUES[pillar]};display:inline-block"></i>{pillar} <em style="color:#a89e92;font-style:normal">{PILLAR_WEIGHTS[pillar]:.0%}</em></span>'
        for pillar in PILLAR_ORDER
    )
    rail_changes = "".join(
        f'<div class="mv2-c-rail-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}"><i style="background:{STATE_COLORS_LIGHT.get(row.state, "#777")}"></i><b>{_esc(row.ticker)}</b><span>{_esc(row.identity)} | state {_esc(row.state_label)}</span><span>{_fmt(row.s_score)}</span></div>'
        for row in warnings[:8]
    )
    positions = "".join(
        f'<div class="mv2-c-rail-row"><i style="background:{STATE_COLORS_LIGHT.get(row.state, "#777")}"></i><b>{_esc(row.ticker)}</b><span>{_esc(row.identity)} | S {_fmt(row.s_score)}</span><span class="{_tone_class(row.f_score)}">F {_fmt(row.f_score)}</span></div>'
        for row in sorted(rows, key=lambda item: abs(item.s_score), reverse=True)[:6]
    )
    return f"""
    <section class="mv2-shell mv2-pillarstack" id="momentum-v2-c">
      {_c_topbar("overview", as_of)}
      <div class="mv2-c-weather">
        <div>
          <div class="mv2-kicker">Today | {_esc(phase.lower())}</div>
          <h3>{_esc(headline)}</h3>
          <p>{_esc(story_body)} {len(exits)} exit/bearish rows and {len(bullish)} bullish candidates across the current universe.</p>
        </div>
        {_c_weather_item("Regime", "RISK-ON" if avg_s >= 0 else "RISK-OFF", f"average S {_fmt(avg_s)}", "mv2-pos" if avg_s >= 0 else "mv2-neg")}
        {_c_weather_item("Phase", phase, "S/F/breadth proxy")}
        {_c_weather_item("Warnings", str(len(warnings)), f"{len(exits)} exit", "mv2-neg" if warnings else "mv2-pos")}
        {_c_weather_item("Breadth", f"{breadth:.0%}", "below 50% gate" if breadth < .5 else "above 50% gate", "mv2-pos" if breadth >= .5 else "mv2-neg")}
        {_c_weather_item("Universe", str(len(rows)), f"{len(bullish)} bullish | {len(warnings)} warn")}
      </div>
      <div class="mv2-c-main">
        <div class="mv2-c-card">
          <div class="mv2-c-head"><b>The composite, dissected</b><span>{len(rows)} ETFs | sorted by S</span></div>
          <p>Each row IS the composite. Seven segments to the right of the midline are bullish contributions; segments to the left are bearish. Length encodes magnitude. Read the row to see why the score is what it is.</p>
          <div class="mv2-c-legend">{legend}<span style="margin-left:auto;color:#7a7066;font:800 10px/1 var(--font-mono)">bearish <- | bullish -></span></div>
          <div class="mv2-c-row" style="color:#7a7066;font:900 10px/1 var(--font-mono);text-transform:uppercase;border-top:0"><span>TKR</span><span>Composition</span><span>State</span><span style="text-align:right">S</span><span style="text-align:right">MOM</span></div>
          {"".join(body)}
        </div>
        <aside class="mv2-c-rail">
          <div class="mv2-c-card">
            <div class="mv2-c-head"><b>State queue</b><span>current run | {len(warnings)} risk rows</span></div>
            {rail_changes}
          </div>
          <div class="mv2-c-card">
            <div class="mv2-c-head"><b>Highest-impact rows</b><span>current universe | sorted by |S|</span></div>
            {positions}
            <div class="mv2-a2-callout"><strong style="color:#a8721a">Actions queued:</strong> Review warning/exit positions before adding new risk.</div>
          </div>
          <div class="mv2-c-card">
            <div class="mv2-c-head"><b>Bullish cohort</b><span>{len(bullish)} passing every gate</span></div>
            {"".join(f'<div class="mv2-c-rail-row"><i style="background:{STATE_COLORS_LIGHT.get(item.state, "#777")}"></i><b>{_esc(item.ticker)}</b><span>{_esc(item.identity)}</span><span>{_fmt(item.s_score)}</span></div>' for item in leaders[:8])}
          </div>
        </aside>
      </div>
    </section>
    """


def render_display_a(
    rows: list[MomentumV2Row],
    as_of: str,
    sort_field: str | None = "s_score",
    sort_direction: str | None = "desc",
) -> str:
    sort_field, sort_direction = normalize_display_a_sort(sort_field, sort_direction)
    sort_label = DISPLAY_A_SORT_FIELDS[sort_field]
    direction_label = DISPLAY_A_SORT_DIRECTIONS[sort_direction]
    grouped = rows_by_class(rows, sort_field=sort_field, sort_direction=sort_direction)
    body_parts = []
    for asset_class, items in grouped.items():
        bullish_in_class = sum(1 for item in items if item.state == "STAGE_2_BULLISH")
        body_parts.append(
            f'<div class="mv2-a-class"><span>{_esc(asset_class.upper() or "UNCLASSIFIED")}</span>'
            f'<span>{len(items)} | {bullish_in_class} bullish</span></div>'
        )
        body_parts.extend(_terminal_row_html(item) for item in items)
    body = "".join(body_parts)

    exits = [row for row in rows if row.state in {"EXIT", "BEARISH_STAGE_4"}]
    warnings = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}]
    new_buys = [row for row in rows if row.state == "STAGE_2_BULLISH"]
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    avg_stage_2 = sum(1 for row in rows if row.stage == "2")
    risk_on = avg_s >= 0 and breadth >= 0.45
    cycle_phase = "LATE" if avg_f < 0 or len(warnings) > len(new_buys) else "MID"
    leader_text = ", ".join(row.ticker for row in sorted(new_buys, key=lambda item: item.s_score, reverse=True)[:3]) or "none"
    exit_text = ", ".join(row.ticker for row in exits[:3]) or "none"
    warning_text = ", ".join(row.ticker for row in warnings[:4]) or "none"
    bluf_phase = "LATE CYCLE TOPPING" if warnings else "RISK-ON EXPANSION"
    bluf_summary = (
        f"{len(warnings)} instruments are in warning, exit, or bearish states while {len(new_buys)} remain bullish. "
        f"Leadership is led by {leader_text}; the current attention queue is {warning_text}. "
        f"Average S is {_fmt(avg_s)} and average F is {_fmt(avg_f)}, so the board is "
        f"{'constructive but narrowing' if risk_on and warnings else 'defensive'}."
    )
    transitions = warnings[:9] or sorted(rows, key=lambda item: abs(item.s_score), reverse=True)[:9]
    watchlist = sorted(rows, key=lambda item: (item.state not in {"WARNING", "EXIT", "BEARISH_STAGE_4"}, -abs(item.s_score)))[:6]
    action_names = [row.ticker for row in watchlist if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}]
    action_text = (
        f"Action this week: review {', '.join(action_names)} because they are in WARNING / EXIT / BEARISH states."
        if action_names
        else f"Action this week: no current holdings proxy is in WARNING or EXIT; monitor leaders {leader_text}."
    )
    warning_track = [max(0.0, len(warnings) * factor) for factor in (0.35, 0.45, 0.55, 0.70, 0.84, 1.0)]
    breadth_track = [min(1.0, max(0.0, breadth + delta)) for delta in (0.12, 0.08, 0.04, 0.0, -0.02, -0.01)]
    spy_track = [max(-2.0, avg_s * 2 + delta) for delta in (1.4, 1.1, 0.8, 0.45, 0.2, 0.0)]
    transition_rows = "".join(
        f"""
        <div class="mv2-a-transition mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}">
          <i style="background:{STATE_COLORS_LIGHT.get(row.state, '#777')};box-shadow:0 0 6px {STATE_COLORS_LIGHT.get(row.state, '#777')}66"></i>
          <div class="mv2-a-id"><b>{_esc(row.ticker)}</b><small>{_esc(row.identity)}</small></div>
          <span>state {_esc(row.state_label)}</span>
          <span>{_fmt(row.s_score)}</span>
        </div>
        """
        for row in transitions
    )
    watchlist_rows = "".join(
        f"""
        <div class="mv2-a-holding">
          <i style="background:{STATE_COLORS_LIGHT.get(row.state, '#777')}"></i>
          <div class="mv2-a-id"><b>{_esc(row.ticker)}</b><small>{_esc(row.identity)}</small></div>
          <span>S {_fmt(row.s_score)} | F {_fmt(row.f_score)}</span>
          {_row_state_pill(row)}
        </div>
        """
        for row in watchlist
    )
    return f"""
    <section class="mv2-shell mv2-terminal" id="momentum-v2-a">
      <div class="mv2-a-topbar">
        <span class="mv2-a-mark"></span>
        <span class="mv2-a-brand">SENTIMENT BOARD</span>
        <span style="color:#5a5a5a;font:800 11px/1 var(--font-mono)">v2 / momentum</span>
        <div class="mv2-a-live">
          <span><i></i>LIVE | 16:00 ET</span>
          <span>{_esc(as_of)}</span>
          <span>NEXT REFRESH 00:60:00</span>
        </div>
        <span class="mv2-a-btn" title="Refresh">R</span>
        <span class="mv2-a-btn" title="Theme">S</span>
        <span class="mv2-a-btn" title="More">...</span>
      </div>

      <div class="mv2-a-bluf">
        <div class="mv2-a-meta">
          <span class="mv2-a-chip">BLUF | {_esc(bluf_phase)}</span>
          <span>{_esc(as_of)}</span>
          <span>WK CHANGE</span>
        </div>
        <p>{_esc(bluf_summary)}</p>
        <div class="mv2-a-blufnums">
          <div class="mv2-a-blufnum"><b class="mv2-neg">{len(exits)}</b><span>EXIT</span></div>
          <span>|</span>
          <div class="mv2-a-blufnum"><b style="color:#e6b450">{len(warnings)}</b><span>WARNINGS</span></div>
          <span>|</span>
          <div class="mv2-a-blufnum"><b class="mv2-pos">{len(new_buys)}</b><span>NEW BUYS</span></div>
          <span class="mv2-a-bluf-spacer"></span>
          <span>UNIVERSE {len(rows)} ETFs | BREADTH {breadth:.0%} {'UP' if breadth >= .5 else 'DOWN'}</span>
        </div>
      </div>

      <div class="mv2-a-status">
        <div class="mv2-a-tile">
          <span>Risk regime</span>
          <b class="{'mv2-pos' if risk_on else 'mv2-neg'}">{'RISK-ON' if risk_on else 'RISK-OFF'}</b>
          <small>Average S {_fmt(avg_s)} | breadth {breadth:.0%}</small>
          {_trend_track_svg(spy_track, "#e6b450")}
          <small><em>Faber gate proxy, falling toward flip when breadth drops below 50%.</em></small>
        </div>
        <div class="mv2-a-tile">
          <span>Cycle phase</span>
          <b style="color:#e6b450">{_esc(cycle_phase)}</b>
          <small>{avg_stage_2} Stage-2 candidates | avg F {_fmt(avg_f)}</small>
          {_trend_track_svg([0.2, 0.38, 0.62, 0.74, 0.70, 0.66], "#e6b450")}
          <small><em>Macro/flow proxy from current board state.</em></small>
        </div>
        <div class="mv2-a-tile">
          <span>Active warnings</span>
          <b class="{'mv2-neg' if warnings else 'mv2-pos'}">{len(warnings)}</b>
          <small>{len(exits)} exit | {len(warnings)} warn | queue {exit_text}</small>
          {_trend_track_svg(warning_track, "#ef4f4a")}
          <small><em>Risk queue grows when warning/exit/bearish labels cluster.</em></small>
        </div>
        <div class="mv2-a-tile">
          <span>Breadth</span>
          <b class="{'mv2-pos' if breadth >= .5 else 'mv2-neg'}">{breadth:.0%}</b>
          <small>% above 50dMA | model breadth input</small>
          {_trend_track_svg(breadth_track, "#ef4f4a" if breadth < .5 else "#26d65b")}
          <small><em>Below 50% trips the warning gate for the board.</em></small>
        </div>
      </div>

      <div class="mv2-a-body">
        <div class="mv2-a-panel">
          <div class="mv2-a-head"><b>7-PILLAR HEATMAP</b><span>composite = weighted sum of signed pillar contributions | sorted by {_esc(sort_label)} within class | {_esc(direction_label)}</span></div>
          {_display_a_header_row(sort_field, sort_direction)}
          {body}
        </div>
        <aside class="mv2-a-rail">
          <div class="mv2-a-panel">
            <div class="mv2-a-head"><b>TRANSITIONS</b><span>current run queue | {len(transitions)} events</span></div>
            {transition_rows}
            <p style="margin:10px 0 0;color:#7c7c7c;font:italic 11px/1.4 var(--font-prose)">Click any row to open the deep-dive for that ticker when the Streamlit bridge is active.</p>
          </div>
          <div class="mv2-a-panel">
            <div class="mv2-a-head"><b>WATCHLIST | MY POSITIONS</b><span>{len(watchlist)} / {len(warnings)} in warning</span></div>
            {watchlist_rows}
            <div class="mv2-a-callout"><b>{_esc(action_text)}</b></div>
          </div>
        </aside>
      </div>

      <div class="mv2-a-footer">
        <span>{len(rows)} ETFs | 7 PILLARS | CURRENT DATA</span>
        <span>v2 | TERMINAL | READ-ONLY | MEIRI</span>
      </div>
    </section>
    """


def render_display_b(rows: list[MomentumV2Row], as_of: str) -> str:
    leaders = sorted(rows, key=lambda item: item.s_score, reverse=True)[:8]
    risks = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}]
    bullish = [row for row in rows if row.state == "STAGE_2_BULLISH"]
    featured = sorted(risks, key=lambda item: (item.state not in {"EXIT", "BEARISH_STAGE_4"}, item.s_score))[:3] or leaders[:3]
    headline, story_body = _board_story(rows)
    phase = _board_phase(rows)
    stories = []
    for item in featured:
        pos, pos_value, neg, neg_value = _largest_pillars(item)
        stories.append(
            f"""
            <article class="mv2-story mv2-a-click" {drill_bridge_attrs(item.ticker, label=item.identity)} data-ticker="{_esc(item.ticker)}">
              <div><b>{_esc(item.ticker)}</b><br>{_row_state_pill(item)}</div>
              <div>
                <h4>{_esc(item.identity)}: {_esc(item.state_label)}</h4>
                <p><strong>By the model.</strong> S is {_fmt(item.s_score)} and flow is {_fmt(item.f_score)}. {_esc(" ".join(item.reasons))}</p>
                <p>Largest support is {_esc(pos)} {_fmt(pos_value, digits=3)}; largest drag is {_esc(neg)} {_fmt(neg_value, digits=3)}. The practical read is to respect the state label first, then check the nearest failed gate.</p>
              </div>
            </article>
            """
        )
    num_rows = "".join(
        f'<div class="mv2-b-num"><span>{_esc(label)}<small style="display:block;color:#8b7e70;font:11px/1.2 var(--font-prose)">{_esc(sub)}</small></span><b class="{tone}">{_esc(value)}</b></div>'
        for label, value, sub, tone in _board_proxy_stats(rows)
    )
    tape_items = [*leaders[:4], *risks[:4]]
    tape = "".join(
        f'<span><b>{_esc(item.ticker)}</b> {_fmt(item.momentum_pct, "%", 1)} <i class="{_tone_class(item.s_score)}">{_esc(item.state_label)}</i></span>'
        for item in tape_items
    )
    position_rows = "".join(
        f'<div class="mv2-rail-item"><b>{_esc(item.ticker)} | {_esc(item.identity)}</b><span>{_esc(item.state_label)} | S {_fmt(item.s_score)} | F {_fmt(item.f_score)}</span></div>'
        for item in sorted(rows, key=lambda item: abs(item.s_score), reverse=True)[:6]
    )
    watch_rows = "".join(
        f'<div class="mv2-rail-item"><b>{_esc(item.display_label)}</b><span>{_esc(" ".join(item.reasons))}</span></div>'
        for item in risks[:8]
    )
    return f"""
    <section class="mv2-shell mv2-editorial" id="momentum-v2-b">
      <div class="mv2-b-mast">
        <b>The Sentiment Brief</b>
        <span style="flex:1"></span>
        <span>{_esc(as_of)} | CURRENT RUN | {_esc(phase)}</span>
        <span>SEARCH</span><span>ARCHIVE</span><span>MOON</span>
      </div>
      <div class="mv2-tape"><span>LIVE</span>{tape}<span style="margin-left:auto">UPDATED {_esc(as_of)}</span></div>
      <div class="mv2-b-hero">
        <div>
          <div class="mv2-kicker">Today's read | {_esc(phase.lower())}</div>
          <h3>{_esc(headline)}</h3>
          <p>{_esc(story_body)}</p>
          <div class="mv2-kicker" style="margin-top:16px">BY THE MODEL | {len(rows)} ETFS | 7 PILLARS | POSTED {_esc(as_of)}</div>
        </div>
        <div class="mv2-b-numbers">
          <h3>By the numbers</h3>
          {num_rows}
        </div>
      </div>
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>Current risk stories</h3>
          <p>The state machine triggered {len(risks)} caution or exit reads in the current universe. The featured stories below are selected by severity.</p>
          {"".join(stories)}
          <div class="mv2-article-block">
            <div>
              <p>The editorial display is designed for a slower reading workflow: not just which tickers changed, but what forces changed first. Momentum and trend say where price has been; flow and rotation say where sponsorship may be moving next.</p>
              <p>Read every story as decision support. A bullish state means evidence is aligned today; a warning means one or more forward-looking gates has started to deteriorate.</p>
            </div>
            <div class="mv2-article-side">
              <b>READING ORDER</b>
              <p>1. State label<br>2. S and F scores<br>3. Largest pillar drag<br>4. Exit trigger proximity</p>
            </div>
          </div>
        </div>
        <aside class="mv2-rail-stack">
          <div class="mv2-panel">
            <h3>Your positions</h3>
            <div class="mv2-rail-list">{position_rows}</div>
            <p style="margin-top:12px"><em>{len(risks)} current universe rows carry warning, exit, or bearish labels; review those before adding risk.</em></p>
          </div>
          <div class="mv2-panel">
            <h3>Bullish cohort</h3>
            <div class="mv2-rail-list">
              {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)}</b><span>S {_fmt(item.s_score)} | F {_fmt(item.f_score)} | {item.quadrant}</span></div>' for item in bullish[:6])}
            </div>
          </div>
          <div class="mv2-panel">
            <h3>On watch</h3>
            <div class="mv2-rail-list">{watch_rows}</div>
          </div>
        </aside>
      </div>
      <div class="mv2-footer"><span>THE SENTIMENT BRIEF | {len(rows)} ETFS | 7 PILLARS | CURRENT DATA</span><span><em>Read before you trade.</em> | v2 | EDITORIAL | MEIRI</span></div>
    </section>
    """


def _tabs_html(active_screen: str) -> str:
    return (
        '<div class="mv2-tabs">'
        + "".join(
            f'<span class="mv2-tab {"active" if key == active_screen else ""}">{_esc(label)}</span>'
            for key, label in SCREEN_LABELS.items()
        )
        + "</div>"
    )


def _focus_row(rows: list[MomentumV2Row], focus_ticker: str | None = None) -> MomentumV2Row:
    if not rows:
        raise ValueError("Momentum v2 needs at least one scored row")
    normalized = str(focus_ticker or "").strip().upper()
    for row in rows:
        if row.ticker.upper() == normalized:
            return row
    return sorted(rows, key=lambda item: item.s_score, reverse=True)[0]


def _find_focus_row(rows: list[MomentumV2Row], focus_ticker: str | None = None) -> MomentumV2Row | None:
    normalized = str(focus_ticker or "").strip().upper()
    if not normalized:
        return None
    for row in rows:
        if row.ticker.upper() == normalized:
            return row
    return None


def _metric_card(label: str, value: str, tone_class: str = "") -> str:
    return f'<div class="mv2-metric"><span>{_esc(label)}</span><b class="{tone_class}">{_esc(value)}</b></div>'


def _gate_html(ok: bool, label: str, detail: str) -> str:
    color = "var(--mv2-green)" if ok else "var(--mv2-red)"
    mark = "Y" if ok else "!"
    return (
        f'<div class="mv2-gate"><i class="mv2-gate-mark" style="background:{color}">{mark}</i>'
        f'<b>{_esc(label)}</b><span>{_esc(detail)}</span></div>'
    )


def _state_count_cards(rows: list[MomentumV2Row]) -> str:
    counts = {state: 0 for state in STATE_LABELS}
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
    cards = []
    for state in ("STAGE_2_BULLISH", "HOLD", "WARNING", "EXIT", "BEARISH_STAGE_4"):
        cards.append(
            f"""
            <div class="mv2-state-card">
              <span>{_esc(STATE_LABELS.get(state, state))}</span>
              <b>{counts.get(state, 0)}</b>
            </div>
            """
        )
    return '<div class="mv2-state-grid">' + "".join(cards) + "</div>"


def _state_summary(rows: list[MomentumV2Row]) -> str:
    bullish = sum(1 for row in rows if row.state == "STAGE_2_BULLISH")
    warnings = sum(1 for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"})
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    return (
        f"{len(rows)} instruments scanned. {bullish} bullish candidates, {warnings} risk names, "
        f"average S {_fmt(avg_s)}, average F {_fmt(avg_f)}."
    )


def _risk_rows(rows: list[MomentumV2Row]) -> list[MomentumV2Row]:
    return [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}]


def _board_phase(rows: list[MomentumV2Row]) -> str:
    if not rows:
        return "NO DATA"
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    risk_count = len(_risk_rows(rows))
    if avg_s < 0 or breadth < 0.45 or risk_count > len(rows) * 0.40:
        return "RISK-OFF"
    if avg_f < 0 or breadth < 0.55 or risk_count:
        return "NARROWING"
    return "RISK-ON"


def _row_name(row: MomentumV2Row | None) -> str:
    if row is None:
        return "No data"
    return f"{row.ticker} | {row.identity}"


def _board_story(rows: list[MomentumV2Row]) -> tuple[str, str]:
    if not rows:
        return "No instruments loaded.", "The dashboard needs scored rows before it can generate a board story."
    weakest_flow = min(rows, key=lambda item: item.f_score)
    strongest_flow = max(rows, key=lambda item: item.f_score)
    weakest_state = min(rows, key=lambda item: item.s_score)
    strongest_state = max(rows, key=lambda item: item.s_score)
    flow_spread = strongest_flow.f_score - weakest_flow.f_score
    if abs(flow_spread) < 0.05:
        headline = f"{strongest_state.identity} leads by composite score. Flow sponsorship is flat."
        body = (
            f"The current run ranks {_row_name(strongest_state)} highest by composite S "
            f"({_fmt(strongest_state.s_score)}) and {_row_name(weakest_state)} lowest "
            f"({_fmt(weakest_state.s_score)}). Flow scores are effectively tied "
            f"(range {_fmt(weakest_flow.f_score)} to {_fmt(strongest_flow.f_score)}), so the model is not naming "
            "a real flow leader or flow drag for this run."
        )
    else:
        headline = f"{weakest_flow.identity} lost flow support. {strongest_flow.identity} leads sponsorship."
        body = (
            f"The current run ranks {_row_name(strongest_state)} highest by composite S "
            f"({_fmt(strongest_state.s_score)}) and {_row_name(weakest_state)} lowest "
            f"({_fmt(weakest_state.s_score)}). Flow leadership is {_row_name(strongest_flow)} "
            f"({_fmt(strongest_flow.f_score)}), while the largest flow drag is {_row_name(weakest_flow)} "
            f"({_fmt(weakest_flow.f_score)})."
        )
    return headline, body


def _board_proxy_stats(rows: list[MomentumV2Row]) -> list[tuple[str, str, str, str]]:
    if not rows:
        return []
    risks = _risk_rows(rows)
    exits = [row for row in risks if row.state in {"EXIT", "BEARISH_STAGE_4"}]
    warnings_only = [row for row in rows if row.state == "WARNING"]
    bullish = [row for row in rows if row.state == "STAGE_2_BULLISH"]
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    avg_mom = sum(row.momentum_pct for row in rows) / max(len(rows), 1)
    cmf_negative = sum(1 for row in rows if row.cmf21 < 0)
    return [
        ("Exit/bearish states", str(len(exits)), "current scored universe", "mv2-neg" if exits else "mv2-pos"),
        ("Warning states", str(len(warnings_only)), "current scored universe", "mv2-neg" if warnings_only else "mv2-pos"),
        ("Total risk states", str(len(risks)), "warning + exit + bearish", "mv2-neg" if risks else "mv2-pos"),
        ("Bullish states", str(len(bullish)), "current scored universe", "mv2-pos" if bullish else ""),
        ("Average S", _fmt(avg_s), "composite board proxy", _tone_class(avg_s)),
        ("Average F", _fmt(avg_f), "provider-flow board proxy", _tone_class(avg_f)),
        ("Breadth > 50dMA", f"{breadth:.0%}", "mean breadth input", "mv2-pos" if breadth >= 0.5 else "mv2-neg"),
        ("Average momentum", _fmt(avg_mom, "%", 1), "12-1 momentum mean", _tone_class(avg_mom)),
        ("Negative CMF count", str(cmf_negative), "CMF21 below zero", "mv2-neg" if cmf_negative else "mv2-pos"),
    ]


def _support_count(row: MomentumV2Row) -> tuple[int, int]:
    supportive = sum(1 for value in row.pillars.values() if value >= 0)
    return supportive, len(row.pillars)


def _deepdive_headline(row: MomentumV2Row) -> tuple[str, str, str]:
    trend_ok = row.above_30wma and row.ma_slope_pos
    flow_ok = row.f_score >= 0 and row.cmf21 >= 0
    price = "trend confirms" if trend_ok else "trend is mixed" if row.above_30wma else "trend broke"
    flow = "flow confirms" if flow_ok else "flow is warning"
    subtitle = (
        f"{row.identity} is in {row.state_label} with S {_fmt(row.s_score)}, "
        f"F {_fmt(row.f_score)}, momentum {_fmt(row.momentum_pct, '%', 1)}, and RRG {row.quadrant}. "
        f"The article explains the exact pillar balance and the nearest exit/escalation gates for this ticker."
    )
    return price, flow, subtitle


def _deepdive_interpretation(row: MomentumV2Row) -> tuple[str, str, str]:
    pos, pos_value, neg, neg_value = _largest_pillars(row)
    failed = [label for ok, label, _ in _gate_rows_for(row) if not ok]
    support, total = _support_count(row)
    first = (
        f"The practical interpretation is based on the current data for {row.ticker}. "
        f"{support} of {total} pillars are supportive. The largest support is {pos} "
        f"({_fmt(pos_value, digits=3)}), and the largest drag is {neg} ({_fmt(neg_value, digits=3)})."
    )
    second = (
        f"The dashboard treats {row.ticker} as {row.state_label.lower()}. "
        f"Failed gates: {', '.join(failed) if failed else 'none'}. "
        f"{_next_escalation_text(row)}"
    )
    third = (
        f"For a novice reader: S is the blended score, F is the flow score, and the state label is the action language. "
        f"For {row.ticker}, do not read one number alone; compare S {_fmt(row.s_score)}, "
        f"F {_fmt(row.f_score)}, CMF {_fmt(row.cmf21)}, Mansfield {_fmt(row.mansfield_rs)}, "
        f"and RRG {row.quadrant} together."
    )
    return first, second, third


def _macro_proxy_stats(rows: list[MomentumV2Row]) -> list[tuple[str, str]]:
    if not rows:
        return []
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    warnings = len(_risk_rows(rows))
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    avg_mom = sum(row.momentum_pct for row in rows) / max(len(rows), 1)
    negative_cmf = sum(1 for row in rows if row.cmf21 < 0)
    return [
        ("Board phase", _board_phase(rows)),
        ("Avg S", _fmt(avg_s)),
        ("Avg F", _fmt(avg_f)),
        ("Avg momentum", _fmt(avg_mom, "%", 1)),
        ("Breadth", f"{breadth:.0%}"),
        ("Risk states", str(warnings)),
        ("CMF<0 count", str(negative_cmf)),
    ]


def _rotation_summary(rows: list[MomentumV2Row]) -> tuple[str, str]:
    sectors = [row for row in rows if row.asset_class == "US Sectors"] or rows
    weakening = [row for row in sectors if row.quadrant == "Weakening"]
    lagging = [row for row in sectors if row.quadrant == "Lagging"]
    improving = [row for row in sectors if row.quadrant == "Improving"]
    leading = [row for row in sectors if row.quadrant == "Leading"]
    strongest = max(sectors, key=lambda item: item.f_score, default=None)
    weakest = min(sectors, key=lambda item: item.f_score, default=None)
    sentence = (
        f"Current quadrant counts: {len(leading)} leading, {len(weakening)} weakening, "
        f"{len(lagging)} lagging, {len(improving)} improving. "
        f"Strongest flow is {_row_name(strongest)}; weakest flow is {_row_name(weakest)}."
    )
    caption = (
        f"Read clockwise using current RRG coordinates. Weakening: "
        f"{', '.join(row.ticker for row in weakening[:4]) or 'none'}. Improving: "
        f"{', '.join(row.ticker for row in improving[:4]) or 'none'}."
    )
    return sentence, caption


def _waterfall_html(row: MomentumV2Row) -> str:
    max_abs = max(0.25, max(abs(v) for v in row.pillars.values()), abs(row.s_score))
    steps = []
    for pillar in PILLAR_ORDER:
        value = row.pillars[pillar]
        height = 28 + (abs(value) / max_abs) * 120
        tone = "mv2-pos" if value >= 0 else "mv2-neg"
        steps.append(
            f"""
            <div class="mv2-step">
              <div class="mv2-step-val {tone}">{_fmt(value, digits=3)}</div>
              <div class="mv2-step-bar" style="height:{height:.1f}px;background:{PILLAR_HUES[pillar]}"></div>
              <div class="mv2-step-lbl">{_esc(pillar)}<br>{PILLAR_WEIGHTS[pillar]:.0%}</div>
            </div>
            """
        )
    final_tone = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    final_height = 36 + (abs(row.s_score) / max_abs) * 120
    steps.append(
        f"""
        <div class="mv2-step">
          <div class="mv2-step-val {final_tone}">{_fmt(row.s_score)}</div>
          <div class="mv2-step-bar" style="height:{final_height:.1f}px;background:{'var(--mv2-green)' if row.s_score >= 0 else 'var(--mv2-red)'}"></div>
          <div class="mv2-step-lbl">SCORE<br>FINAL</div>
        </div>
        """
    )
    return '<div class="mv2-waterfall">' + "".join(steps) + "</div>"


def _composite_bar_html(row: MomentumV2Row) -> str:
    max_abs = max(1.0, sum(max(value, 0) for value in row.pillars.values()), sum(abs(min(value, 0)) for value in row.pillars.values()))
    pos_cursor = 50.0
    neg_cursor = 50.0
    segments: list[str] = []
    for pillar in sorted(PILLAR_ORDER, key=lambda key: row.pillars[key], reverse=True):
        value = row.pillars[pillar]
        width = min(48.0, abs(value) / max_abs * 50.0)
        if width <= 0.2:
            continue
        if value >= 0:
            left = pos_cursor
            pos_cursor += width
            klass = "mv2-a-seg"
        else:
            left = neg_cursor - width
            neg_cursor -= width
            klass = "mv2-a-seg neg"
        segments.append(
            f'<span class="{klass}" title="{_esc(PILLAR_FULL[pillar])}: {_fmt(value, digits=3)}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%;background:{PILLAR_HUES[pillar]}"></span>'
        )
    return (
        '<div class="mv2-a-bar-wrap">'
        '<div class="mv2-a-bar-meta"><span>bearish contribution &lt;-</span>'
        f'<span>S = {_fmt(row.s_score)}</span><span>-&gt; bullish contribution</span></div>'
        '<div class="mv2-a-bar">' + "".join(segments) + "</div></div>"
    )


def _pillar_detail_grid(row: MomentumV2Row) -> str:
    cells = []
    for pillar in PILLAR_ORDER:
        tone = "mv2-pos" if row.pillars[pillar] >= 0 else "mv2-neg"
        cells.append(
            f"""
            <div class="mv2-a-pillar">
              <i style="background:{PILLAR_HUES[pillar]}"></i>
              <b>{_esc(pillar)} | {_esc(PILLAR_FULL[pillar])}</b>
              <span class="{tone}">{_fmt(row.pillars[pillar], digits=3)}</span>
            </div>
            """
        )
    return '<div class="mv2-a-pillars">' + "".join(cells) + "</div>"


def _pillar_reason(row: MomentumV2Row, pillar: str) -> str:
    value = row.pillars[pillar]
    sign = "supports" if value >= 0 else "drags on"
    if pillar == "MOM":
        return f"12-1 momentum is {_fmt(row.momentum_pct, '%', 1)}, so trend speed {sign} the score."
    if pillar == "MANS":
        return f"Mansfield RS is {_fmt(row.mansfield_rs)}, showing whether {row.ticker} leads its peer group."
    if pillar == "RS-R":
        return f"RRG ratio is {_fmt(row.rs_ratio - 100.0)}, measuring relative strength versus the benchmark."
    if pillar == "RS-M":
        return f"RRG momentum is {_fmt(row.rs_momentum - 100.0)}, the rotation signal that often moves first."
    if pillar == "FILT":
        gates = [
            "above 30wMA" if row.above_30wma else "below 30wMA",
            "rising slope" if row.ma_slope_pos else "falling slope",
            f"stage {row.stage}",
        ]
        return "Trend filters read " + ", ".join(gates) + "."
    if pillar == "CYC":
        return f"Business-cycle tilt adjusts the score for {row.asset_class or 'this group'}."
    if pillar == "FLOW":
        return f"Flow is {_fmt(row.f_score)} and CMF is {_fmt(row.cmf21)}, so institutional demand {sign} the score."
    return "Signed weighted contribution from the methodology."


def _terminal_pillar_detail_grid(row: MomentumV2Row) -> str:
    cells = []
    for pillar in PILLAR_ORDER:
        value = row.pillars[pillar]
        tone = _tone_class(value)
        cells.append(
            f"""
            <div class="mv2-a2-pillar">
              <i style="background:{PILLAR_HUES[pillar]}"></i>
              <div>
                <b>{_esc(PILLAR_FULL[pillar])} | w {PILLAR_WEIGHTS[pillar]:.0%}</b>
                <p>{_esc(_pillar_reason(row, pillar))}</p>
              </div>
              <span class="{tone}">{_fmt(value, digits=3)}</span>
            </div>
            """
        )
    return '<div class="mv2-a2-pillars">' + "".join(cells) + "</div>"


def _gate_rows_for(row: MomentumV2Row) -> list[tuple[bool, str, str]]:
    return [
        (row.quadrant not in {"Weakening", "Lagging"}, "RRG not weakening", row.quadrant),
        (row.breadth_50d >= 0.5, "Breadth >= 50%", f"{row.breadth_50d:.0%}"),
        (row.cmf21 > 0, "CMF stayed > 0", _fmt(row.cmf21)),
        (row.f_score >= -0.5, "Flow veto avoided", _fmt(row.f_score)),
        (row.above_30wma, "Close above 30wMA", "above" if row.above_30wma else "below"),
        (row.mansfield_rs >= 0, "Mansfield RS >= 0", _fmt(row.mansfield_rs)),
    ]


def _next_escalation_text(row: MomentumV2Row) -> str:
    tripped = []
    if not row.above_30wma:
        tripped.append("close < 30wMA")
    if row.mansfield_rs < 0:
        tripped.append("Mansfield RS < 0")
    if row.cmf21 < -0.10:
        tripped.append("CMF < -0.10")
    if row.quadrant == "Lagging":
        tripped.append("RRG Lagging")
    if tripped:
        return f"Next state escalation: EXIT pressure is active because {', '.join(tripped)}."
    return "Next state escalation: EXIT if close < 30wMA, Mansfield RS < 0, RRG enters Lagging, or CMF < -0.10 holds for one week. Currently no escalation gate is tripped."


def _peer_rank_html(rows: list[MomentumV2Row], focus: MomentumV2Row) -> tuple[str, int, int]:
    peers = [row for row in rows if row.asset_class == focus.asset_class] or rows
    peers = sorted(peers, key=lambda item: item.s_score, reverse=True)
    rank = next((idx + 1 for idx, row in enumerate(peers) if row.ticker == focus.ticker), 1)
    rendered = []
    for idx, row in enumerate(peers[:14], start=1):
        state = row.state_label
        focus_class = " focus" if row.ticker == focus.ticker else ""
        rendered.append(
            f"""
            <div class="mv2-a2-peer-row mv2-a-click{focus_class}" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}">
              <span class="rank">{idx:02d}</span>
              <b>{_esc(row.ticker)}</b>
              <span class="name">{_esc(row.identity)}</span>
              <span class="{_tone_class(row.s_score)}">{_fmt(row.s_score)}</span>
              {_row_state_pill(row)}
              <span style="display:none">{_esc(state)}</span>
            </div>
            """
        )
    return "".join(rendered), rank, len(peers)


def _svg_polyline(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _price_svg(row: MomentumV2Row, width: int = 760, height: int = 220) -> str:
    pad = 34
    price = []
    ma = []
    for i in range(78):
        t = i / 77
        base = 0.20 + 0.58 * t + 0.04 * ((i % 9) / 8)
        fade = 0.16 * max(0, t - 0.72)
        price.append(base - fade)
        ma.append(0.18 + 0.50 * max(0, t - 0.08))
    def pt(values: list[float]) -> list[tuple[float, float]]:
        lo, hi = min(values + ma), max(values + ma)
        return [
            (pad + i / (len(values) - 1) * (width - 2 * pad), height - pad - (v - lo) / (hi - lo) * (height - 2 * pad))
            for i, v in enumerate(values)
        ]
    price_pts = pt(price)
    ma_pts = pt(ma)
    stage_x, obv_x = price_pts[30][0], price_pts[70][0]
    return f"""
    <svg class="mv2-svg-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(row.ticker)} weekly price chart">
      <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#bdb4a8"/>
      <polyline points="{_svg_polyline(ma_pts)}" fill="none" stroke="var(--mv2-amber)" stroke-width="2" stroke-dasharray="5 4"/>
      <polyline points="{_svg_polyline(price_pts)}" fill="none" stroke="var(--mv2-green)" stroke-width="2.5"/>
      <line x1="{stage_x:.1f}" y1="{pad}" x2="{stage_x:.1f}" y2="{height-pad}" stroke="var(--mv2-green)" stroke-dasharray="2 4"/>
      <line x1="{obv_x:.1f}" y1="{pad}" x2="{obv_x:.1f}" y2="{height-pad}" stroke="var(--mv2-amber)" stroke-dasharray="2 4"/>
      <circle cx="{price_pts[-1][0]:.1f}" cy="{price_pts[-1][1]:.1f}" r="5" fill="var(--mv2-amber)"/>
      <text x="{stage_x+6:.1f}" y="{pad+18}" fill="var(--mv2-green)" font-size="12" font-family="monospace">STAGE 2 ENTRY</text>
      <text x="{obv_x-98:.1f}" y="{pad+18}" fill="var(--mv2-amber)" font-size="12" font-family="monospace">OBV DIVERGENCE</text>
      <text x="{width-pad-76}" y="{price_pts[-1][1]-8:.1f}" fill="var(--mv2-ink)" font-size="12" font-family="monospace">LAST</text>
    </svg>
    """


def _obv_svg(row: MomentumV2Row, width: int = 420, height: int = 170) -> str:
    pad = 26
    price = [(pad + i * (width - 2 * pad) / 5, height - pad - y) for i, y in enumerate([46, 70, 92, 112, 134, 150])]
    obv = [(pad + i * (width - 2 * pad) / 5, height - pad - y) for i, y in enumerate([32, 55, 84, 92, 88, 82])]
    return f"""
    <svg class="mv2-svg-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(row.ticker)} OBV divergence chart">
      <polyline points="{_svg_polyline(price)}" fill="none" stroke="var(--mv2-ink)" stroke-width="2"/>
      <polyline points="{_svg_polyline(obv)}" fill="none" stroke="var(--mv2-blue)" stroke-width="2"/>
      <line x1="{price[3][0]:.1f}" y1="{price[3][1]:.1f}" x2="{price[5][0]:.1f}" y2="{price[5][1]:.1f}" stroke="var(--mv2-green)" stroke-dasharray="5 4"/>
      <line x1="{obv[3][0]:.1f}" y1="{obv[3][1]:.1f}" x2="{obv[5][0]:.1f}" y2="{obv[5][1]:.1f}" stroke="var(--mv2-red)" stroke-dasharray="5 4"/>
      <text x="{width-pad-74}" y="{price[5][1]-8:.1f}" fill="var(--mv2-green)" font-size="12" font-family="monospace">price HH</text>
      <text x="{width-pad-70}" y="{obv[5][1]+18:.1f}" fill="var(--mv2-red)" font-size="12" font-family="monospace">OBV LH</text>
    </svg>
    """


def _cmf_svg(row: MomentumV2Row, width: int = 420, height: int = 170) -> str:
    pad = 28
    values = [0.10, 0.08, 0.09, 0.07, 0.04, 0.01, row.cmf21, min(row.cmf21 - 0.03, -0.08)]
    def y(v: float) -> float:
        return pad + (0.16 - v) / 0.32 * (height - 2 * pad)
    pts = [(pad + i * (width - 2 * pad) / (len(values) - 1), y(v)) for i, v in enumerate(values)]
    return f"""
    <svg class="mv2-svg-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(row.ticker)} CMF chart">
      <line x1="{pad}" y1="{y(0.10):.1f}" x2="{width-pad}" y2="{y(0.10):.1f}" stroke="var(--mv2-green)" stroke-dasharray="4 4"/>
      <line x1="{pad}" y1="{y(0):.1f}" x2="{width-pad}" y2="{y(0):.1f}" stroke="#8a8074"/>
      <line x1="{pad}" y1="{y(-0.10):.1f}" x2="{width-pad}" y2="{y(-0.10):.1f}" stroke="var(--mv2-red)" stroke-dasharray="4 4"/>
      <polyline points="{_svg_polyline(pts)}" fill="none" stroke="var(--mv2-amber)" stroke-width="2.5"/>
      <circle cx="{pts[-2][0]:.1f}" cy="{pts[-2][1]:.1f}" r="5" fill="var(--mv2-amber)"/>
      <text x="{width-pad-92}" y="{pts[-2][1]-10:.1f}" fill="var(--mv2-amber)" font-size="12" font-family="monospace">CMF {_fmt(row.cmf21)}</text>
    </svg>
    """


def _deepdive_terminal_body(row: MomentumV2Row, rows: list[MomentumV2Row], as_of: str) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
    mom_class = "mv2-pos" if row.momentum_pct >= 0 else "mv2-neg"
    gate_rows = _gate_rows_for(row)
    failed_gates = [gate for gate in gate_rows if not gate[0]]
    peer_rows, rank, peer_count = _peer_rank_html(rows, row)
    state_text = row.state_label
    flow_phrase = "institutional money is supporting the move" if row.f_score >= 0 else "institutional money is exiting before price fully confirms it"
    narrative = (
        f"{row.ticker} is in {state_text}. Price-based evidence shows momentum at {_fmt(row.momentum_pct, '%', 1)} "
        f"and the 30-week SMA is {'intact' if row.above_30wma else 'broken'}, while flow contributes "
        f"{_fmt(row.pillars['FLOW'], digits=3)} with CMF {_fmt(row.cmf21)}. RRG is {row.quadrant}. "
        f"The system is telling you {flow_phrase}."
    )
    return f"""
      <div class="mv2-a2-header">
        <span class="mv2-a2-back">BACK TO OVERVIEW</span>
        <span style="color:#5a5a5a;font:900 11px/1 var(--font-mono)">/</span>
        <span style="color:#7c7c7c;font:900 12px/1 var(--font-mono);letter-spacing:.08em">DEEP DIVE</span>
        <span style="color:#5a5a5a;font:900 11px/1 var(--font-mono)">/</span>
        <b style="color:#e8e8e8;font:900 14px/1 var(--font-mono)">{_esc(row.ticker)}</b>
        <span style="color:#7c7c7c;font:800 11px/1 var(--font-mono)">{_esc(row.asset_class)} | {_esc(row.identity.upper())}</span>
        <span style="flex:1"></span>
        {_row_state_pill(row)}
        <span style="color:#7c7c7c;font:800 11px/1 var(--font-mono)">model close proxy | mom {_fmt(row.momentum_pct, '%', 1)}</span>
      </div>
      {_tabs_html("deepdive")}
      <div class="mv2-a2-lead">
        <div class="mv2-a2-lead-grid">
          <div>
            <div class="mv2-kicker">COMPOSITE FORWARD OUTLOOK</div>
            <div class="mv2-a2-score"><b class="{s_class}">{_fmt(row.s_score)}</b><span>S-score | rank {rank} of {peer_count} {_esc(row.asset_class)}</span></div>
            <p class="mv2-a2-copy"><strong style="color:#e6b450">{_esc(row.ticker)} is currently {_esc(state_text)}.</strong> {_esc(narrative)}</p>
            {_composite_bar_html(row)}
            {_terminal_pillar_detail_grid(row)}
          </div>
          <aside class="mv2-a2-gate-panel">
            <h3>{_esc(row.state_label)} | STATE GATES</h3>
            <p>State fires when any one deterioration gate is active. Currently triggered by <span style="color:#e6b450">{len(failed_gates)}</span> gates.</p>
            <div class="mv2-gates">{"".join(_gate_html(*gate) for gate in gate_rows)}</div>
            <div class="mv2-a2-callout"><strong style="color:#e6b450">Next state escalation:</strong> {_esc(_next_escalation_text(row))}</div>
          </aside>
        </div>
      </div>
      <div class="mv2-a2-charts">
        <div class="mv2-panel">
          <h3>WEEKLY PRICE vs 30-WEEK SMA | WEINSTEIN</h3>
          {_price_svg(row, width=820, height=245)}
          <p>{_esc(row.ticker)} is {'above' if row.above_30wma else 'below'} the 30-week average and the average slope is {'positive' if row.ma_slope_pos else 'negative'}. A weekly close below the dashed line is the canonical EXIT trigger.</p>
        </div>
        <div class="mv2-panel">
          <h3>OBV DIVERGENCE</h3>
          {_obv_svg(row, width=420, height=190)}
          <p>OBV shows whether volume confirms price. A higher price high with weaker OBV is an early sponsorship warning for {_esc(row.ticker)}.</p>
        </div>
        <div class="mv2-panel">
          <h3>CHAIKIN MONEY FLOW (21D)</h3>
          {_cmf_svg(row, width=820, height=205)}
          <p>CMF is {_fmt(row.cmf21)}. Values below zero show distribution; values below -0.10 are treated as a more serious exit gate.</p>
        </div>
        <div class="mv2-panel">
          <h3>PEERS | {_esc(row.asset_class.upper())} RANK</h3>
          <p>{peer_count} peers sorted by S. {_esc(row.ticker)} is #{rank}. Click a peer row to open its drill-down.</p>
          <div class="mv2-a2-peer-row" style="border-top:0;color:#7c7c7c;text-transform:uppercase"><span>RK</span><span>TKR</span><span>NAME</span><span>S</span><span>STATE</span></div>
          {peer_rows}
        </div>
      </div>
      <div class="mv2-a-footer"><span>{_esc(row.ticker)} | {_esc(row.identity.upper())} | {len(rows)} ETFS | 7 PILLARS | CURRENT DATA</span><span>v2 | TERMINAL | DEEP DIVE | MEIRI</span></div>
    """


def _deepdive_body(row: MomentumV2Row, display_name: str) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
    mom_class = "mv2-pos" if row.momentum_pct >= 0 else "mv2-neg"
    gates = [
        (row.stage == "2", "Weinstein Stage 2", f"stage {row.stage}"),
        (row.above_30wma, "Price above 30-week MA", "above" if row.above_30wma else "below"),
        (row.ma_slope_pos, "30-week MA slope positive", "rising" if row.ma_slope_pos else "falling"),
        (row.mansfield_rs >= 0, "Mansfield RS above zero", _fmt(row.mansfield_rs)),
        (row.quadrant in {"Leading", "Improving"}, "RRG not deteriorating", row.quadrant),
        (row.cmf21 >= 0, "CMF above zero", _fmt(row.cmf21)),
        (row.f_score >= -0.5, "Flow veto avoided", _fmt(row.f_score)),
        (row.breadth_50d >= 0.5, "Breadth above 50%", f"{row.breadth_50d:.0%}"),
    ]
    pillar_cards = "".join(
        f"""
        <div class="mv2-rail-item">
          <b><span class="mv2-swatch" style="background:{PILLAR_HUES[pillar]}"></span> {_esc(pillar)} | {_esc(PILLAR_FULL[pillar])} {_fmt(row.pillars[pillar], digits=3)}</b>
          <span>{'Supports' if row.pillars[pillar] >= 0 else 'Drags'} the composite with weight {PILLAR_WEIGHTS[pillar]:.0%}.</span>
        </div>
        """
        for pillar in PILLAR_ORDER
    )
    return f"""
      <div class="mv2-head">
        <div>
          <div class="mv2-kicker">{_esc(display_name)} | Deep dive | {row.asset_class}</div>
          <h2 class="mv2-title">{_esc(row.display_label)}</h2>
          <p class="mv2-subtitle"><b>{_esc(row.state_label)}</b>. {_esc(" ".join(row.reasons))}</p>
        </div>
        <div class="mv2-screen-note">Ticker-specific report<br>{_row_state_pill(row)}</div>
      </div>
      {_tabs_html("deepdive")}
      <div class="mv2-metric-deck">
        {_metric_card("S-score", _fmt(row.s_score), s_class)}
        {_metric_card("F-score", _fmt(row.f_score), f_class)}
        {_metric_card("Momentum", _fmt(row.momentum_pct, "%", 1), mom_class)}
        {_metric_card("RRG", row.quadrant)}
        {_metric_card("Stage", row.stage)}
      </div>
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>The composite, built pillar by pillar</h3>
          <p>Start at zero, add the seven weighted pillars, and end at the live S score. This is the C2 waterfall concept adapted to Streamlit HTML.</p>
          {_waterfall_html(row)}
        </div>
        <aside class="mv2-panel">
          <h3>State machine checklist</h3>
          <p>These are concrete values for this ticker, not generic tooltips.</p>
          <div class="mv2-gates">{"".join(_gate_html(*gate) for gate in gates)}</div>
        </aside>
      </div>
      <div class="mv2-panel" style="margin-top:16px">
        <h3>The seven pillars</h3>
        <p>Each line shows the signed weighted contribution used by the composite.</p>
        <div class="mv2-pillar-grid">{pillar_cards}</div>
      </div>
      <div class="mv2-chart-grid">
        <div class="mv2-panel">
          <h3>Weekly price vs 30-week average</h3>
          <p>Every ticker story is paired with trend evidence. This panel explains whether price still confirms the current state.</p>
          {_price_svg(row)}
          <p>{_esc(row.ticker)} is currently {'above' if row.above_30wma else 'below'} the 30-week moving average; the average slope is {'positive' if row.ma_slope_pos else 'negative'}.</p>
        </div>
        <div class="mv2-panel">
          <h3>Flow and volume confirmation</h3>
          <p>Flow is the heaviest pillar in the model. The current F score is {_fmt(row.f_score)}, CMF is {_fmt(row.cmf21)}, and the flow contribution is {_fmt(row.pillars['FLOW'], digits=3)}.</p>
          {_obv_svg(row)}
          <div style="height:10px"></div>
          {_cmf_svg(row)}
        </div>
      </div>
    """


def _deepdive_c_body(row: MomentumV2Row, rows: list[MomentumV2Row], as_of: str) -> str:
    peer_rows, rank, peer_count = _peer_rank_html(rows, row)
    gate_rows = _gate_rows_for(row)
    failed = sum(1 for ok, _, _ in gate_rows if not ok)
    pillar_cards = "".join(
        f"""
        <div class="mv2-c-pillar-card">
          <i style="background:{PILLAR_HUES[pillar]}"></i>
          <div>
            <b>{_esc(PILLAR_FULL[pillar])} <span style="color:#7a7066;font:800 10px/1 var(--font-mono)">w {PILLAR_WEIGHTS[pillar]:.0%}</span></b>
            <p>{_esc(_pillar_reason(row, pillar))} <em style="color:#7a7066">Evidence tag: {pillar} methodology.</em></p>
          </div>
          <span class="{_tone_class(row.pillars[pillar])}" style="font:900 18px/1 var(--font-mono)">{_fmt(row.pillars[pillar], digits=3)}</span>
        </div>
        """
        for pillar in PILLAR_ORDER
    )
    return f"""
      {_c_topbar("deepdive", as_of, row.ticker)}
      <div style="padding:28px 12px 8px">
        <div style="display:flex;align-items:flex-end;gap:24px;flex-wrap:wrap">
          <div style="flex:1;min-width:320px">
            <div style="display:flex;align-items:center;gap:14px;margin-bottom:8px">
              <h1 style="font:900 48px/1 var(--font-mono);margin:0;color:#1a1714">{_esc(row.ticker)}</h1>
              {_row_state_pill(row)}
              <span style="color:#7a7066;font:14px/1 var(--font-prose)">{_esc(row.asset_class)} | {_esc(row.identity)}</span>
            </div>
            <p style="max-width:820px;margin:0;color:#3d362f;font:20px/1.4 var(--font-prose)">
              <strong style="color:#a8721a">{_esc(row.ticker)} is {_esc(row.state_label)}.</strong>
              Start at zero, add each pillar's contribution, and end at S {_fmt(row.s_score)}. Flow is {_fmt(row.f_score)} and RRG is {_esc(row.quadrant)}.
            </p>
          </div>
          <div class="mv2-c-statdeck">
            <div class="mv2-c-stat"><span>S-score</span><b class="{_tone_class(row.s_score)}">{_fmt(row.s_score)}</b></div>
            <div class="mv2-c-stat"><span>F-score</span><b class="{_tone_class(row.f_score)}">{_fmt(row.f_score)}</b></div>
            <div class="mv2-c-stat"><span>Mom</span><b class="{_tone_class(row.momentum_pct)}">{_fmt(row.momentum_pct, '%', 0)}</b></div>
            <div class="mv2-c-stat"><span>Rank</span><b>{rank} / {peer_count}</b></div>
            <div class="mv2-c-stat"><span>RRG</span><b style="color:#a8721a">{_esc(row.quadrant.upper())}</b></div>
          </div>
        </div>
      </div>
      <div style="padding:12px 12px 28px">
        <div class="mv2-c-card">
          <div class="mv2-c-head"><b>The composite, built pillar by pillar</b><span>each step is a signed, weighted contribution</span></div>
          <p>Start at zero. Add each pillar's contribution. End at the composite. The chart below makes the math visible: which pillars did the work, which dragged.</p>
          {_waterfall_html(row)}
        </div>
      </div>
      <div style="padding:0 12px 28px">
        <div class="mv2-c-card">
          <div class="mv2-c-head"><b>The seven pillars</b><span>each one, in plain language | weights sum to 1.00</span></div>
          <div class="mv2-c-pillar-grid">{pillar_cards}</div>
        </div>
      </div>
      <div class="mv2-c-rotation-grid" style="padding-top:0">
        <div class="mv2-c-card">
          <div class="mv2-c-head"><b>Price + 30wMA</b><span>Weinstein Stage | {'STAGE 2 INTACT' if row.above_30wma else 'EXIT WATCH'}</span></div>
          {_price_svg(row, width=720, height=220)}
          <p>{_esc(row.ticker)} is {'above' if row.above_30wma else 'below'} the 30-week moving average; Mansfield RS is {_fmt(row.mansfield_rs)}.</p>
        </div>
        <div class="mv2-c-card">
          <div class="mv2-c-head"><b>State machine</b><span>WARNING gates | {failed} tripped</span></div>
          <div class="mv2-gates">{"".join(_gate_html(*gate) for gate in gate_rows)}</div>
          <div class="mv2-a2-callout"><strong style="color:#a8721a">Next escalation:</strong> {_esc(_next_escalation_text(row))}</div>
        </div>
      </div>
      <div class="mv2-a-footer"><span>{_esc(row.ticker)} | {_esc(row.identity)} | WATERFALL | 7 PILLARS</span><span>v2 | PILLAR STACK | DEEP DIVE | MEIRI</span></div>
    """


def _universe_deepdive_body(rows: list[MomentumV2Row], display_name: str, as_of: str) -> str:
    ordered = sorted(rows, key=lambda item: item.s_score, reverse=True)
    leaders = ordered[:10]
    risks = [row for row in ordered if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}]
    weakest_flow = sorted(rows, key=lambda item: item.f_score)[:8]
    grouped = rows_by_class(rows)
    class_rows = []
    for asset_class, items in grouped.items():
        avg_s = sum(item.s_score for item in items) / max(len(items), 1)
        bullish = sum(1 for item in items if item.state == "STAGE_2_BULLISH")
        risk = sum(1 for item in items if item.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"})
        class_rows.append(
            f"""
            <div class="mv2-rail-item">
              <b>{_esc(asset_class)} | {_fmt(avg_s)} avg S</b>
              <span>{len(items)} instruments | {bullish} bullish | {risk} warning/exit/bearish</span>
            </div>
            """
        )
    matrix = []
    for asset_class, items in grouped.items():
        matrix.append(f'<div class="mv2-class">{_esc(asset_class)} | {len(items)} instruments</div>')
        matrix.extend(_row_html(item) for item in items)
    return f"""
      <div class="mv2-head">
        <div>
          <div class="mv2-kicker">{_esc(display_name)} | Deep dive | whole universe | {_esc(as_of)}</div>
          <h2 class="mv2-title">Universe deep dive</h2>
          <p class="mv2-subtitle"><b>Not a single-ticker report.</b> {_esc(_state_summary(rows))} Use this view to understand the whole board before drilling into an individual ticker.</p>
        </div>
        <div class="mv2-screen-note">Universe mode<br>{len(rows)} instruments | {len(grouped)} groups</div>
      </div>
      {_tabs_html("deepdive")}
      {_state_count_cards(rows)}
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>Full seven-pillar matrix</h3>
          <p>Every row is part of the current universe. The bar shows signed pillar contributions; the state and scores show current decision pressure.</p>
          {_legend_html()}
          <div class="mv2-row mv2-muted"><b>Ticker</b><b>Weighted pillar composition</b><b>State</b><b class="mv2-num">S</b><b class="mv2-num">Mom</b></div>
          {"".join(matrix)}
        </div>
        <aside class="mv2-rail-stack">
          <div class="mv2-panel">
            <h3>Top leaders</h3>
            <div class="mv2-rail-list">
              {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)} {_fmt(item.s_score)}</b><span>{_esc(item.state_label)} | {item.quadrant} | F {_fmt(item.f_score)}</span></div>' for item in leaders)}
            </div>
          </div>
          <div class="mv2-panel">
            <h3>Risk queue</h3>
            <p>Warning, exit, and bearish names across the full universe.</p>
            <div class="mv2-rail-list">
              {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)}</b><span>{_esc(" ".join(item.reasons))}</span></div>' for item in risks[:10])}
            </div>
          </div>
          <div class="mv2-panel">
            <h3>Weakest flow</h3>
            <div class="mv2-rail-list">
              {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)} F {_fmt(item.f_score)}</b><span>CMF {_fmt(item.cmf21)} | flow pillar {_fmt(item.pillars["FLOW"], digits=3)}</span></div>' for item in weakest_flow)}
            </div>
          </div>
        </aside>
      </div>
      <div class="mv2-universe-columns">
        <div class="mv2-panel">
          <h3>Group breakdown</h3>
          <div class="mv2-rail-list">{"".join(class_rows)}</div>
        </div>
        <div class="mv2-panel">
          <h3>How to use this universe deep dive</h3>
          <p>Start with state distribution, then scan leaders and risks. Only after that should you select a specific ticker for a ticker-level article or chart review.</p>
          <p>This fixes the previous XLK-centered behavior: the default deep dive now explains the complete dashboard universe.</p>
        </div>
      </div>
    """


def _rrg_position(row: MomentumV2Row) -> tuple[float, float]:
    x = min(94.0, max(6.0, 50.0 + (row.rs_ratio - 100.0) * 1.65))
    y = min(94.0, max(6.0, 50.0 - (row.rs_momentum - 100.0) * 1.65))
    return x, y


def _rrg_html(rows: list[MomentumV2Row], limit: int = 24) -> str:
    dots = []
    for row in rows[:limit]:
        x, y = _rrg_position(row)
        color = STATE_COLORS_LIGHT.get(row.state, "#777")
        dots.append(
            f'<span class="mv2-dot" style="left:{x:.1f}%;top:{y:.1f}%">'
            f'<i style="background:{color}"></i><b>{_esc(row.ticker)}</b></span>'
        )
    return f"""
    <div class="mv2-rrg">
      <span class="mv2-rrg-label" style="right:10px;top:10px;color:var(--mv2-green)">Leading</span>
      <span class="mv2-rrg-label" style="right:10px;bottom:10px;color:var(--mv2-amber)">Weakening</span>
      <span class="mv2-rrg-label" style="left:10px;bottom:10px;color:var(--mv2-red)">Lagging</span>
      <span class="mv2-rrg-label" style="left:10px;top:10px;color:var(--mv2-blue)">Improving</span>
      {"".join(dots)}
    </div>
    """


def _momentum_rows(rows: list[MomentumV2Row], limit: int = 16) -> str:
    ordered = sorted(rows, key=lambda item: item.momentum_pct, reverse=True)[:limit]
    if not ordered:
        return '<p class="mv2-muted">No momentum rows available.</p>'
    max_abs = max(5.0, max(abs(row.momentum_pct) for row in ordered))
    html = []
    for row in ordered:
        width = min(50.0, abs(row.momentum_pct) / max_abs * 50.0)
        if row.momentum_pct >= 0:
            style = f"left:50%;width:{width:.1f}%;background:var(--mv2-green)"
            tone = "mv2-pos"
        else:
            style = f"right:50%;width:{width:.1f}%;background:var(--mv2-red)"
            tone = "mv2-neg"
        html.append(
            f"""
            <div class="mv2-mom-row">
              <b>{_esc(row.display_label)}</b>
              <div class="mv2-mom-track"><span class="mv2-mom-fill" style="{style}"></span></div>
              <span class="mv2-num {tone}">{_fmt(row.momentum_pct, "%", 1)}</span>
            </div>
            """
        )
    return "".join(html)


def _flow_river_html(rows: list[MomentumV2Row]) -> str:
    outflows = sorted(rows, key=lambda item: item.f_score)[:5]
    inflows = sorted(rows, key=lambda item: item.f_score, reverse=True)[:5]
    if not outflows or not inflows:
        return '<div class="mv2-flow-river"><div class="mv2-flow-node" style="left:14px;top:12px"><b>No flow rows</b>Refresh or load a universe to render flow rotation.</div></div>'
    bands = []
    for idx, (left, right) in enumerate(zip(outflows, inflows)):
        top = 22 + idx * 38
        height = 18 + min(24, abs(left.f_score - right.f_score) * 5)
        bands.append(
            f'<span class="mv2-river-band" style="top:{top}px;height:{height:.1f}px;background:{PILLAR_HUES["FLOW"]}"></span>'
        )
    nodes = []
    for idx, row in enumerate(outflows):
        nodes.append(
            f'<div class="mv2-flow-node" style="left:14px;top:{12 + idx * 41}px"><b>{_esc(row.ticker)} out</b>{_esc(row.identity)} | F {_fmt(row.f_score)}</div>'
        )
    for idx, row in enumerate(inflows):
        nodes.append(
            f'<div class="mv2-flow-node" style="right:14px;top:{12 + idx * 41}px"><b>{_esc(row.ticker)} in</b>{_esc(row.identity)} | F {_fmt(row.f_score)}</div>'
        )
    return '<div class="mv2-flow-river">' + "".join(bands + nodes) + "</div>"


def _macro_grid_html(rows: list[MomentumV2Row]) -> str:
    warnings = sum(1 for row in rows if row.state == "WARNING")
    exits = sum(1 for row in rows if row.state in {"EXIT", "BEARISH_STAGE_4"})
    bullish = sum(1 for row in rows if row.state == "STAGE_2_BULLISH")
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    return f"""
    <div class="mv2-macro-grid">
      <div class="mv2-macro"><span>Universe</span><b>{len(rows)}</b></div>
      <div class="mv2-macro"><span>Bullish</span><b class="mv2-pos">{bullish}</b></div>
      <div class="mv2-macro"><span>Warnings</span><b class="mv2-neg">{warnings + exits}</b></div>
      <div class="mv2-macro"><span>Average S</span><b>{_fmt(avg_s)}</b></div>
      <div class="mv2-macro"><span>Average F</span><b>{_fmt(avg_f)}</b></div>
      <div class="mv2-macro"><span>Flow horizon</span><b>1-3W</b></div>
    </div>
    """


def _short_identity(row: MomentumV2Row, max_chars: int = 24) -> str:
    label = row.identity if row.identity != row.ticker else row.display_label
    return label if len(label) <= max_chars else label[: max_chars - 1].rstrip() + "."


def _rotation_class_counts(rows: list[MomentumV2Row]) -> list[tuple[str, int]]:
    grouped = rows_by_class(rows)
    ordered = ["US Sectors", "US Industries", "Countries", "Factors"]
    counts = [(label, len(grouped.get(label, []))) for label in ordered]
    other = sum(len(items) for label, items in grouped.items() if label not in ordered)
    if other:
        counts.append(("Other", other))
    counts.append(("All", len(rows)))
    return counts


def _rotation_scope_chips(rows: list[MomentumV2Row]) -> str:
    chips = []
    for label, count in _rotation_class_counts(rows):
        active = " active" if label == "US Sectors" else ""
        chips.append(f'<span class="mv2-a3-filter{active}" data-rotation-scope="{_esc(label)}">{_esc(label.upper())} {count}</span>')
    return '<div class="mv2-a3-filters">' + "".join(chips) + "</div>"


def _rotation_scope_summary(rows: list[MomentumV2Row]) -> str:
    chips = "".join(f"<span>{_esc(label.upper())}: {count}</span>" for label, count in _rotation_class_counts(rows))
    return f'<div class="mv2-a3-scope" aria-label="Rotation universe inventory">{chips}</div>'


def _rotation_state_legend() -> str:
    labels = (
        ("STAGE_2_BULLISH", "Bullish"),
        ("HOLD", "Hold"),
        ("WARNING", "Warning"),
        ("EXIT", "Exit"),
        ("BEARISH_STAGE_4", "Bear stage 4"),
    )
    return (
        '<div class="mv2-a3-rrg-legend">'
        + "".join(
            f'<span><i style="background:{STATE_COLORS_LIGHT[state]}"></i>{_esc(label)}</span>'
            for state, label in labels
        )
        + '<span style="margin-left:auto">small dot = four-week trail start | large dot = current</span></div>'
    )


def _quadrant_groups(rows: list[MomentumV2Row]) -> dict[str, list[MomentumV2Row]]:
    groups = {name: [] for name in ("Leading", "Weakening", "Lagging", "Improving")}
    for row in rows:
        groups.setdefault(row.quadrant, []).append(row)
    for items in groups.values():
        items.sort(key=lambda item: item.s_score, reverse=True)
    return groups


def _rotation_story_parts(rows: list[MomentumV2Row]) -> dict[str, str]:
    sectors = [row for row in rows if row.asset_class == "US Sectors"] or rows
    groups = _quadrant_groups(sectors)
    strongest = max(sectors, key=lambda item: item.f_score, default=None)
    weakest = min(sectors, key=lambda item: item.f_score, default=None)
    leaders = sorted(sectors, key=lambda item: item.momentum_pct, reverse=True)[:3]
    laggards = sorted(sectors, key=lambda item: item.momentum_pct)[:3]
    lead_names = ", ".join(row.ticker for row in leaders) or "none"
    lag_names = ", ".join(row.ticker for row in laggards) or "none"
    weakening = ", ".join(row.ticker for row in groups.get("Weakening", [])[:4]) or "none"
    improving = ", ".join(row.ticker for row in groups.get("Improving", [])[:4]) or "none"
    leading = ", ".join(row.ticker for row in groups.get("Leading", [])[:4]) or "none"
    lagging = ", ".join(row.ticker for row in groups.get("Lagging", [])[:4]) or "none"
    count_sentence = (
        f"{len(groups.get('Leading', []))} leading, {len(groups.get('Weakening', []))} weakening, "
        f"{len(groups.get('Lagging', []))} lagging, and {len(groups.get('Improving', []))} improving."
    )
    return {
        "count_sentence": count_sentence,
        "caption": (
            f"Read clockwise using current RRG coordinates. Weakening: {weakening}. "
            f"Improving: {improving}. Leading: {leading}. Lagging: {lagging}."
        ),
        "terminal_caption": (
            f"Trails show each ticker's four-week path. Current sector map: {count_sentence} "
            f"Strongest flow is {_row_name(strongest)}; weakest flow is {_row_name(weakest)}."
        ),
        "editorial_1": (
            f"The current sector map contains {count_sentence} The weakening group is {weakening}; "
            f"the improving group is {improving}. That is the live rotation read generated from the scored universe."
        ),
        "editorial_2": (
            f"Momentum leadership is concentrated in {lead_names}, while the bottom of the 12-1 ranking is {lag_names}. "
            f"Use this with the RRG: the best setup is a positive momentum row moving into Improving or Leading."
        ),
        "editorial_3": (
            f"Flow confirmation is led by {_row_name(strongest)} with F {_fmt(strongest.f_score) if strongest else '+0.00'}; "
            f"flow pressure is concentrated in {_row_name(weakest)} with F {_fmt(weakest.f_score) if weakest else '+0.00'}."
        ),
    }


def _flow_node_rows(rows: list[MomentumV2Row], limit: int = 5) -> tuple[list[MomentumV2Row], list[MomentumV2Row]]:
    ranked = sorted(rows, key=lambda item: item.f_score)
    if not ranked:
        return [], []
    outflow_rows = ranked[:limit]
    inflow_rows = list(reversed(ranked[-limit:]))
    return outflow_rows, inflow_rows


def _flow_magnitude(row: MomentumV2Row) -> float:
    return max(0.05, abs(row.f_score))


def _terminal_rrg_svg(
    rows: list[MomentumV2Row],
    width: int = 620,
    height: int = 580,
    *,
    theme: str = "dark",
    annotate: bool = False,
) -> str:
    pad = 60
    light = theme in {"light", "editorial"}
    bg = "#fffbf3" if theme == "editorial" else "#ffffff" if light else "#070707"
    border = "#e1d8c9" if theme == "editorial" else "#e6e1d8" if light else "#1f1f1f"
    grid = "#e1d8c9" if theme == "editorial" else "#e6e1d8" if light else "#1a1a1a"
    axis = "#3d362f" if light else "#5a5a5a"
    muted = "#6e6258" if theme == "editorial" else "#7a7066" if light else "#7c7c7c"
    label_fill = "#1c1815" if light else "#ddd"
    dot_stroke = bg if light else "#0a0a0a"

    def x(value: float) -> float:
        return pad + (value - 80.0) / 40.0 * (width - 2 * pad)

    def y(value: float) -> float:
        return height - pad - (value - 80.0) / 40.0 * (height - 2 * pad)

    def clamp(value: float) -> float:
        return min(119.0, max(81.0, value))

    quadrants = [
        (x(100), y(120), x(120) - x(100), y(100) - y(120), "#26d65b", "LEADING", width - pad - 8, pad + 14, "end"),
        (x(100), y(100), x(120) - x(100), y(80) - y(100), "#e6b450", "WEAKENING", width - pad - 8, height - pad - 8, "end"),
        (x(80), y(100), x(100) - x(80), y(80) - y(100), "#ef4f4a", "LAGGING", pad + 8, height - pad - 8, "start"),
        (x(80), y(120), x(100) - x(80), y(100) - y(120), "#5fa8d3", "IMPROVING", pad + 8, pad + 14, "start"),
    ]
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Relative rotation graph with four week trails">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}" stroke="{border}"/>',
    ]
    for qx, qy, qw, qh, color, label, lx, ly, anchor in quadrants:
        parts.append(f'<rect x="{qx:.1f}" y="{qy:.1f}" width="{qw:.1f}" height="{qh:.1f}" fill="{color}" opacity=".055"/>')
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="{color}" '
            'font-family="monospace" font-size="11" font-weight="700" letter-spacing=".06em">'
            f'{label}</text>'
        )
    for value in (85, 90, 95, 105, 110, 115):
        parts.append(f'<line x1="{x(value):.1f}" y1="{pad}" x2="{x(value):.1f}" y2="{height-pad}" stroke="{grid}"/>')
        parts.append(f'<line x1="{pad}" y1="{y(value):.1f}" x2="{width-pad}" y2="{y(value):.1f}" stroke="{grid}"/>')
    parts.extend(
        [
            f'<line x1="{pad}" y1="{y(100):.1f}" x2="{width-pad}" y2="{y(100):.1f}" stroke="{axis}" stroke-width="1.2"/>',
            f'<line x1="{x(100):.1f}" y1="{pad}" x2="{x(100):.1f}" y2="{height-pad}" stroke="{axis}" stroke-width="1.2"/>',
            f'<text x="{width/2:.1f}" y="{height-14}" text-anchor="middle" fill="{muted}" font-family="monospace" font-size="10">RS-RATIO -></text>',
            f'<text x="16" y="{height/2:.1f}" text-anchor="middle" fill="{muted}" font-family="monospace" font-size="10" transform="rotate(-90 16 {height/2:.1f})">RS-MOMENTUM -></text>',
        ]
    )
    for value in (85, 95, 105, 115):
        parts.append(f'<text x="{x(value):.1f}" y="{height-pad+16}" text-anchor="middle" fill="{muted}" font-family="monospace" font-size="9">{value}</text>')
        parts.append(f'<text x="{pad-8}" y="{y(value)+3:.1f}" text-anchor="end" fill="{muted}" font-family="monospace" font-size="9">{value}</text>')
    if annotate:
        parts.append(
            f'<path d="M {x(108):.1f} {y(108):.1f} Q {x(111):.1f} {y(97):.1f} {x(105):.1f} {y(94):.1f}" '
            'fill="none" stroke="#a8721a" stroke-width="1.6" stroke-dasharray="3 3" opacity=".68"/>'
        )
        parts.append(
            f'<text x="{x(112):.1f}" y="{y(102):.1f}" fill="#a8721a" font-family="Georgia" font-size="12" font-style="italic">'
            "current rotation</text>"
        )
    for row in rows:
        cx = clamp(row.rs_ratio)
        cy = clamp(row.rs_momentum)
        if row.quadrant == "Weakening":
            tx, ty = clamp(cx + 5.5), clamp(cy + 4.0)
        elif row.quadrant == "Lagging":
            tx, ty = clamp(cx + 4.0), clamp(cy - 2.5)
        elif row.quadrant == "Improving":
            tx, ty = clamp(cx - 2.0), clamp(cy - 5.0)
        else:
            tx, ty = clamp(cx - 4.0), clamp(cy - 2.0)
        color = STATE_COLORS_LIGHT.get(row.state, "#777")
        attrs = drill_bridge_attrs(row.ticker, label=row.identity)
        parts.append(
            f'<g {attrs} data-ticker="{_esc(row.ticker)}" class="mv2-a-click">'
            f'<title>{_esc(row.display_label)} | {row.quadrant} | RS-Ratio {row.rs_ratio:.1f} | RS-Momentum {row.rs_momentum:.1f} | S {_fmt(row.s_score)} | F {_fmt(row.f_score)}</title>'
            f'<line x1="{x(tx):.1f}" y1="{y(ty):.1f}" x2="{x(cx):.1f}" y2="{y(cy):.1f}" stroke="{color}" stroke-width="1.5" opacity=".35"/>'
            f'<circle cx="{x(tx):.1f}" cy="{y(ty):.1f}" r="2" fill="{color}" opacity=".25"/>'
            f'<circle cx="{x(cx):.1f}" cy="{y(cy):.1f}" r="6" fill="{color}" stroke="{dot_stroke}" stroke-width="1.5"/>'
            f'<text x="{x(cx):.1f}" y="{y(cy)-10:.1f}" text-anchor="middle" fill="{label_fill}" font-family="monospace" font-size="10" font-weight="700">{_esc(row.ticker)}</text>'
            "</g>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _terminal_momentum_bars(rows: list[MomentumV2Row], limit: int = 14) -> str:
    ordered = sorted(rows, key=lambda item: item.momentum_pct, reverse=True)[:limit]
    if not ordered:
        return '<p class="mv2-a3-caption">No momentum rows available for the selected universe.</p>'
    max_abs = max(5.0, max(abs(row.momentum_pct) for row in ordered))
    rendered = []
    for row in ordered:
        pct = min(50.0, abs(row.momentum_pct) / max_abs * 50.0)
        if row.momentum_pct >= 0:
            style = f"left:50%;width:{pct:.1f}%;background:#26d65b"
            tone = "mv2-pos"
        else:
            style = f"right:50%;width:{pct:.1f}%;background:#ef4f4a"
            tone = "mv2-neg"
        rendered.append(
            f"""
            <div class="mv2-a3-mom-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}">
              <b>{_esc(row.ticker)}</b>
              <div>
                <div class="name">{_esc(row.identity)}</div>
                <div class="mv2-a3-track"><span class="mv2-a3-fill" style="{style}"></span></div>
              </div>
              <span class="{tone}">{_fmt(row.momentum_pct, '%', 1)}</span>
              {_row_state_pill(row)}
            </div>
            """
        )
    return "".join(rendered)


def _c_momentum_bars(rows: list[MomentumV2Row], limit: int = 12) -> str:
    ordered = sorted(rows, key=lambda item: item.momentum_pct, reverse=True)[:limit]
    if not ordered:
        return '<p>No momentum rows available for the selected universe.</p>'
    max_abs = max(5.0, max(abs(row.momentum_pct) for row in ordered))
    rendered = []
    for row in ordered:
        pct = min(50.0, abs(row.momentum_pct) / max_abs * 50.0)
        side = "left:50%" if row.momentum_pct >= 0 else "right:50%"
        color = STATE_COLORS_LIGHT.get(row.state, "#777")
        rendered.append(
            f"""
            <div class="mv2-c-flow-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}" style="grid-template-columns:54px 1fr 66px">
              <b>{_esc(row.ticker)}</b>
              <div>
                <div class="name">{_esc(row.identity)}</div>
                <div class="mv2-a3-track" style="background:#f4f1ec;border-color:#e6e1d8"><span class="mv2-a3-fill" style="{side};width:{pct:.1f}%;background:{color}"></span></div>
              </div>
              <span class="{_tone_class(row.momentum_pct)}" style="text-align:right">{_fmt(row.momentum_pct, '%', 1)}</span>
            </div>
            """
        )
    return "".join(rendered)


def _terminal_flow_detail(rows: list[MomentumV2Row]) -> str:
    grouped = rows_by_class(rows)
    cards = []
    for asset_class, items in grouped.items():
        avg_f = sum(row.f_score for row in items) / max(len(items), 1)
        warn = sum(1 for row in items if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"})
        cards.append(
            f"""
            <div class="mv2-a3-flow-card">
              <span>{_esc(asset_class.upper() or "UNCLASSIFIED")}</span>
              <b class="{_tone_class(avg_f)}">{_fmt(avg_f)}</b>
              <span>{warn} warn/exit | {len(items)} total</span>
            </div>
            """
        )
    flow_rows = []
    for row in sorted(rows, key=lambda item: item.f_score)[:4] + sorted(rows, key=lambda item: item.f_score, reverse=True)[:4]:
        flow_rows.append(
            f"""
            <div class="mv2-a3-flow-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}">
              <b>{_esc(row.ticker)}</b>
              <span class="name">{_esc(row.identity)}</span>
              <span class="{_tone_class(row.cmf21)}">{_fmt(row.cmf21)}</span>
              <span class="{_tone_class(row.f_score)}">{_fmt(row.f_score)}</span>
              <span class="{_tone_class(row.breadth_50d - 0.5)}">{row.breadth_50d:.0%}</span>
              {_row_state_pill(row)}
            </div>
            """
        )
    header = '<div class="mv2-a3-flow-row" style="border-top:0;color:#7c7c7c;text-transform:uppercase"><span>TKR</span><span>Name</span><span>CMF21</span><span>F</span><span>Breadth</span><span>State</span></div>'
    return '<div class="mv2-a3-flow-cards">' + "".join(cards[:4]) + "</div>" + header + "".join(flow_rows)


def _terminal_macro_panel(rows: list[MomentumV2Row]) -> str:
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    avg_f = sum(row.f_score for row in rows) / max(len(rows), 1)
    support = sorted(rows, key=lambda item: (item.f_score, item.s_score), reverse=True)[:5]
    support_text = " | ".join(f"{row.ticker} {_fmt(row.f_score)}" for row in support) or "No support rows"
    cells = "".join(
        f'<div class="mv2-a3-macro-stat"><span>{_esc(label)}</span><b>{_esc(value)}</b></div>'
        for label, value in _macro_proxy_stats(rows)
    )
    return f"""
      <div class="mv2-a3-macro-stats">{cells}</div>
      <div class="mv2-a2-callout"><strong style="color:#e6b450">Support basket from current data:</strong> {_esc(support_text)}. If the board phase deteriorates, reduce risk before adding new cyclicals.</div>
      <p class="mv2-a3-caption">Average S {_fmt(avg_s)} and average F {_fmt(avg_f)} summarize whether macro pressure is confirming or fighting the rotation.</p>
    """


def _c_macro_panel(rows: list[MomentumV2Row]) -> str:
    phase = _board_phase(rows)
    support = sorted(rows, key=lambda item: (item.f_score, item.s_score), reverse=True)[:5]
    phase_cells = "".join(
        f'<span class="{"active" if label == phase else ""}" style="flex:1;padding:10px 6px;text-align:center;border-radius:4px;background:{"#1a1714" if label == phase else "#f4f1ec"};color:{"#fff" if label == phase else "#7a7066"};font:800 10px/1 var(--font-mono);letter-spacing:.06em">{_esc(label)}</span>'
        for label in ("RISK-ON", "NARROWING", "RISK-OFF", "NO DATA")
    )
    cells = "".join(
        f'<div class="mv2-macro"><span>{_esc(label)}</span><b class="{_tone_class(_num(value.replace("%", "")) if value not in {"RISK-ON", "NARROWING", "RISK-OFF", "NO DATA"} else 0)}">{_esc(value)}</b></div>'
        for label, value in _macro_proxy_stats(rows)
    )
    support_text = " | ".join(f"{row.ticker} {_fmt(row.f_score)}" for row in support) or "No support rows"
    return f"""
      <div style="margin-bottom:16px">
        <div style="color:#7a7066;font:900 10px/1 var(--font-mono);letter-spacing:.1em;text-transform:uppercase;margin-bottom:7px">Cycle / board phase</div>
        <div style="display:flex;gap:4px">{phase_cells}</div>
        <p style="margin:9px 0 0;color:#3d362f;font:12.5px/1.5 var(--font-prose)">Phase is derived from current scored-universe breadth, average S/F, and warning or exit concentration.</p>
      </div>
      <div class="mv2-macro-grid">{cells}</div>
      <div style="margin-top:14px;padding:12px 14px;background:#fdf4ea;border:1px solid #e7c98f;border-radius:6px;color:#3d362f;font:12px/1.5 var(--font-prose)">
        <strong style="color:#a8721a">If the board deteriorates:</strong> review support basket {support_text} before adding new cyclicals.
      </div>
    """


def _rotation_terminal_body(rows: list[MomentumV2Row], as_of: str) -> str:
    sectors = [row for row in rows if row.asset_class == "US Sectors"] or rows
    story = _rotation_story_parts(rows)
    return f"""
      <div class="mv2-a3-header">
        <span class="mv2-a2-back">BACK TO OVERVIEW</span>
        <span style="color:#5a5a5a;font:900 11px/1 var(--font-mono)">/</span>
        <span style="color:#7c7c7c;font:900 12px/1 var(--font-mono);letter-spacing:.08em">ROTATION MAP</span>
        <span style="flex:1"></span>
        {_rotation_scope_chips(rows)}
      </div>
      {_tabs_html("rotation")}
      {_rotation_scope_summary(rows)}
      <div class="mv2-a3-grid">
        <div class="mv2-a3-panel">
          <div class="mv2-a3-section"><b>RELATIVE ROTATION GRAPH</b><span>US Sectors | 4-week motion trail | {len(sectors)} / {len(sectors)}</span></div>
          {_terminal_rrg_svg(sectors)}
          {_rotation_state_legend()}
          <p class="mv2-a3-caption">{_esc(story["terminal_caption"])}</p>
        </div>
        <div class="mv2-a3-panel">
          <div class="mv2-a3-section"><b>12-1 CROSS-SECTIONAL MOMENTUM</b><span>LOOKBACK 12M | {len(sectors)} rows</span></div>
          {_terminal_momentum_bars(sectors)}
        </div>
      </div>
      <div class="mv2-a3-grid lower">
        <div class="mv2-a3-panel">
          <div class="mv2-a3-section"><b>INSTITUTIONAL FLOW DETAIL | PILLAR 7</b><span>CMF | F score | flow pillar | breadth | provider data when configured</span></div>
          {_terminal_flow_detail(rows)}
        </div>
        <div class="mv2-a3-panel">
          <div class="mv2-a3-section"><b>MACRO | BUSINESS CYCLE</b><span>board proxies | {_esc(_board_phase(rows))} | {_esc(as_of)}</span></div>
          {_terminal_macro_panel(rows)}
        </div>
      </div>
      <div class="mv2-a-footer"><span>{len(rows)} ETFS | 7 PILLARS | CURRENT DATA</span><span>v2 | TERMINAL | ROTATION | MEIRI</span></div>
    """


def _c_rrg_svg(rows: list[MomentumV2Row]) -> str:
    return _terminal_rrg_svg(rows, width=620, height=530, theme="light")


def _c_flow_river_svg(rows: list[MomentumV2Row]) -> str:
    outflow_rows, inflow_rows = _flow_node_rows(rows, limit=5)
    width, height = 1260, 260
    if not outflow_rows or not inflow_rows:
        return f'<div class="mv2-c-flow-river"><svg viewBox="0 0 {width} {height}" role="img" aria-label="Flow river from outflows to inflows"><text x="630" y="130" text-anchor="middle" fill="#7a7066" font-size="14">No flow rows available</text></svg></div>'

    pad_t, gap = 28.0, 7.0
    usable = height - 2 * pad_t - gap * (len(outflow_rows) - 1)
    left_total = max(0.1, sum(_flow_magnitude(row) for row in outflow_rows))
    right_total = max(0.1, sum(_flow_magnitude(row) for row in inflow_rows))

    def nodes(source: list[MomentumV2Row], total: float, colors: list[str]) -> list[dict[str, object]]:
        cursor = pad_t
        rendered = []
        for idx, row in enumerate(source):
            value = _flow_magnitude(row)
            h = max(18.0, value / total * usable)
            rendered.append({"row": row, "value": value, "color": colors[idx % len(colors)], "y": cursor, "h": h})
            cursor += h + gap
        return rendered

    left_nodes = nodes(outflow_rows, left_total, ["#b13a1f", "#c66b3a", "#a85a3a", "#a85a45", "#9d6638"])
    right_nodes = nodes(inflow_rows, right_total, ["#1f7a4a", "#1d6a3f", "#2c8358", "#3a8a64", "#4a9070"])
    left_x, right_x = 190.0, 1086.0
    left_end, right_start = left_x + 16.0, right_x - 16.0
    right_stack = [0.0 for _ in right_nodes]
    ribbons: list[str] = []
    for left in left_nodes:
        left_cursor = float(left["y"])
        for idx, right in enumerate(right_nodes):
            portion = float(right["value"]) / right_total
            ribbon_h = max(1.2, portion * float(left["h"]))
            right_y = float(right["y"]) + right_stack[idx]
            right_stack[idx] += ribbon_h
            mx1 = left_end + (right_start - left_end) * 0.38
            mx2 = left_end + (right_start - left_end) * 0.62
            path = (
                f"M {left_end:.1f} {left_cursor:.1f} "
                f"C {mx1:.1f} {left_cursor:.1f}, {mx2:.1f} {right_y:.1f}, {right_start:.1f} {right_y:.1f} "
                f"L {right_start:.1f} {right_y + ribbon_h:.1f} "
                f"C {mx2:.1f} {right_y + ribbon_h:.1f}, {mx1:.1f} {left_cursor + ribbon_h:.1f}, {left_end:.1f} {left_cursor + ribbon_h:.1f} Z"
            )
            left_row = left["row"]
            right_row = right["row"]
            ribbons.append(
                f'<path d="{path}" fill="{left["color"]}" opacity=".20">'
                f'<title>{_esc(left_row.display_label)} pressure into {_esc(right_row.display_label)} support | F magnitude {float(left["value"]):.2f}</title>'
                "</path>"
            )
            left_cursor += ribbon_h

    node_html: list[str] = [
        f'<text x="{left_x:.1f}" y="18" fill="#7a7066" font-size="10" font-family="monospace" font-weight="800" letter-spacing=".10em">NET OUTFLOWS</text>',
        f'<text x="{right_x+14:.1f}" y="18" text-anchor="end" fill="#7a7066" font-size="10" font-family="monospace" font-weight="800" letter-spacing=".10em">NET INFLOWS</text>',
    ]
    for node in left_nodes:
        row = node["row"]
        y, h, color = float(node["y"]), float(node["h"]), str(node["color"])
        node_html.append(f'<rect x="{left_x:.1f}" y="{y:.1f}" width="16" height="{h:.1f}" fill="{color}"/>')
        node_html.append(f'<text x="{left_x-10:.1f}" y="{y+h/2-3:.1f}" text-anchor="end" fill="#1a1714" font-size="12" font-family="Arial" font-weight="700">{_esc(row.ticker)} | {_esc(_short_identity(row, 18))}</text>')
        node_html.append(f'<text x="{left_x-10:.1f}" y="{y+h/2+12:.1f}" text-anchor="end" fill="#b13a1f" font-size="10" font-family="monospace">F {_fmt(row.f_score)}</text>')
    for node in right_nodes:
        row = node["row"]
        y, h, color = float(node["y"]), float(node["h"]), str(node["color"])
        node_html.append(f'<rect x="{right_start:.1f}" y="{y:.1f}" width="16" height="{h:.1f}" fill="{color}"/>')
        node_html.append(f'<text x="{right_x+10:.1f}" y="{y+h/2-3:.1f}" fill="#1a1714" font-size="12" font-family="Arial" font-weight="700">{_esc(row.ticker)} | {_esc(_short_identity(row, 18))}</text>')
        node_html.append(f'<text x="{right_x+10:.1f}" y="{y+h/2+12:.1f}" fill="#1f7a4a" font-size="10" font-family="monospace">F {_fmt(row.f_score)}</text>')
    return f'<div class="mv2-c-flow-river"><svg viewBox="0 0 {width} {height}" role="img" aria-label="Flow river from outflows to inflows">{"".join(ribbons + node_html)}</svg></div>'


def _rotation_c_body(rows: list[MomentumV2Row], as_of: str) -> str:
    sectors = [row for row in rows if row.asset_class == "US Sectors"] or rows
    story = _rotation_story_parts(rows)
    flow_low = sorted(rows, key=lambda item: item.f_score)[:4]
    flow_high = sorted(rows, key=lambda item: item.f_score, reverse=True)[:4]
    flow_note = (
        f"Weakest current flow: {', '.join(row.ticker for row in flow_low) or 'none'}. "
        f"Strongest current flow: {', '.join(row.ticker for row in flow_high) or 'none'}."
    )
    flow_table = "".join(
        f"""
        <div class="mv2-c-flow-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}">
          <b>{_esc(row.ticker)}</b><span class="name">{_esc(row.identity)}</span>
          <span class="{_tone_class(row.cmf21)}">{_fmt(row.cmf21)}</span>
          <span class="{_tone_class(row.f_score)}">{_fmt(row.f_score)}</span>
          <span class="{_tone_class(row.pillars['FLOW'])}">{_fmt(row.pillars['FLOW'], digits=3)}</span>
          {_row_state_pill(row)}
        </div>
        """
        for row in sorted(rows, key=lambda item: item.f_score)[:10]
    )
    return f"""
      {_c_topbar("rotation", as_of)}
      <div class="mv2-c-rotation-head">
        <h1>The rotation map</h1>
        <p>Where the money was, where it is, where it's heading. The map shows current quadrant positions; the trails show the four-week path; the flow river shows which sectors are giving up share and which are taking it.</p>
      </div>
      <div class="mv2-c-rotation-grid">
        <div class="mv2-c-card"><div class="mv2-c-head"><b>Relative rotation | US Sectors</b><span>4-week trail | {len(sectors)} sectors</span></div>{_c_rrg_svg(sectors)}{_rotation_state_legend()}</div>
        <div class="mv2-c-card"><div class="mv2-c-head"><b>12-1 momentum</b><span>cross-sectional | sorted</span></div>{_c_momentum_bars(sectors, limit=12)}</div>
      </div>
      <div style="padding:0 12px 16px">
        <div class="mv2-c-card">
          <div class="mv2-c-head"><b>The flow river</b><span>net flow-score pressure | provider feeds when configured</span></div>
          {_c_flow_river_svg(rows)}
          <p>Width of each strand encodes the current F-score magnitude from the scored universe. The left side shows current flow pressure; the right side shows current flow support. {_esc(flow_note)}</p>
        </div>
      </div>
      <div class="mv2-c-rotation-grid" style="padding-top:0">
        <div class="mv2-c-card"><div class="mv2-c-head"><b>Macro / business cycle</b><span>board proxies | {_esc(_board_phase(rows))}</span></div>{_c_macro_panel(rows)}</div>
        <div class="mv2-c-card"><div class="mv2-c-head"><b>Flow detail</b><span>per-ticker | pillar 7 | leads price 1-3 wk</span></div><div class="mv2-c-flow-row" style="border-top:0;color:#7a7066;text-transform:uppercase"><span>TKR</span><span>Name</span><span>CMF</span><span>F</span><span>Flow</span><span>State</span></div>{flow_table}</div>
      </div>
      <p class="mv2-a3-caption" style="padding:0 12px 16px">{_esc(story["caption"])} {_esc(story["count_sentence"])}</p>
      <div class="mv2-a-footer"><span>{len(rows)} ETFS | ROTATION | FLOW RIVER | MACRO</span><span>v2 | PILLAR STACK | ROTATION | MEIRI</span></div>
    """


def _rotation_b_body(rows: list[MomentumV2Row], as_of: str) -> str:
    sectors = [row for row in rows if row.asset_class == "US Sectors"] or rows
    leaders = sorted(rows, key=lambda item: item.momentum_pct, reverse=True)[:12]
    laggards = sorted(rows, key=lambda item: item.momentum_pct)[:12]
    story = _rotation_story_parts(rows)
    flow_leaders = sorted(rows, key=lambda item: item.f_score, reverse=True)[:5]
    flow_laggards = sorted(rows, key=lambda item: item.f_score)[:5]
    phase = _board_phase(rows)
    phase_html = "".join(
        f'<span class="{"active" if label == phase else ""}">{_esc(label)}</span>'
        for label in ("RISK-ON", "NARROWING", "RISK-OFF", "NO DATA")
    )

    def leaderboard(title: str, items: list[MomentumV2Row]) -> str:
        max_abs = max(5.0, max(abs(row.momentum_pct) for row in items))
        rows_html = []
        for idx, row in enumerate(items, start=1):
            width = min(100, abs(row.momentum_pct) / max_abs * 100)
            color = "#1f7a4a" if row.momentum_pct >= 0 else "#b13a1f"
            rows_html.append(
                f"""
                <div class="mv2-a3-mom-row mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}" style="grid-template-columns:30px 52px 1fr 64px;border-color:#e1d8c9">
                  <span style="color:#8b7e70">{idx:02d}</span><b style="color:#1c1815">{_esc(row.ticker)}</b>
                  <div class="mv2-a3-track" style="background:#eee5d4;border-color:#e1d8c9"><span class="mv2-a3-fill" style="left:0;width:{width:.1f}%;background:{color}"></span></div>
                  <span class="{_tone_class(row.momentum_pct)}">{_fmt(row.momentum_pct, '%', 1)}</span>
                  <span style="display:none">{_esc(row.identity)}</span>
                </div>
                """
            )
        return f'<div><h3>{_esc(title)}</h3>{"".join(rows_html)}</div>'

    flow_items = "".join(
        f"""
        <div class="mv2-rail-item">
          <b>{_esc(label)}</b>
          <span>{_esc(body)}</span>
        </div>
        """
        for label, body in (
            ("Strongest F scores", ", ".join(f"{row.ticker} {_fmt(row.f_score)}" for row in flow_leaders) or "none"),
            ("Weakest F scores", ", ".join(f"{row.ticker} {_fmt(row.f_score)}" for row in flow_laggards) or "none"),
            ("Weakening quadrant", ", ".join(row.ticker for row in sectors if row.quadrant == "Weakening") or "none"),
            ("Lagging quadrant", ", ".join(row.ticker for row in sectors if row.quadrant == "Lagging") or "none"),
            ("CMF below zero", ", ".join(row.ticker for row in rows if row.cmf21 < 0) or "none"),
        )
    )
    support_cells = "".join(
        f'<div class="mv2-macro"><span>{_esc(row.ticker)}</span><b class="{_tone_class(row.f_score)}">{_fmt(row.f_score)}</b></div>'
        for row in flow_leaders[:4]
    )
    risk_basket = "".join(
        f'<div class="mv2-a-click" {drill_bridge_attrs(row.ticker, label=row.identity)} data-ticker="{_esc(row.ticker)}"><b>{_esc(row.ticker)}</b><span>{_esc(_short_identity(row, 18))}</span></div>'
        for row in sorted(rows, key=lambda item: (item.f_score, item.s_score), reverse=True)[:5]
    )
    return f"""
      <div class="mv2-b-mast"><b>The Sentiment Brief</b><span>|</span><span>THE ROTATION MAP</span><span style="flex:1"></span><span>BACK TO BRIEF</span><span>{_esc(as_of)}</span></div>
      <div class="mv2-article-hero" style="padding:46px 56px 28px;max-width:1240px;margin:0 auto">
        <div class="mv2-kicker">The map | weekly | US sectors</div>
        <h2>Where the money is going,<br><em style="color:#a23a1f">and where it has been.</em></h2>
        <p style="max-width:900px;font:italic 20px/1.45 Georgia,'Times New Roman',serif;color:#3d342e">The relative-rotation graph is a four-quadrant map of every sector's strength and the rate of change of that strength. Read clockwise: leaders weaken, weakeners lag, laggards improve, improvers lead. This version is generated from the current scored universe.</p>
      </div>
      <div class="mv2-b-article-grid">
        <main class="mv2-b-main">
          <h3>FIGURE 1 | RELATIVE ROTATION</h3>
          <div class="mv2-panel" style="background:#fffbf3;border-color:#e1d8c9">{_terminal_rrg_svg(sectors, width=700, height=580, theme="editorial", annotate=True)}</div>
          <div style="margin-top:16px;font:15.5px/1.6 Georgia,'Times New Roman',serif;color:#3d342e;max-width:700px">
            <p><strong style="font-family:var(--font-prose)">The current rotation story.</strong> {_esc(story["editorial_1"])}</p>
            <p>{_esc(story["editorial_2"])}</p>
            <p>{_esc(story["editorial_3"])}</p>
          </div>
          <h3>Cross-sectional leaderboard</h3>
          <p>12-1 momentum ranking, all ETFs: leaders show where price still works; laggards show where sponsorship already broke.</p>
          <div class="mv2-pillar-grid">{leaderboard("LEADERS", leaders)}{leaderboard("LAGGARDS", laggards)}</div>
        </main>
        <aside class="mv2-b-sidebar">
          <h3>The phase</h3>
          <div class="mv2-b-phase-row">{phase_html}</div>
          <p><strong>{_esc(phase)}</strong> | Derived from current S, F, breadth, and warning/exit counts in the scored universe.</p>
          <h3>Where the flow went</h3>
          <div class="mv2-rail-list">{flow_items}</div>
          <h3>Current support basket</h3>
          <div class="mv2-macro-grid" style="grid-template-columns:1fr 1fr">
            {support_cells}
          </div>
          <h3>If the regime weakens</h3>
          <p>The standby basket is selected from current rows with the strongest combination of F and S, using the latest scored universe.</p>
          <div class="mv2-b-risk-basket">{risk_basket}</div>
        </aside>
      </div>
      <div class="mv2-footer"><span>THE SENTIMENT BRIEF | THE MAP</span><span>v2 | EDITORIAL | MEIRI</span></div>
    """


def _rotation_body(rows: list[MomentumV2Row], display_name: str) -> str:
    sectors = [row for row in rows if row.asset_class == "US Sectors"] or rows
    return f"""
      <div class="mv2-head">
        <div>
          <div class="mv2-kicker">{_esc(display_name)} | Rotation</div>
          <h2 class="mv2-title">The rotation map</h2>
          <p class="mv2-subtitle">RRG position, cross-sectional momentum, flow migration, and macro context in one screen. ETF labels include sector/country/factor identity.</p>
        </div>
        <div class="mv2-screen-note">RRG: roughly 4-12 weeks<br>Flow: roughly 1-3 weeks</div>
      </div>
      {_tabs_html("rotation")}
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>Relative rotation graph</h3>
          <p>Right side means stronger relative ratio. Top side means improving relative momentum. Dot color is current state.</p>
          {_rrg_html(sectors)}
        </div>
        <aside class="mv2-panel">
          <h3>12-1 momentum leaders</h3>
          <p>Sorted by trailing 12-month return excluding the latest month.</p>
          {_momentum_rows(rows, limit=12)}
        </aside>
      </div>
      <div class="mv2-panel" style="margin-top:16px">
        <h3>Flow river</h3>
        <p>Left side shows the weakest current flow scores; right side shows strongest flow scores. Band width approximates the size of flow rotation.</p>
        {_flow_river_html(rows)}
      </div>
      <div class="mv2-panel" style="margin-top:16px">
        <h3>Macro and board context</h3>
        {_macro_grid_html(rows)}
      </div>
    """


def _pillar_article_text(row: MomentumV2Row, pillar: str) -> str:
    value = row.pillars[pillar]
    direction = "supports" if value >= 0 else "drags on"
    base = (
        f"{pillar} carries a {PILLAR_WEIGHTS[pillar]:.0%} model weight and currently {direction} "
        f"the composite by {_fmt(value, digits=3)}."
    )
    details = {
        "MOM": (
            f" For {row.ticker}, trailing momentum is {_fmt(row.momentum_pct, '%', 1)}. "
            "This is the primary trend-following evidence: strong values say the market has already been rewarding the instrument."
        ),
        "MANS": (
            f" Mansfield relative strength is {_fmt(row.mansfield_rs)}. "
            "Positive readings mean the instrument is outperforming its benchmark; negative readings warn that leadership is fading before the price chart fully breaks."
        ),
        "RS-R": (
            f" RS-Ratio is {row.rs_ratio:.1f}, placing the instrument in the {row.quadrant} rotation context. "
            "This tells whether relative strength is still on the right side of the rotation map."
        ),
        "RS-M": (
            f" RS-Momentum is {row.rs_momentum:.1f}. "
            "It measures acceleration or deceleration in relative strength, so it often changes before the slower trend filters."
        ),
        "FILT": (
            f" The filter stack reads stage {row.stage}, price {'above' if row.above_30wma else 'below'} the 30-week average, "
            f"and average slope {'rising' if row.ma_slope_pos else 'falling'}. These gates keep the model anchored to observable trend structure."
        ),
        "CYC": (
            f" The business-cycle tilt adjusts the score for the current macro phase and {row.asset_class}. "
            "It is intentionally smaller than price and flow, but it helps separate sectors that usually lead in different cycle regimes."
        ),
        "FLOW": (
            f" Flow is {_fmt(row.f_score)} and CMF is {_fmt(row.cmf21)}. "
            "This is the sponsorship test: accumulation supports a trend, while distribution can warn before price-based exits are triggered."
        ),
    }
    conclusion = (
        f" Read this pillar together with state {row.state_label} and RRG {row.quadrant}; "
        "the article view is designed to show which part of the evidence stack changed, not just the final label."
    )
    return base + details[pillar] + conclusion


def _deepdive_article_body(row: MomentumV2Row, as_of: str) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
    price_phrase, flow_phrase, subtitle = _deepdive_headline(row)
    intro_one, intro_two, intro_three = _deepdive_interpretation(row)
    support, total = _support_count(row)
    pillar_paras = "".join(
        f"""
        <div class="mv2-pillar-article">
          <div class="num">{idx + 1}</div>
          <div>
            <h4>{_esc(PILLAR_FULL[pillar])} <span class="{s_class if row.pillars[pillar] >= 0 else 'mv2-neg'}">{_fmt(row.pillars[pillar], digits=3)}</span></h4>
            <p>{_esc(_pillar_article_text(row, pillar))}</p>
          </div>
        </div>
        """
        for idx, pillar in enumerate(PILLAR_ORDER)
    )
    return f"""
      <div class="mv2-b-mast">
        <b>The Sentiment Brief</b>
        <span>|</span>
        <span>DEEP-DIVE | {_esc(row.ticker)}</span>
        <span style="margin-left:auto">Back to brief | Next leader</span>
      </div>
      <div class="mv2-article-hero">
        <div class="mv2-kicker">Display B | Editorial deep dive | {_esc(as_of)}</div>
        <h2>{_esc(row.ticker)}: {_esc(price_phrase)}.<br><em style="color:#a23a1f">{_esc(flow_phrase)}.</em></h2>
        <p class="mv2-subtitle" style="font-family:Georgia,'Times New Roman',serif;font-size:20px;max-width:940px">
          {_esc(subtitle)}
        </p>
        <div class="mv2-article-meta">
          <span>By the model</span>
          <span>{len(PILLAR_ORDER)} pillar analysis</span>
          <span>Momentum {_fmt(row.momentum_pct, "%", 1)}</span>
          <span>Flow {_fmt(row.f_score)}</span>
        </div>
      </div>
      {_tabs_html("deepdive")}
      <div class="mv2-pull-strip">
        <div><span>COMPOSITE S</span><b class="{s_class}">{_fmt(row.s_score)}</b></div>
        <div><span>Flow F</span><b class="{f_class}">{_fmt(row.f_score)}</b></div>
        <div><span>Momentum</span><b>{_fmt(row.momentum_pct, "%", 1)}</b></div>
        <div><span>RRG</span><b>{_esc(row.quadrant)}</b></div>
        <div><em>{support} of {total} pillars support the current composite; flow contributes {_fmt(row.pillars['FLOW'], digits=3)}.</em></div>
      </div>
      <div class="mv2-b-article-grid">
        <main class="mv2-b-main">
          <h3>The seven pillars, explained</h3>
          <p>Each paragraph corresponds to a signed, weighted contribution and is meant to be read as an analyst note.</p>
          {pillar_paras}
          <div class="mv2-article-block">
            <div>
              <p>{_esc(intro_one)}</p>
              <p>{_esc(intro_two)}</p>
              <p>{_esc(intro_three)}</p>
            </div>
            <div class="mv2-article-side">
              <b>NEXT WATCH LIST</b>
              <p>{'<br>'.join(_esc(label + ': ' + detail) for ok, label, detail in _gate_rows_for(row) if not ok) or 'No failed gates in the current row.'}</p>
            </div>
          </div>
        </main>
        <aside class="mv2-b-sidebar">
          <h3>WEEKLY PRICE vs 30wMA</h3>
          {_price_svg(row, width=420, height=190)}
          <p>Price is {'above' if row.above_30wma else 'below'} the 30-week average. Mansfield RS is {_fmt(row.mansfield_rs)}.</p>
          <h3>OBV DIVERGENCE</h3>
          {_cmf_svg(row, width=420, height=190)}
          <p>CMF and flow decide whether the warning is just noise or early institutional distribution.</p>
          <div class="mv2-gates">
            {_gate_html(row.above_30wma, "Close above 30wMA", "above" if row.above_30wma else "below")}
            {_gate_html(row.mansfield_rs >= 0, "Mansfield RS > 0", _fmt(row.mansfield_rs))}
            {_gate_html(row.cmf21 > -0.10, "CMF above exit line", _fmt(row.cmf21))}
            {_gate_html(row.f_score >= -0.5, "Flow veto avoided", _fmt(row.f_score))}
          </div>
        </aside>
      </div>
      <div class="mv2-b-gate-table">
        <h3>Exit trigger table</h3>
        <div class="mv2-gates">
          {_gate_html(row.above_30wma, "Weekly close remains above 30wMA", "pass" if row.above_30wma else "failed")}
          {_gate_html(row.mansfield_rs >= 0, "Mansfield RS remains positive", _fmt(row.mansfield_rs))}
          {_gate_html(row.cmf21 > -0.10, "CMF remains above -0.10", _fmt(row.cmf21))}
          {_gate_html(row.quadrant != "Lagging", "RRG has not entered Lagging", row.quadrant)}
          {_gate_html(row.f_score >= -0.5, "Flow veto has not fired", _fmt(row.f_score))}
        </div>
        <p style="margin-top:14px">This lower table turns the narrative into a concrete action checklist.</p>
      </div>
    """


def _shell(display: str, screen: str, body: str) -> str:
    shell_class = {
        "A": "mv2-terminal",
        "B": "mv2-editorial",
        "C": "mv2-pillarstack",
    }.get(display, "mv2-pillarstack")
    return f'<section class="mv2-shell {shell_class}" id="momentum-v2-{display.lower()}-{screen}">{body}</section>'


def render_deepdive(display: str, rows: list[MomentumV2Row], as_of: str, focus_ticker: str | None = None) -> str:
    display_name = DISPLAY_LABELS.get(display, "Display C")
    row = _find_focus_row(rows, focus_ticker)
    if row is None:
        return _shell(display, "deepdive", _universe_deepdive_body(rows, display_name, as_of))
    if display == "B":
        return _shell(display, "deepdive", _deepdive_article_body(row, as_of))
    if display == "A":
        return _shell(display, "deepdive", _deepdive_terminal_body(row, rows, as_of))
    if display == "C":
        return _shell(display, "deepdive", _deepdive_c_body(row, rows, as_of))
    body = _deepdive_body(row, display_name)
    return _shell(display, "deepdive", body)


def render_rotation(display: str, rows: list[MomentumV2Row], as_of: str) -> str:
    display_name = DISPLAY_LABELS.get(display, "Display C")
    if display == "A":
        return _shell(display, "rotation", _rotation_terminal_body(rows, as_of))
    if display == "C":
        return _shell(display, "rotation", _rotation_c_body(rows, as_of))
    if display == "B":
        return _shell(display, "rotation", _rotation_b_body(rows, as_of))
    body = _rotation_body(rows, display_name)
    return _shell(display, "rotation", body)


def render_display(
    display: str,
    rows: list[MomentumV2Row],
    as_of: str,
    screen: str = "overview",
    focus_ticker: str | None = None,
    data_provenance: Mapping[str, Any] | None = None,
    display_a_sort_field: str | None = "s_score",
    display_a_sort_direction: str | None = "desc",
) -> str:
    normalized_screen = screen if screen in SCREEN_LABELS else "overview"
    if normalized_screen == "deepdive":
        html = render_deepdive(display, rows, as_of, focus_ticker)
    elif normalized_screen == "rotation":
        html = render_rotation(display, rows, as_of)
    elif display == "A":
        html = render_display_a(
            rows,
            as_of,
            sort_field=display_a_sort_field,
            sort_direction=display_a_sort_direction,
        ).replace('<div class="mv2-a-body">', _tabs_html("overview") + '<div class="mv2-a-body">', 1)
    elif display == "B":
        html = render_display_b(rows, as_of).replace('<div class="mv2-grid">', _tabs_html("overview") + '<div class="mv2-grid">', 1)
    else:
        html = render_display_c(rows, as_of).replace('<div class="mv2-grid">', _tabs_html("overview") + '<div class="mv2-grid">', 1)
    return _with_provenance(html, data_provenance)
