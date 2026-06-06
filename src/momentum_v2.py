"""Momentum v2 view-model and HTML helpers.

The UX handoff is a React prototype; this module adapts its three display
directions into the existing Streamlit app while keeping live dashboard data as
the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable, Mapping

import pandas as pd

from .macro import cycle_tilt
from .scoring import BINARY_FILTER_COUNT, COMPOSITE_WEIGHTS
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


def rows_by_class(rows: Iterable[MomentumV2Row]) -> dict[str, list[MomentumV2Row]]:
    grouped: dict[str, list[MomentumV2Row]] = {}
    for row in rows:
        grouped.setdefault(row.asset_class, []).append(row)
    for asset_class in grouped:
        grouped[asset_class].sort(key=lambda item: item.s_score, reverse=True)
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
.mv2-pull-strip { background:#1c1815; color:#f6efe2; display:grid; grid-template-columns:repeat(4,1fr); gap:1px; margin:18px 0; }
.mv2-pull-strip div { padding:14px 18px; border-right:1px solid #3d342e; }
.mv2-pull-strip span { display:block; color:#c4b5a0; font:800 10px/1 var(--font-mono); text-transform:uppercase; }
.mv2-pull-strip b { display:block; margin-top:5px; font:900 26px/1 var(--font-mono); color:#f6efe2; }
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
@media (max-width: 1050px) {
  .mv2-grid { grid-template-columns: 1fr; }
  .mv2-head { flex-direction:column; }
  .mv2-weather, .mv2-b-hero { grid-template-columns:1fr; }
  .mv2-row { grid-template-columns: 120px minmax(160px,1fr) 76px 58px 62px; }
  .mv2-metric-deck, .mv2-macro-grid { grid-template-columns:1fr 1fr; }
  .mv2-chart-grid, .mv2-chart-grid.tight, .mv2-article-block, .mv2-pillar-grid, .mv2-a-hero-grid, .mv2-a-pillars, .mv2-b-article-grid { grid-template-columns:1fr; }
}
"""


def _esc(value: object) -> str:
    return escape(str(value), quote=True)


def _fmt(value: float, suffix: str = "", digits: int = 2) -> str:
    return f"{value:+.{digits}f}{suffix}"


def _state_pill(state: str) -> str:
    color = STATE_COLORS_LIGHT.get(state, "#777")
    return f'<span class="mv2-state" style="background:{color}">{_esc(STATE_LABELS.get(state, state))}</span>'


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


