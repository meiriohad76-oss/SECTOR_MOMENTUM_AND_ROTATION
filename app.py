"""Sentiment Board - Streamlit implementation of the Claude Design mockup.

Run with: streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.universe import ALL_TICKERS, UNIVERSE_BY_CLASS, BENCH
from src.data import fetch_ohlcv
from src.indicators import compute_all_indicators
from src.flow import compute_flow_signals, flow_composite_z, STUB_MODE
from src.macro import assess_regime
from src.scoring import compute_composite, apply_state_machine, recent_transitions
from src.visuals import (
    rrg_chart_dark,
    price_chart_with_30wma,
    cmf_chart,
    obv_chart,
    svg_sparkline,
    color_for_state,
    STATE_COLOR,
)


# =============================== page config =====================================

st.set_page_config(
    page_title="Sentiment Board",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================== load css ========================================

_STATIC = Path(__file__).resolve().parent / "static"
_CSS = (_STATIC / "style.css").read_text(encoding="utf-8")

# Streamlit-specific overrides on top of the design CSS
_EXTRA = """
/* hide streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.stApp { background: var(--bg) !important; }
section.main > div.block-container { padding-top: 0; padding-bottom: 0; max-width: 1480px; }
[data-testid="stSidebar"] { display: none !important; }
.element-container, .stMarkdown { font-family: var(--font-prose); }
/* keep plotly chart wrappers transparent */
.element-container .stPlotlyChart { background: transparent !important; }
"""

if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "klass" not in st.session_state:
    st.session_state.klass = "US Sectors"
if "drill_ticker" not in st.session_state:
    st.session_state.drill_ticker = "XLK"
if "table_open" not in st.session_state:
    st.session_state.table_open = True

st.markdown(
    f'<style>{_CSS}{_EXTRA}</style>'
    f'<script>document.documentElement.setAttribute("data-theme","{st.session_state.theme}");</script>',
    unsafe_allow_html=True,
)


# =============================== data load (cached) ==============================

@st.cache_data(ttl=3600, show_spinner=False)
def _load_data(period: str = "3y") -> dict[str, pd.DataFrame]:
    tickers = ALL_TICKERS + ["^TNX", "^IRX"]
    return fetch_ohlcv(tickers, period=period)


with st.spinner("Loading market data…"):
    ohlcv = _load_data("3y")

bench_ticker = BENCH["US"]
bil_ticker = BENCH["TBILL"]
if bench_ticker not in ohlcv or bil_ticker not in ohlcv:
    st.error("Missing benchmark/T-bill data. Try the refresh button.")
    st.stop()

with st.spinner("Computing indicators…"):
    indicators_df = compute_all_indicators(ohlcv, bench_ticker, bil_ticker)
    flow_df = compute_flow_signals(ohlcv)
    flow_z = flow_composite_z(flow_df)
    regime = assess_regime(ohlcv[bench_ticker], ohlcv.get("^TNX"), ohlcv.get("^IRX"))
    scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
    scored = apply_state_machine(scored)


# =============================== derive view-model ===============================

def _state_color_var(state: str) -> str:
    return {
        "STAGE_2_BULLISH":  "var(--st-stage2)",
        "HOLD":             "var(--st-hold)",
        "WARNING":          "var(--st-warn)",
        "EXIT":             "var(--st-exit)",
        "BEARISH_STAGE_4":  "var(--st-bear)",
        "STAGE_1_BASING":   "var(--st-basing)",
    }.get(state, "var(--muted)")


def _build_bluf(scored_df: pd.DataFrame):
    """Compute the BLUF action lists from current state."""
    exits = scored_df[scored_df["state"].isin(["EXIT", "BEARISH_STAGE_4"])]
    warns = scored_df[scored_df["state"] == "WARNING"]
    buys = scored_df[scored_df["state"] == "STAGE_2_BULLISH"]

    def _note_exit(row):
        bits = []
        if row.get("above_30wma") is False:
            bits.append("below 30wMA")
        if (row.get("cmf21") or 0) < -0.05:
            bits.append(f"CMF {row['cmf21']:+.2f}")
        if row.get("rrg_quadrant") == "Lagging":
            bits.append("RRG Lagging")
        if row.get("veto"):
            bits.append("flow veto")
        if not bits:
            bits = [f"S {row['S_score']:+.2f}"]
        return " · ".join(bits[:3])

    def _note_warn(row):
        bits = []
        if row.get("rrg_quadrant") == "Weakening":
            bits.append("RRG Weakening")
        if (row.get("breadth_50d") or 0) < 0.50:
            bits.append(f"breadth {row['breadth_50d']*100:.0f}%")
        if (row.get("cmf21") or 0) < 0:
            bits.append(f"CMF {row['cmf21']:+.2f}")
        if not bits:
            bits = [f"S {row['S_score']:+.2f}"]
        return " · ".join(bits[:3])

    def _note_buy(row):
        bits = [f"S {row['S_score']:+.2f}"]
        if (row.get("F_score") or 0) > 0:
            bits.append(f"F {row['F_score']:+.2f}")
        if (row.get("mom_12_1") or 0) > 0:
            bits.append(f"mom +{row['mom_12_1']*100:.0f}%")
        return " · ".join(bits[:3])

    def _pack(sub_df, note_fn, kind, label, eta, state):
        items = []
        sub_sorted = sub_df.sort_values("S_score", ascending=(kind == "exit"))
        for tkr, r in sub_sorted.head(4).iterrows():
            items.append({"t": tkr, "note": note_fn(r)})
        return {
            "kind": kind, "label": label, "eta": eta, "state": state, "tickers": items
        }

    return {
        "exits_count": len(exits),
        "warns_count": len(warns),
        "buys_count":  len(buys),
        "actions": [
            _pack(exits, _note_exit, "exit", "EXIT NOW",        "ON MONDAY OPEN", "EXIT"),
            _pack(warns, _note_warn, "warn", "WATCH CLOSELY",   "TIGHTEN STOPS",  "WARNING"),
            _pack(buys,  _note_buy,  "buy",  "BUY CANDIDATES",  "ENTER ON DIP",   "STAGE_2_BULLISH"),
        ],
    }


bluf = _build_bluf(scored)
transitions = recent_transitions(n=14)

# Phase index for the phase bar
PHASE_IDX = {"EARLY": 0, "MID": 1, "LATE": 2, "RECESSION": 3, "UNKNOWN": -1}
phase_idx = PHASE_IDX.get(regime.phase_hint, -1)


# =============================== render helpers ==================================

def render_header():
    now = datetime.now()
    last_update = now.strftime("%H:%M")
    as_of = now.strftime("%a %b %d %Y · %H:%M %Z").upper().strip(" ·").strip()
    next_refresh = "00:60:00"
    html = f"""
    <div class="app">
      <header class="header">
        <div class="brand">
          <span class="brand-mark"></span>
          SENTIMENT&nbsp;BOARD
        </div>
        <div class="meta">
          <span><span class="live-dot"></span>LIVE · {last_update}</span>
          <span class="sep">·</span>
          <span>{as_of}</span>
          <span class="sep">·</span>
          <span>next <span class="val">{next_refresh}</span></span>
        </div>
      </header>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_bluf():
    sub = (
        f"{bluf['exits_count']} exits · {bluf['warns_count']} warnings · "
        f"{bluf['buys_count']} candidates from {len(scored)} ETFs. "
        f"Risk regime is {('on' if regime.risk_on else 'off')} ({regime.phase_hint.lower()} cycle). "
        f"Click any action card → drill-down."
    )
    head_html = f"""
    <section class="section">
      <div class="bluf">
        <div class="bluf-head">
          <div class="bluf-eyebrow">
            <span class="pill-tiny">BLUF</span>
            <span>BOTTOM LINE · {datetime.now().strftime('%H:%M')}</span>
            <span class="stamp">{'RISK-ON' if regime.risk_on else 'RISK-OFF'}</span>
          </div>
        </div>
        <div class="bluf-headline">
          <span class="exit-num">{bluf['exits_count']}</span> EXIT
          <span class="sep">·</span>
          <span class="warn-num">{bluf['warns_count']}</span> WARNINGS
          <span class="sep">·</span>
          <span class="buy-num">{bluf['buys_count']}</span> NEW BUYS
        </div>
        <div class="bluf-sub">{sub}</div>
        <div class="bluf-actions">
    """
    cards = []
    for a in bluf["actions"]:
        items_html = "".join(
            f'<li><span class="t">{it["t"]}</span><span class="n">{it["note"]}</span></li>'
            for it in a["tickers"]
        ) or '<li><span class="t">—</span><span class="n">none</span></li>'
        card_html = f"""
        <div class="action-card {a['kind']}">
          <div class="action-head">
            <div class="action-label">{a['label']}</div>
            <div class="action-eta">{a['eta']}</div>
          </div>
          <span class="pill {a['state']}">{a['state'].replace('_', ' ')}</span>
          <ul class="action-list">{items_html}</ul>
        </div>
        """
        cards.append(card_html)
    st.markdown(head_html + "".join(cards) + "</div></div></section>", unsafe_allow_html=True)


