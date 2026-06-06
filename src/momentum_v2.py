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
  margin: 18px 0;
}
.mv2-shell, .mv2-shell * { box-sizing: border-box; letter-spacing: 0; }
.mv2-head { display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:16px; }
.mv2-kicker { font: 700 12px/1.2 var(--font-mono); color: var(--mv2-muted); text-transform: uppercase; }
.mv2-title { margin:4px 0 0; font: 700 24px/1.15 var(--font-prose); color: var(--mv2-ink); }
.mv2-subtitle { margin:6px 0 0; color: var(--mv2-muted); font-size:14px; line-height:1.45; max-width:820px; }
.mv2-screen-note { background: #fff7e7; border:1px solid #ead1a4; color:#4f3510; padding:10px 12px; border-radius:8px; min-width:260px; font-size:13px; line-height:1.35; }
.mv2-grid { display:grid; grid-template-columns: minmax(0, 1fr) 330px; gap:16px; align-items:start; }
.mv2-panel { background: var(--mv2-panel); border:1px solid var(--mv2-border); border-radius:8px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,.04); }
.mv2-panel h3 { margin:0 0 4px; font-size:16px; line-height:1.25; color:var(--mv2-ink); }
.mv2-panel p { margin:0 0 12px; color:var(--mv2-muted); font-size:13px; line-height:1.45; }
.mv2-legend { display:flex; flex-wrap:wrap; gap:8px 12px; margin:10px 0 12px; }
.mv2-chip { display:inline-flex; align-items:center; gap:6px; color:var(--mv2-muted); font:700 12px/1 var(--font-mono); }
.mv2-swatch { width:10px; height:10px; border-radius:2px; display:inline-block; }
.mv2-class { margin:18px 0 8px; color:var(--mv2-muted); font:700 12px/1.2 var(--font-mono); text-transform:uppercase; }
.mv2-row { display:grid; grid-template-columns: 150px minmax(220px,1fr) 82px 70px 76px; gap:10px; align-items:center; min-height:38px; border-top:1px solid #eee7dd; padding:8px 0; }
.mv2-row .t { color:var(--mv2-ink); font:800 14px/1.1 var(--font-mono); }
.mv2-row .t small { display:block; margin-top:3px; color:var(--mv2-muted); font:500 12px/1.2 var(--font-prose); white-space:normal; }
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
.mv2-story { border-top:1px solid #e1d8c9; padding:13px 0; display:grid; grid-template-columns:90px 1fr; gap:14px; }
.mv2-story b { font:800 15px/1.1 var(--font-mono); color:#1c1815; }
.mv2-story h4 { margin:0 0 5px; font:700 20px/1.18 Georgia, 'Times New Roman', serif; color:#1c1815; }
.mv2-story p { margin:0; font:16px/1.48 Georgia, 'Times New Roman', serif; color:#3d342e; }
.mv2-rail-list { display:grid; gap:10px; }
.mv2-rail-item { border-top:1px solid #eee7dd; padding-top:10px; }
.mv2-rail-item b { display:block; font:800 13px/1.2 var(--font-mono); color:var(--mv2-ink); }
.mv2-rail-item span { display:block; color:var(--mv2-muted); font-size:12px; line-height:1.35; margin-top:3px; }
@media (max-width: 1050px) {
  .mv2-grid { grid-template-columns: 1fr; }
  .mv2-head { flex-direction:column; }
  .mv2-row { grid-template-columns: 120px minmax(160px,1fr) 76px 58px 62px; }
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


def render_display_c(rows: list[MomentumV2Row], as_of: str) -> str:
    grouped = rows_by_class(rows)
    body = []
    for asset_class, items in grouped.items():
        bullish = sum(1 for item in items if item.state == "STAGE_2_BULLISH")
        body.append(f'<div class="mv2-class">{_esc(asset_class)} | {len(items)} | {bullish} bullish</div>')
        body.extend(_row_html(item) for item in items)
    leaders = sorted(rows, key=lambda item: item.s_score, reverse=True)[:8]
    warnings = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}][:8]
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
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>Seven-pillar heatmap</h3>
          <p>Sorted by S score inside each class. Hover a row for the current trigger story.</p>
          {_legend_html()}
          <div class="mv2-row mv2-muted"><b>Ticker</b><b>Weighted pillar composition</b><b>State</b><b class="mv2-num">S</b><b class="mv2-num">Mom</b></div>
          {"".join(body)}
        </div>
        <aside class="mv2-panel">
          <h3>What changed first</h3>
          <p>Risk items are shown with concrete reasons instead of bare arrows.</p>
          <div class="mv2-rail-list">
            {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)}</b><span>{_esc(" ".join(item.reasons))}</span></div>' for item in warnings)}
          </div>
          <h3 style="margin-top:18px">Top leaders</h3>
          <div class="mv2-rail-list">
            {"".join(f'<div class="mv2-rail-item"><b>{_esc(item.display_label)} {_fmt(item.s_score)}</b><span>{_esc(item.quadrant)} | F {_fmt(item.f_score)} | {_esc(item.state.replace("_", " "))}</span></div>' for item in leaders)}
          </div>
        </aside>
      </div>
    </section>
    """


def render_display_a(rows: list[MomentumV2Row], as_of: str) -> str:
    ordered = sorted(rows, key=lambda item: (item.asset_class, -item.s_score))
    body = "".join(_row_html(item) for item in ordered[:36])
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
    leaders = sorted(rows, key=lambda item: item.s_score, reverse=True)[:4]
    risks = [row for row in rows if row.state in {"WARNING", "EXIT", "BEARISH_STAGE_4"}][:6]
    stories = []
    for item in [*leaders[:2], *risks[:3]]:
        stories.append(
            f"""
            <article class="mv2-story">
              <div><b>{_esc(item.ticker)}</b><br>{_state_pill(item.state)}</div>
              <div>
                <h4>{_esc(item.identity)}: S {_fmt(item.s_score)} with flow {_fmt(item.f_score)}</h4>
                <p>{_esc(" ".join(item.reasons))} The largest positive and negative pillar forces should be read together before acting.</p>
              </div>
            </article>
            """
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
      <div class="mv2-grid">
        <div class="mv2-panel">
          <h3>Current stories</h3>
          {"".join(stories)}
        </div>
        <aside class="mv2-panel">
          <h3>By the numbers</h3>
          <div class="mv2-rail-list">
            <div class="mv2-rail-item"><b>{len(leaders)} leaders sampled</b><span>Top names by S score.</span></div>
            <div class="mv2-rail-item"><b>{len(risks)} warnings/exits sampled</b><span>Names with active deterioration states.</span></div>
            <div class="mv2-rail-item"><b>7 pillars</b><span>{_esc(", ".join(PILLAR_ORDER))}</span></div>
          </div>
        </aside>
      </div>
    </section>
    """


def render_display(display: str, rows: list[MomentumV2Row], as_of: str) -> str:
    if display == "A":
        return render_display_a(rows, as_of)
    if display == "B":
        return render_display_b(rows, as_of)
    return render_display_c(rows, as_of)