def _row_html(row: MomentumV2Row) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
    mom_class = "mv2-pos" if row.momentum_pct >= 0 else "mv2-neg"
    reason = " ".join(row.reasons)
    return f"""
    <div class="mv2-row" title="{_esc(reason)}">
      <div class="t">{_esc(row.ticker)}<small>{_esc(row.identity)}</small></div>
      {_pillar_bar(row)}
      <div>{_state_pill(row.state)}</div>
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


def render_display_c(rows: list[MomentumV2Row], as_of: str) -> str:
    grouped = rows_by_class(rows)
    body = []
    for asset_class, items in grouped.items():
        bullish = sum(1 for item in items if item.state == "STAGE_2_BULLISH")
        body.append(f'<div class="mv2-class">{_esc(asset_class)} | {len(items)} | {bullish} bullish</div>')
        body.extend(_row_html(item) for item in items)
    leaders = sorted(rows, key=lambda item: item.s_score, reverse=True)[:8]
    warnings = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}][:8]
    bullish = [row for row in rows if row.state == "STAGE_2_BULLISH"]
    exits = [row for row in rows if row.state in {"EXIT", "BEARISH_STAGE_4"}]
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    avg_s = sum(row.s_score for row in rows) / max(len(rows), 1)
    return f"""
    <section class="mv2-shell mv2-pillarstack" id="momentum-v2-c">
      <div class="mv2-head">
        <div>
          <div class="mv2-kicker">Display C | Pillar Stack | live data</div>
          <h2 class="mv2-title">The composite, dissected</h2>
          <p class="mv2-subtitle">Each row shows the seven weighted forces behind the score. Segments to the right of the midline are bullish; segments to the left are bearish. The label always includes the ETF sector, country, factor, theme, or company identity.</p>
        </div>
        <div class="mv2-screen-note">As of {_esc(as_of)}<br>Best default view for novice explanation and score transparency.</div>
      </div>
      <div class="mv2-weather">
        <div>
          <div class="mv2-kicker">Today | dashboard weather</div>
          <h3>{len(bullish)} bullish leaders. {len(warnings)} risk names.</h3>
          <p>The top strip summarizes the whole board before the user scans individual ETF rows.</p>
        </div>
        {_weather_item("Regime", "RISK-ON" if avg_s >= 0 else "RISK-OFF", f"average S {_fmt(avg_s)}", "mv2-pos" if avg_s >= 0 else "mv2-neg")}
        {_weather_item("Warnings", str(len(warnings)), f"{len(exits)} exit/bearish", "mv2-neg" if warnings else "mv2-pos")}
        {_weather_item("Breadth", f"{breadth:.0%}", "above 50d moving average", "mv2-pos" if breadth >= 0.5 else "mv2-neg")}
        {_weather_item("Universe", str(len(rows)), f"{len(grouped)} groups tracked")}
        {_weather_item("Leaders", str(len(bullish)), "Stage 2 bullish", "mv2-pos")}
      </div>
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>Seven-pillar heatmap</h3>
          <p>Sorted by S score inside each class. Hover a row for the current trigger story.</p>
          {_legend_html()}
          <div class="mv2-row mv2-muted"><b>Ticker</b><b>Weighted pillar composition</b><b>State</b><b class="mv2-num">S</b><b class="mv2-num">Mom</b></div>
          {"".join(body)}
        </div>
        <aside class="mv2-rail-stack">
          <div class="mv2-panel">
            <h3>What changed first</h3>
            <p>Risk items are shown with concrete reasons instead of bare arrows.</p>
            <div class="mv2-rail-list">
              {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)}</b><span>{_esc(" ".join(item.reasons))}</span></div>' for item in warnings[:6])}
            </div>
          </div>
          <div class="mv2-panel">
            <h3>Top leaders</h3>
            <div class="mv2-rail-list">
              {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)} {_fmt(item.s_score)}</b><span>{_esc(item.quadrant)} | F {_fmt(item.f_score)} | {_esc(item.state.replace("_", " "))}</span></div>' for item in leaders[:6])}
            </div>
          </div>
          <div class="mv2-panel">
            <h3>Board summary</h3>
            <div class="mv2-rail-list">
              <div class="mv2-rail-item"><b>{len(rows)} instruments</b><span>{len(grouped)} asset groups with full seven-pillar rows.</span></div>
              <div class="mv2-rail-item"><b>{len(bullish)} passing every bullish gate</b><span>These are the cleanest candidates before position sizing and risk review.</span></div>
              <div class="mv2-rail-item"><b>{len(exits)} exits or bearish Stage 4</b><span>These should be reviewed before new adds.</span></div>
            </div>
          </div>
        </aside>
      </div>
    </section>
    """


def render_display_a(rows: list[MomentumV2Row], as_of: str) -> str:
    ordered = sorted(rows, key=lambda item: (item.asset_class, -item.s_score))
    body = "".join(_row_html(item) for item in ordered)
    exits = [row for row in rows if row.state in {"EXIT", "BEARISH_STAGE_4"}]
    return f"""
    <section class="mv2-shell mv2-terminal" id="momentum-v2-a">
      <div class="mv2-head">
        <div>
          <div class="mv2-kicker">Display A | Terminal | dense scan</div>
          <h2 class="mv2-title">Momentum terminal board</h2>
          <p class="mv2-subtitle">Dense power-user scan of state, S score, momentum, and pillar bars. Use this when you need quick triage across the whole board.</p>
        </div>
        <div class="mv2-screen-note">As of {_esc(as_of)}<br>{len(exits)} exit/bearish names currently require attention.</div>
      </div>
      <div class="mv2-panel">
        {_legend_html()}
        <div class="mv2-row mv2-muted"><b>Ticker</b><b>Pillars</b><b>State</b><b class="mv2-num">S</b><b class="mv2-num">Mom</b></div>
        {body}
      </div>
    </section>
    """


def render_display_b(rows: list[MomentumV2Row], as_of: str) -> str:
    leaders = sorted(rows, key=lambda item: item.s_score, reverse=True)[:8]
    risks = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}][:10]
    bullish = [row for row in rows if row.state == "STAGE_2_BULLISH"]
    exits = [row for row in rows if row.state in {"EXIT", "BEARISH_STAGE_4"}]
    breadth = sum(row.breadth_50d for row in rows) / max(len(rows), 1)
    avg_flow = sum(row.f_score for row in rows) / max(len(rows), 1)
    stories = []
    for item in [*leaders[:3], *risks[:6]]:
        pos, pos_value, neg, neg_value = _largest_pillars(item)
        stories.append(
            f"""
            <article class="mv2-story">
              <div><b>{_esc(item.ticker)}</b><br>{_state_pill(item.state)}</div>
              <div>
                <h4>{_esc(item.identity)}: S {_fmt(item.s_score)} with flow {_fmt(item.f_score)}</h4>
                <p>{_esc(" ".join(item.reasons))} Largest support is {_esc(pos)} {_fmt(pos_value, digits=3)}; largest drag is {_esc(neg)} {_fmt(neg_value, digits=3)}.</p>
              </div>
            </article>
            """
        )
    tape = "".join(
        f'<span><b>{_esc(item.ticker)}</b> {_fmt(item.s_score)} <i class="{"mv2-pos" if item.s_score >= 0 else "mv2-neg"}">{_esc(item.state.replace("_", " "))}</i></span>'
        for item in [*leaders[:4], *risks[:4]]
    )
    return f"""
    <section class="mv2-shell mv2-editorial" id="momentum-v2-b">
      <div class="mv2-head">
        <div>
          <div class="mv2-kicker">Display B | Editorial | daily brief</div>
          <h2 class="mv2-title">The Sentiment Brief</h2>
          <p class="mv2-subtitle">Plain-English market briefing generated from the same seven-pillar model. This view is for explaining why the dashboard is leaning bullish, cautious, or bearish.</p>
        </div>
        <div class="mv2-screen-note">Edition generated from live dashboard run<br>{_esc(as_of)}</div>
      </div>
      <div class="mv2-tape"><span>Live</span>{tape}<span>Updated {_esc(as_of)}</span></div>
      <div class="mv2-b-hero">
        <div>
          <div class="mv2-kicker">Today's read | seven-pillar model</div>
          <h3>{len(exits)} exits. {len(bullish)} bullish leaders.</h3>
          <p>The board is being read as an editorial brief: trend tells us what has worked, flow and rotation tell us where sponsorship is moving next, and the state machine turns that evidence into action language.</p>
          <div class="mv2-kicker" style="margin-top:16px">By the model | {len(rows)} instruments | 7 pillars</div>
        </div>
        <div class="mv2-b-numbers">
          <div class="mv2-b-num"><span>New/bullish basket</span><b class="mv2-pos">{len(bullish)}</b></div>
          <div class="mv2-b-num"><span>Active warnings</span><b class="mv2-neg">{len(risks)}</b></div>
          <div class="mv2-b-num"><span>Exit/bearish states</span><b class="mv2-neg">{len(exits)}</b></div>
          <div class="mv2-b-num"><span>Breadth above 50dMA</span><b class="{"mv2-pos" if breadth >= 0.5 else "mv2-neg"}">{breadth:.0%}</b></div>
          <div class="mv2-b-num"><span>Average flow score</span><b class="{"mv2-pos" if avg_flow >= 0 else "mv2-neg"}">{_fmt(avg_flow)}</b></div>
          <div class="mv2-b-num"><span>Top leader</span><b>{_esc(leaders[0].ticker if leaders else "N/A")}</b></div>
        </div>
      </div>
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>This week's transitions</h3>
          <p>Each story uses the same data as the heatmap, but explains it like an analyst note.</p>
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
        <aside class="mv2-panel">
          <h3>By the numbers</h3>
          <div class="mv2-rail-list">
            <div class="mv2-rail-item"><b>{len(leaders)} leaders sampled</b><span>Top names by S score.</span></div>
            <div class="mv2-rail-item"><b>{len(risks)} warnings/exits sampled</b><span>Names with active deterioration states.</span></div>
            <div class="mv2-rail-item"><b>7 pillars</b><span>{_esc(", ".join(PILLAR_ORDER))}</span></div>
          </div>
          <h3 style="margin-top:18px">Bullish cohort</h3>
          <div class="mv2-rail-list">
            {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)}</b><span>S {_fmt(item.s_score)} | F {_fmt(item.f_score)} | {item.quadrant}</span></div>' for item in bullish[:6])}
          </div>
        </aside>
      </div>
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