def render_status():
    risk_on = regime.risk_on
    risk_label = "RISK-ON" if risk_on else "RISK-OFF"
    risk_tone = "up" if risk_on else "down"
    risk_dot = "var(--green)" if risk_on else "var(--red)"
    sub_risk = ("SPY > 10mo SMA" if risk_on else "SPY < 10mo SMA")

    # phase bar
    phase_bar_html = ""
    if phase_idx >= 0:
        bars = "".join(
            f'<div><div class="ph {"on" if i == phase_idx else ""}"></div>'
            f'<div class="lbl" style="margin-top:4px;color:{"var(--fg-dim)" if i == phase_idx else "var(--muted-2)"}">{lbl}</div></div>'
            for i, lbl in enumerate(["EARLY", "MID", "LATE", "RECESS"])
        )
        phase_bar_html = f'<div class="phase-bar">{bars}</div>'

    n_warn = bluf["warns_count"] + bluf["exits_count"]
    delta = '<span class="tile-delta">+2 24H</span>' if n_warn > 0 else ""

    yc_label = (
        "POSITIVE" if regime.yield_curve_positive
        else ("INVERTED" if regime.yield_curve_positive is False else "—")
    )

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Market state <span class="count">3 indicators</span></h2>
        <div class="right">UPDATED {datetime.now().strftime('%H:%M').upper()}</div>
      </div>
      <div class="status-row">

        <div class="tile">
          <div class="tile-label"><span>Risk regime</span></div>
          <div class="tile-value {risk_tone}">
            <span class="dot" style="background:{risk_dot}"></span>
            {risk_label}
          </div>
          <div class="tile-sub">{sub_risk} · curve {yc_label.lower()}</div>
        </div>

        <div class="tile">
          <div class="tile-label"><span>Cycle phase</span></div>
          <div class="tile-value">
            <span class="dot" style="background:var(--amber)"></span>
            {regime.phase_hint}
          </div>
          <div class="tile-sub">{regime.note}</div>
          {phase_bar_html}
        </div>

        <div class="tile">
          <div class="tile-label"><span>Active warnings</span>{delta}</div>
          <div class="tile-value warn">
            <span class="dot" style="background:var(--amber)"></span>
            {n_warn}
          </div>
          <div class="tile-sub">{bluf['exits_count']} exit · {bluf['warns_count']} warn</div>
        </div>

      </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_alerts():
    rows = ""
    for r in transitions[:8]:
        new_state = r.get("to", "")
        from_state = r.get("from", "—")
        dot_color = color_for_state(new_state)
        when = r.get("date", "")
        ticker = r.get("ticker", "")
        rows += f"""
        <div class="alert-row">
          <span class="dot" style="background:{dot_color}"></span>
          <span class="t">{ticker}</span>
          <span class="change">
            <span class="from">{from_state.replace('_', ' ')}</span>
            <span class="arrow">→</span>
            <span class="to">{new_state.replace('_', ' ')}</span>
          </span>
          <span class="when">{when}</span>
          <span class="chev">›</span>
        </div>
        """
    if not rows:
        rows = '<div class="alert-row"><span class="dot" style="background:var(--muted-2)"></span><span class="t">—</span><span class="change">no state changes yet — state machine starts logging on first run</span><span class="when"></span><span class="chev"></span></div>'

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Recent transitions <span class="count">{len(transitions)} in last 14d</span></h2>
        <div class="right">{datetime.now().strftime('%H:%M').upper()}</div>
      </div>
      <div class="alerts">{rows}</div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_picks():
    selected_picks = scored[scored["selected"]].sort_values(["class", "rank_in_class"])
    if selected_picks.empty:
        st.markdown(
            '<section class="section"><div class="section-head"><h2>Picks <span class="count">0 active</span></h2></div>'
            '<div class="alerts"><div class="alert-row"><span class="t">—</span>'
            '<span class="change">No picks meet the gates right now. System is defensive.</span></div></div></section>',
            unsafe_allow_html=True,
        )
        return

    cards_html = ""
    for tkr, p in selected_picks.iterrows():
        state = p["state"]
        s = p["S_score"]
        f = p["F_score"]
        mom = (p["mom_12_1"] or 0) * 100
        stage = p.get("stage") or "—"
        quad = (p.get("rrg_quadrant") or "—").upper()
        klass_lbl = p["class"]
        spark_color = "#26d65b" if mom >= 0 else "#ef4f4a"
        spark = svg_sparkline(ohlcv.get(tkr), spark_color) if tkr in ohlcv else ""
        mom_class = "pos" if mom >= 0 else "neg"
        s_class = "pos" if s >= 0 else "neg"
        f_class = "pos" if f >= 0 else "neg"

        cards_html += f"""
        <div class="pick {state}">
          <div class="pick-top">
            <div>
              <div class="pick-ticker">{tkr}</div>
              <div class="pick-class">{klass_lbl}</div>
            </div>
            <span class="pill {state}">{state.replace('_', ' ')}</span>
          </div>
          {spark}
          <div class="pick-metrics">
            <div class="m"><span class="k">S</span><span class="v {s_class}">{s:+.2f}</span></div>
            <div class="m"><span class="k">F</span><span class="v {f_class}">{f:+.2f}</span></div>
            <div class="m"><span class="k">MOM</span><span class="v {mom_class}">{mom:+.1f}%</span></div>
            <div class="m"><span class="k">STAGE</span><span class="v">{stage}</span></div>
          </div>
          <div class="pick-foot">
            <span>RRG</span>
            <span class="quad">{quad}</span>
          </div>
        </div>
        """

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Picks <span class="count">{len(selected_picks)} active</span></h2>
        <div class="right">SORTED BY COMPOSITE</div>
      </div>
      <div class="picks-grid">{cards_html}</div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_rrg():
    st.markdown('<section class="section"><div class="section-head">'
                f'<h2>Relative Rotation Graph <span class="count">{st.session_state.klass}</span></h2>'
                '<div class="right">CLICK DOT → DRILL-DOWN</div></div></section>',
                unsafe_allow_html=True)

    # class selector (Streamlit native buttons styled by our CSS)
    cls_list = list(UNIVERSE_BY_CLASS.keys()) + ["ALL"]
    cols = st.columns(len(cls_list))
    for c, cls in zip(cols, cls_list):
        if c.button(cls.upper(), key=f"cls_{cls}",
                    type="primary" if st.session_state.klass == cls else "secondary"):
            st.session_state.klass = cls
            st.rerun()

    # filter scored df
    if st.session_state.klass == "ALL":
        rrg_sub = scored.copy()
    else:
        rrg_sub = scored[scored["class"] == st.session_state.klass].copy()

    # quadrant counts
    quads = {"Leading": [], "Weakening": [], "Lagging": [], "Improving": []}
    for tkr, r in rrg_sub.iterrows():
        q = r.get("rrg_quadrant")
        if q in quads:
            quads[q].append(tkr)

    left_col, right_col = st.columns([2.2, 1])

    with left_col:
        if not rrg_sub.empty:
            st.plotly_chart(
                rrg_chart_dark(rrg_sub, title=""),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.info("No data for this class.")

    with right_col:
        for q, color_cls in [("Leading", "leading"), ("Weakening", "weakening"),
                              ("Lagging", "lagging"), ("Improving", "improving")]:
            tickers = quads[q]
            count = len(tickers)
            ticks = " · ".join(tickers) if tickers else "—"
            st.markdown(
                f'<div class="quad-card {color_cls}">'
                f'<div class="qlbl">{q}</div>'
                f'<div class="qcount">{count}</div>'
                f'<div class="qtick">{ticks}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_drill():
    sel = st.session_state.drill_ticker
    if sel not in ohlcv:
        return

    row = scored.loc[sel] if sel in scored.index else None
    if row is None:
        return

    state = row["state"]
    color = color_for_state(state)

    # picker
    pick_options = sorted(scored.index.tolist())
    new_sel = st.selectbox("DRILL-DOWN TICKER", pick_options,
                           index=pick_options.index(sel) if sel in pick_options else 0,
                           label_visibility="visible")
    if new_sel != sel:
        st.session_state.drill_ticker = new_sel
        st.rerun()

    # header tiles
    head_html = f"""
    <section class="section" id="drill">
      <div class="section-head">
        <h2>Per-ticker drill-down <span class="count">{sel} · {row['class']}</span></h2>
        <div class="right">{state.replace('_', ' ')}</div>
      </div>
      <div class="drill">
        <div class="drill-metrics">

          <div class="tile">
            <div class="tile-label"><span>Composite</span></div>
            <div class="tile-value {'up' if row['S_score'] >= 0 else 'down'}">{row['S_score']:+.3f}</div>
            <div class="tile-sub">rank {int(row.get('rank_in_class') or 0)} in {row['class']}</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span>Flow score</span></div>
            <div class="tile-value {'up' if row['F_score'] >= 0 else 'down'}">{row['F_score']:+.3f}</div>
            <div class="tile-sub">{'VETO' if row.get('veto') else 'OK'} · CMF {row.get('cmf21', 0) or 0:+.2f}</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span>State</span></div>
            <div class="tile-value" style="color:{color};font-size:1.1rem;">{state.replace('_', ' ')}</div>
            <div class="tile-sub">Stage {row.get('stage', '—')} · {(row.get('rrg_quadrant') or '—').upper()}</div>
          </div>

          <div class="tile">
            <div class="tile-label"><span>12-1 Momentum</span></div>
            <div class="tile-value {'up' if (row.get('mom_12_1') or 0) >= 0 else 'down'}">{(row.get('mom_12_1') or 0)*100:+.1f}%</div>
            <div class="tile-sub">Mansfield RS {row.get('mansfield_rs', 0) or 0:+.1f}</div>
          </div>

        </div>
      </div>
    </section>
    """
    st.markdown(head_html, unsafe_allow_html=True)

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(price_chart_with_30wma(ohlcv[sel], sel),
                        use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.plotly_chart(cmf_chart(ohlcv[sel], sel),
                        use_container_width=True, config={"displayModeBar": False})
    st.plotly_chart(obv_chart(ohlcv[sel], sel),
                    use_container_width=True, config={"displayModeBar": False})


def render_full_table():
    if st.button(("▾ HIDE" if st.session_state.table_open else "▸ SHOW") + "  FULL 7-PILLAR MATRIX",
                 key="table_toggle"):
        st.session_state.table_open = not st.session_state.table_open
        st.rerun()

    if not st.session_state.table_open:
        return

    rows_html = ""
    # 7 pillar booleans:
    # 1. mom_12_1 > 0
    # 2. faber == 1
    # 3. stage == 2 (Weinstein)
    # 4. antonacci == 1
    # 5. rrg_quadrant in {Leading, Improving}
    # 6. (cycle tilt — derive from class match, approximate)  → just use breadth > 50%
    # 7. F_score > 0 (institutional flow)

    for tkr, r in scored.sort_values("S_score", ascending=False).iterrows():
        p1 = (r.get("mom_12_1") or 0) > 0
        p2 = (r.get("faber") or 0) == 1
        p3 = (r.get("stage") or 0) == 2
        p4 = (r.get("antonacci") or 0) == 1
        p5 = (r.get("rrg_quadrant") in ("Leading", "Improving"))
        p6 = (r.get("breadth_50d") or 0) >= 0.5
        p7 = (r.get("F_score") or 0) > 0
        pillars = [p1, p2, p3, p4, p5, p6, p7]

        s = r["S_score"]
        f = r["F_score"]
        mom = (r.get("mom_12_1") or 0) * 100
        state = r["state"]

        p_tds = "".join(
            f'<td class="num"><span class="dot {"ok" if ok else "bad"}">{"●" if ok else "○"}</span></td>'
            for ok in pillars
        )

        rows_html += f"""
        <tr>
          <td class="t">{tkr}</td>
          <td style="color:var(--muted)">{r['class']}</td>
          <td><span class="pill {state}">{state.replace('_', ' ')}</span></td>
          {p_tds}
          <td class="num {'pos' if s >= 0 else 'neg'}">{s:+.2f}</td>
          <td class="num {'pos' if f >= 0 else 'neg'}">{f:+.2f}</td>
          <td class="num {'pos' if mom >= 0 else 'neg'}">{mom:+.1f}%</td>
        </tr>
        """

    pillars_th = "".join(
        f'<th class="num">{p}</th>' for p in
        ["MOM", "FABER", "STAGE2", "ANT", "RRG", "BREADTH", "FLOW"]
    )

    html = f"""
    <section class="section">
      <div class="section-head">
        <h2>Full 7-pillar matrix <span class="count">{len(scored)} of 67 ETFs</span></h2>
      </div>
      <div class="full-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Class</th>
              <th>State</th>
              {pillars_th}
              <th class="num">S</th>
              <th class="num">F</th>
              <th class="num">MOM</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_footer():
    html = f"""
    <div class="footer">
      <span>{len(scored)} ETFS · 7 PILLARS · STUB MODE {'ON' if STUB_MODE else 'OFF'} · CACHE TTL 60min</span>
      <span>v2.4.2 · {st.session_state.theme.upper()} · MEIRI / READ-ONLY</span>
    </div>
    </div>
    """  # closes <div class="app">
    st.markdown(html, unsafe_allow_html=True)


# =============================== compose page ====================================

render_header()
render_bluf()
render_status()
render_alerts()
render_picks()
render_rrg()
render_drill()
render_full_table()
render_footer()


# floating refresh / theme controls (mini fixed buttons, top-right)
ctrl_col1, ctrl_col2, _ = st.columns([1, 1, 18])
with ctrl_col1:
    if st.button("↻", key="refresh_btn", help="Refresh data"):
        _load_data.clear()
        st.rerun()
with ctrl_col2:
    icon = "☀" if st.session_state.theme == "dark" else "☾"
    if st.button(icon, key="theme_btn", help="Toggle theme"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()