def _metric_card(label: str, value: str, tone_class: str = "") -> str:
    return f'<div class="mv2-metric"><span>{_esc(label)}</span><b class="{tone_class}">{_esc(value)}</b></div>'


def _gate_html(ok: bool, label: str, detail: str) -> str:
    color = "var(--mv2-green)" if ok else "var(--mv2-red)"
    mark = "Y" if ok else "!"
    return (
        f'<div class="mv2-gate"><i class="mv2-gate-mark" style="background:{color}">{mark}</i>'
        f'<b>{_esc(label)}</b><span>{_esc(detail)}</span></div>'
    )


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


def _deepdive_terminal_body(row: MomentumV2Row, as_of: str) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
    mom_class = "mv2-pos" if row.momentum_pct >= 0 else "mv2-neg"
    gates = [
        (row.quadrant not in {"Weakening", "Lagging"}, "RRG leadership intact", row.quadrant),
        (row.breadth_50d >= 0.5, "Breadth above 50% gate", f"{row.breadth_50d:.0%}"),
        (row.cmf21 >= 0, "CMF stayed above zero", _fmt(row.cmf21)),
        (row.f_score >= -0.5, "Flow veto avoided", _fmt(row.f_score)),
        (row.above_30wma, "Weekly close above 30wMA", "above" if row.above_30wma else "below"),
        (row.mansfield_rs >= 0, "Mansfield RS positive", _fmt(row.mansfield_rs)),
    ]
    return f"""
      <div class="mv2-head" style="border-bottom:1px solid var(--mv2-border);padding-bottom:12px">
        <div>
          <div class="mv2-kicker">A | Terminal | Deep dive | {_esc(as_of)}</div>
          <h2 class="mv2-title">{_esc(row.ticker)} | {_esc(row.identity)}</h2>
          <p class="mv2-subtitle">{_esc(row.asset_class)} | last model state {_esc(row.state.replace("_", " "))} | RRG {_esc(row.quadrant)}</p>
        </div>
        <div class="mv2-screen-note">{_state_pill(row.state)}<br>S {_fmt(row.s_score)} | F {_fmt(row.f_score)}</div>
      </div>
      {_tabs_html("deepdive")}
      <div class="mv2-a-hero">
        <div class="mv2-a-hero-grid">
          <div>
            <div class="mv2-kicker">COMPOSITE FORWARD OUTLOOK</div>
            <div class="mv2-a-score"><b class="{s_class}">{_fmt(row.s_score)}</b><span>S-score | {_esc(row.asset_class)}</span></div>
            <p class="mv2-a-prose">
              <strong>{_esc(row.ticker)}</strong> is being classified by seven signed evidence pillars.
              Momentum is {_fmt(row.momentum_pct, "%", 1)}, flow is {_fmt(row.f_score)}, Mansfield RS is {_fmt(row.mansfield_rs)}, and CMF is {_fmt(row.cmf21)}.
              The handoff view makes the disagreement visible first: price/trend gates can still be constructive while flow or rotation starts to deteriorate.
            </p>
            {_composite_bar_html(row)}
            {_pillar_detail_grid(row)}
          </div>
          <aside class="mv2-panel">
            <h3>{_esc(row.state.replace("_", " "))} state gates</h3>
            <p>State changes are driven by concrete gates. Failed or warning gates are marked with an exclamation point.</p>
            <div class="mv2-gates">{"".join(_gate_html(*gate) for gate in gates)}</div>
            <p style="margin-top:12px"><b>Nearest escalation:</b> watch CMF below -0.10, RRG Lagging, or a weekly close below the 30-week average.</p>
          </aside>
        </div>
      </div>
      <div class="mv2-chart-grid tight" style="padding-top:16px">
        <div class="mv2-panel">
          <h3>Weekly price vs 30-week SMA | Weinstein</h3>
          {_price_svg(row, width=820, height=245)}
          <p>{_esc(row.ticker)} is {'above' if row.above_30wma else 'below'} the 30-week average and the average slope is {'positive' if row.ma_slope_pos else 'negative'}. This is the primary Stage 2 versus exit line.</p>
        </div>
        <div class="mv2-panel">
          <h3>OBV divergence</h3>
          {_obv_svg(row, width=420, height=190)}
          <p>OBV shows whether volume confirms price. A higher price high with weaker OBV is an early sponsorship warning.</p>
        </div>
        <div class="mv2-panel">
          <h3>Chaikin Money Flow | 21D</h3>
          {_cmf_svg(row, width=820, height=205)}
          <p>CMF is {_fmt(row.cmf21)}. Values below zero show distribution; values below -0.10 are treated as a more serious exit gate.</p>
        </div>
        <div class="mv2-panel">
          <h3>Peer rank | S-score context</h3>
          <div class="mv2-metric-deck" style="grid-template-columns:1fr 1fr;margin-top:0">
            {_metric_card("S-score", _fmt(row.s_score), s_class)}
            {_metric_card("F-score", _fmt(row.f_score), f_class)}
            {_metric_card("Momentum", _fmt(row.momentum_pct, "%", 1), mom_class)}
            {_metric_card("RRG", row.quadrant)}
          </div>
          <p>The peer panel summarizes where the ticker sits before the user switches back to the full matrix.</p>
        </div>
      </div>
      <div class="mv2-footer"><span>{_esc(row.ticker)} | {_esc(row.identity)} | 7 pillars</span><span>Momentum v2 | Terminal deep dive</span></div>
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
          <p class="mv2-subtitle"><b>{_esc(row.state.replace("_", " "))}</b>. {_esc(" ".join(row.reasons))}</p>
        </div>
        <div class="mv2-screen-note">Ticker-specific report<br>{_state_pill(row.state)}</div>
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
          <p>The handoff pairs every ticker story with trend evidence. This panel reserves the same visual weight and explains whether price still confirms the state.</p>
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
        f" Read this pillar together with state {row.state.replace('_', ' ')} and RRG {row.quadrant}; "
        "the article view is designed to show which part of the evidence stack changed, not just the final label."
    )
    return base + details[pillar] + conclusion


def _deepdive_article_body(row: MomentumV2Row, as_of: str) -> str:
    s_class = "mv2-pos" if row.s_score >= 0 else "mv2-neg"
    f_class = "mv2-pos" if row.f_score >= 0 else "mv2-neg"
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
        <span>Deep-dive | {_esc(row.ticker)}</span>
        <span style="margin-left:auto">Back to brief | Next leader</span>
      </div>
      <div class="mv2-article-hero">
        <div class="mv2-kicker">Display B | Editorial deep dive | {_esc(as_of)}</div>
        <h2>{_esc(row.ticker)}: price says fine.<br><em style="color:#a23a1f">Flow says watch carefully.</em></h2>
        <p class="mv2-subtitle" style="font-family:Georgia,'Times New Roman',serif;font-size:20px;max-width:940px">
          {_esc(row.identity)} is a model article, not a card. It explains how the seven forces combine, why the current state exists, and which exit trigger is nearest.
        </p>
      </div>
      {_tabs_html("deepdive")}
      <div class="mv2-pull-strip">
        <div><span>Composite S</span><b class="{s_class}">{_fmt(row.s_score)}</b></div>
        <div><span>Flow F</span><b class="{f_class}">{_fmt(row.f_score)}</b></div>
        <div><span>Momentum</span><b>{_fmt(row.momentum_pct, "%", 1)}</b></div>
        <div><span>RRG</span><b>{_esc(row.quadrant)}</b></div>
      </div>
      <div class="mv2-b-article-grid">
        <main class="mv2-b-main">
          <h3>The seven pillars, explained</h3>
          <p>Each paragraph corresponds to a signed, weighted contribution. The handoff's editorial display is meant to be read as an analyst note.</p>
          {pillar_paras}
          <div class="mv2-article-block">
            <div>
              <p>The practical interpretation is deliberately conservative. A warning state does not say the instrument must immediately fall; it says the evidence stack has stopped agreeing. In this case the largest disagreement is between price trend and sponsorship. Price remains above the long moving average, but flow and relative rotation are no longer confirming the advance.</p>
              <p>The dashboard therefore treats the position as a hold-with-conditions rather than a fresh buy. The nearest escalation gate is a weekly close below the 30-week moving average, followed by a deeper CMF break below -0.10 or a sustained Mansfield RS failure. If those gates fire, the model moves from warning to exit without waiting for every pillar to turn negative.</p>
              <p>For a novice reader, the important idea is simple: the score is not one magic number. It is seven forces. The article view is designed to show which forces still help, which forces hurt, and which one changed most recently.</p>
            </div>
            <div class="mv2-article-side">
              <b>NEXT WATCH LIST</b>
              <p>Weekly close vs 30wMA<br>CMF relative to -0.10<br>Mansfield RS crossing zero<br>RRG Weakening to Lagging<br>Flow contribution below veto line</p>
            </div>
          </div>
        </main>
        <aside class="mv2-b-sidebar">
          <h3>Charts and gates</h3>
          {_price_svg(row, width=420, height=190)}
          <p>Price is {'above' if row.above_30wma else 'below'} the 30-week average. Mansfield RS is {_fmt(row.mansfield_rs)}.</p>
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
        <p style="margin-top:14px">This lower table mirrors the handoff article's role: it turns the narrative into a concrete action checklist.</p>
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
    row = _focus_row(rows, focus_ticker)
    display_name = DISPLAY_LABELS.get(display, "Display C")
    if display == "B":
        return _shell(display, "deepdive", _deepdive_article_body(row, as_of))
    if display == "A":
        return _shell(display, "deepdive", _deepdive_terminal_body(row, as_of))
    body = _deepdive_body(row, display_name)
    return _shell(display, "deepdive", body)


def render_rotation(display: str, rows: list[MomentumV2Row], as_of: str) -> str:
    display_name = DISPLAY_LABELS.get(display, "Display C")
    body = _rotation_body(rows, display_name)
    if display == "B":
        body = body.replace("The rotation map", "The Rotation Column")
    if display == "A":
        body = body.replace("The rotation map", "RRG / FLOW TERMINAL")
    return _shell(display, "rotation", body)


def render_display(
    display: str,
    rows: list[MomentumV2Row],
    as_of: str,
    screen: str = "overview",
    focus_ticker: str | None = None,
) -> str:
    normalized_screen = screen if screen in SCREEN_LABELS else "overview"
    if normalized_screen == "deepdive":
        return render_deepdive(display, rows, as_of, focus_ticker)
    if normalized_screen == "rotation":
        return render_rotation(display, rows, as_of)
    if display == "A":
        return render_display_a(rows, as_of).replace('<div class="mv2-panel">', _tabs_html("overview") + '<div class="mv2-panel">', 1)
    if display == "B":
        return render_display_b(rows, as_of).replace('<div class="mv2-grid">', _tabs_html("overview") + '<div class="mv2-grid">', 1)
    return render_display_c(rows, as_of).replace('<div class="mv2-grid">', _tabs_html("overview") + '<div class="mv2-grid">', 1)
