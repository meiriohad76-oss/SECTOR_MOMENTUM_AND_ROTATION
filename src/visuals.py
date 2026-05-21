"""Plotly visualizations for the dashboard."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .data import close_price


# ---- color helpers ---------------------------------------------------------------

STATE_COLOR = {
    "STAGE_2_BULLISH":  "#1A8A4E",
    "HOLD":             "#5C9DCB",
    "WARNING":          "#E2A53A",
    "EXIT":             "#D5562C",
    "BEARISH_STAGE_4":  "#A21E2C",
    "STAGE_1_BASING":   "#9E9E9E",
}


def color_for_state(s: str) -> str:
    return STATE_COLOR.get(s, "#777")


# ---- RRG quadrant chart ----------------------------------------------------------

def rrg_chart(df: pd.DataFrame, title: str = "Relative Rotation Graph") -> go.Figure:
    """Plot a single-snapshot RRG. ``df`` must have rs_ratio, rs_momentum, state."""
    sub = df.dropna(subset=["rs_ratio", "rs_momentum"]).copy()
    fig = go.Figure()
    # quadrant background shading
    fig.add_shape(type="rect", x0=100, x1=120, y0=100, y1=120, fillcolor="#D6F5E0", line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=100, x1=120, y0=80,  y1=100, fillcolor="#FFF0CC", line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=80,  x1=100, y0=80,  y1=100, fillcolor="#FFD6D6", line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=80,  x1=100, y0=100, y1=120, fillcolor="#DCE7FA", line=dict(width=0), layer="below")
    # axes
    fig.add_hline(y=100, line=dict(color="#999", width=1))
    fig.add_vline(x=100, line=dict(color="#999", width=1))
    # points
    fig.add_trace(go.Scatter(
        x=sub["rs_ratio"],
        y=sub["rs_momentum"],
        mode="markers+text",
        text=sub.index,
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(
            size=12,
            color=[color_for_state(s) for s in sub.get("state", pd.Series([""] * len(sub), index=sub.index))],
            line=dict(width=1, color="#333"),
        ),
        hovertemplate="<b>%{text}</b><br>RS-Ratio: %{x:.1f}<br>RS-Mom: %{y:.1f}<extra></extra>",
    ))
    # quadrant labels
    fig.add_annotation(x=118, y=118, text="Leading", showarrow=False, font=dict(size=11, color="#1A8A4E"))
    fig.add_annotation(x=118, y=82,  text="Weakening", showarrow=False, font=dict(size=11, color="#B57E14"))
    fig.add_annotation(x=82,  y=82,  text="Lagging", showarrow=False, font=dict(size=11, color="#A21E2C"))
    fig.add_annotation(x=82,  y=118, text="Improving", showarrow=False, font=dict(size=11, color="#3B6FB6"))
    fig.update_layout(
        title=title,
        xaxis=dict(title="JdK RS-Ratio", range=[80, 120]),
        yaxis=dict(title="JdK RS-Momentum", range=[80, 120]),
        height=520,
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="#FAFAFA",
    )
    return fig


# ---- Cross-sectional momentum bar -----------------------------------------------

def momentum_bar(df: pd.DataFrame, title: str = "12-1 Cross-sectional Momentum") -> go.Figure:
    sub = df.dropna(subset=["mom_12_1"]).copy()
    sub = sub.sort_values("mom_12_1", ascending=True)
    colors = ["#1A8A4E" if v >= 0 else "#D5562C" for v in sub["mom_12_1"]]
    fig = go.Figure(go.Bar(
        x=sub["mom_12_1"] * 100,
        y=sub.index,
        orientation="h",
        marker_color=colors,
        text=[f"{v*100:+.1f}%" for v in sub["mom_12_1"]],
        textposition="outside",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="12-month return (skipping last month), %",
        yaxis_title="",
        height=max(420, 22 * len(sub)),
        margin=dict(l=80, r=40, t=60, b=40),
        plot_bgcolor="#FAFAFA",
    )
    return fig


# ---- Price + 30wMA chart for the drill-down -------------------------------------

def price_chart_with_30wma(df_daily: pd.DataFrame, ticker: str) -> go.Figure:
    weekly = df_daily.resample("W-FRI").agg({"close": "last"})
    weekly["sma30"] = weekly["close"].rolling(30).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=weekly.index, y=weekly["close"], name="Close (weekly)", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=weekly.index, y=weekly["sma30"], name="30-week SMA", line=dict(width=1.5, dash="dash")))
    fig.update_layout(
        title=f"{ticker} — weekly price vs 30-week SMA",
        height=400,
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="#FAFAFA",
        legend=dict(orientation="h", yanchor="top", y=-0.1),
    )
    return fig


def cmf_chart(df_daily: pd.DataFrame, ticker: str) -> go.Figure:
    high, low, close, vol = df_daily["high"], df_daily["low"], df_daily["close"], df_daily["volume"]
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    mfv = (mfm * vol).fillna(0)
    cmf = mfv.rolling(21).sum() / vol.rolling(21).sum().replace(0, np.nan)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cmf.index, y=cmf, name="CMF(21)", line=dict(width=1.5)))
    fig.add_hline(y=0.10, line=dict(color="#1A8A4E", dash="dot"))
    fig.add_hline(y=0, line=dict(color="#999"))
    fig.add_hline(y=-0.10, line=dict(color="#D5562C", dash="dot"))
    fig.update_layout(
        title=f"{ticker} — Chaikin Money Flow (21d)",
        height=320,
        yaxis=dict(range=[-0.5, 0.5]),
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="#FAFAFA",
    )
    return fig


def obv_chart(df_daily: pd.DataFrame, ticker: str) -> go.Figure:
    sign = np.sign(df_daily["close"].diff().fillna(0))
    obv = (sign * df_daily["volume"]).cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_daily.index, y=df_daily["close"], name="Close", yaxis="y1", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=obv.index, y=obv, name="OBV", yaxis="y2", line=dict(width=1.5, color="#3B6FB6")))
    fig.update_layout(
        title=f"{ticker} — Price vs OBV (divergence detector)",
        height=350,
        yaxis=dict(title="Price"),
        yaxis2=dict(title="OBV", overlaying="y", side="right", showgrid=False),
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="#FAFAFA",
        legend=dict(orientation="h", yanchor="top", y=-0.1),
    )
    return fig


# ---- Bloomberg-terminal style additions -----------------------------------------

# Terminal-style palette tokens (used in app.py via CSS variables too)
TERM_GREEN  = "#26d65b"
TERM_RED    = "#ef4f4a"
TERM_AMBER  = "#e6b450"
TERM_BLUE   = "#5fa8d3"
TERM_MUTED  = "#8b8b8b"


def relative_strength_lines_frame(
    ohlcv: dict[str, pd.DataFrame],
    sector_tickers: list[str],
    bench_ticker: str = "SPY",
    lookback_days: int = 252,
) -> pd.DataFrame:
    """Return sector relative-strength lines normalized to 100 at the start."""
    if bench_ticker not in ohlcv:
        return pd.DataFrame()

    try:
        bench = close_price(ohlcv[bench_ticker]).dropna().astype(float)
    except (KeyError, TypeError, ValueError):
        return pd.DataFrame()
    if bench.empty:
        return pd.DataFrame()

    lines: dict[str, pd.Series] = {}
    for ticker in sector_tickers:
        if ticker == bench_ticker or ticker not in ohlcv:
            continue
        try:
            prices = close_price(ohlcv[ticker]).dropna().astype(float)
        except (KeyError, TypeError, ValueError):
            continue
        aligned = pd.concat({"price": prices, "bench": bench}, axis=1, sort=False).dropna()
        if aligned.empty:
            continue
        aligned = aligned.tail(max(2, int(lookback_days)))
        ratio = aligned["price"] / aligned["bench"].replace(0, np.nan)
        ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
        if len(ratio) < 2 or ratio.iloc[0] == 0 or pd.isna(ratio.iloc[0]):
            continue
        lines[ticker] = (ratio / ratio.iloc[0]) * 100.0

    if not lines:
        return pd.DataFrame()

    frame = pd.DataFrame(lines).dropna(how="all")
    if frame.empty:
        return frame
    latest = frame.apply(lambda column: column.dropna().iloc[-1] if column.notna().any() else np.nan)
    ordered = latest.dropna().sort_values(ascending=False).index.tolist()
    return frame[ordered]


def sector_spaghetti_chart(
    ohlcv: dict[str, pd.DataFrame],
    sector_tickers: list[str],
    bench_ticker: str = "SPY",
    lookback_days: int = 252,
) -> go.Figure:
    """Overlaid 12-month sector relative-strength lines versus SPY."""
    frame = relative_strength_lines_frame(
        ohlcv,
        sector_tickers,
        bench_ticker=bench_ticker,
        lookback_days=lookback_days,
    )
    fig = go.Figure()
    for ticker in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[ticker],
                mode="lines",
                name=ticker,
                line=dict(width=1.8),
                hovertemplate=f"<b>{ticker}</b><br>%{{x|%Y-%m-%d}}<br>RS %{{y:.1f}}<extra></extra>",
            )
        )
    fig.add_hline(y=100, line=dict(color="#444", width=1, dash="dot"))
    fig.update_layout(
        title=dict(text="US SECTOR RELATIVE STRENGTH", font=dict(size=14, color="#ccc", family="JetBrains Mono, monospace")),
        xaxis=dict(title="", color="#888", gridcolor="#222", showgrid=True),
        yaxis=dict(title=f"Relative strength vs {bench_ticker}, start = 100", color="#888", gridcolor="#222", showgrid=True),
        height=460,
        margin=dict(l=44, r=24, t=48, b=36),
        plot_bgcolor="#0a0a0a",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
            font=dict(size=10, color="#ccc", family="JetBrains Mono, monospace"),
        ),
    )
    return fig


def sparkline(df_daily: pd.DataFrame, height: int = 60) -> go.Figure:
    """Mini price line, no axes, no grid - for embedding on cards."""
    if df_daily is None or df_daily.empty:
        return go.Figure()
    p = df_daily["close"].dropna().iloc[-90:]    # last ~90 trading days
    if len(p) < 5:
        return go.Figure()
    color = TERM_GREEN if p.iloc[-1] >= p.iloc[0] else TERM_RED
    fig = go.Figure(go.Scatter(
        x=list(range(len(p))),
        y=p.values,
        mode="lines",
        line=dict(color=color, width=1.6),
        hoverinfo="skip",
    ))
    # add a baseline area for that classic terminal-y filled look
    fig.add_trace(go.Scatter(
        x=list(range(len(p))),
        y=p.values,
        fill="tozeroy",
        fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.10)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=2, b=2),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True, range=[p.min() * 0.99, p.max() * 1.01]),
    )
    return fig


def rrg_chart_dark(df: pd.DataFrame, title: str = "Rotation") -> go.Figure:
    """Dark-theme RRG. Same logic as rrg_chart but tuned for terminal aesthetic."""
    sub = df.dropna(subset=["rs_ratio", "rs_momentum"]).copy()
    fig = go.Figure()
    # quadrant shading - subtle dark tints
    fig.add_shape(type="rect", x0=100, x1=120, y0=100, y1=120, fillcolor="rgba(38,214,91,0.07)", line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=100, x1=120, y0=80,  y1=100, fillcolor="rgba(230,180,80,0.07)", line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=80,  x1=100, y0=80,  y1=100, fillcolor="rgba(239,79,74,0.07)",  line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=80,  x1=100, y0=100, y1=120, fillcolor="rgba(95,168,211,0.07)", line=dict(width=0), layer="below")
    fig.add_hline(y=100, line=dict(color="#444", width=1))
    fig.add_vline(x=100, line=dict(color="#444", width=1))
    fig.add_trace(go.Scatter(
        x=sub["rs_ratio"], y=sub["rs_momentum"],
        mode="markers+text",
        text=sub.index, textposition="top center",
        textfont=dict(size=10, color="#ddd", family="JetBrains Mono, monospace"),
        marker=dict(
            size=11,
            color=[color_for_state(s) for s in sub.get("state", pd.Series([""] * len(sub), index=sub.index))],
            line=dict(width=1, color="#222"),
        ),
        hovertemplate="<b>%{text}</b><br>RS-Ratio %{x:.1f}<br>RS-Mom %{y:.1f}<extra></extra>",
    ))
    fig.add_annotation(x=119, y=119, text="LEADING",   showarrow=False, font=dict(size=10, color=TERM_GREEN, family="JetBrains Mono, monospace"))
    fig.add_annotation(x=119, y=81,  text="WEAKENING", showarrow=False, font=dict(size=10, color=TERM_AMBER, family="JetBrains Mono, monospace"))
    fig.add_annotation(x=81,  y=81,  text="LAGGING",   showarrow=False, font=dict(size=10, color=TERM_RED,   family="JetBrains Mono, monospace"))
    fig.add_annotation(x=81,  y=119, text="IMPROVING", showarrow=False, font=dict(size=10, color=TERM_BLUE,  family="JetBrains Mono, monospace"))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#ccc", family="JetBrains Mono, monospace")),
        xaxis=dict(title="RS-RATIO",    range=[80, 120], color="#888", gridcolor="#222", zerolinecolor="#444", showgrid=True, title_font=dict(size=10, family="JetBrains Mono, monospace")),
        yaxis=dict(title="RS-MOMENTUM", range=[80, 120], color="#888", gridcolor="#222", zerolinecolor="#444", showgrid=True, title_font=dict(size=10, family="JetBrains Mono, monospace")),
        height=560,
        margin=dict(l=40, r=40, t=50, b=40),
        plot_bgcolor="#0a0a0a",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---- Inline SVG sparkline (for HTML-rendered cards) -----------------------------

def svg_sparkline(df_daily, color: str, width: int = 240, height: int = 50, style: str = "filled") -> str:
    """Return raw SVG markup for an inline sparkline. Matches Claude Design output."""
    mode = str(style).strip().lower()
    if mode == "off":
        return ""
    if df_daily is None or df_daily.empty:
        return ""
    try:
        p = df_daily["close"].dropna().iloc[-90:].astype(float).values
    except Exception:
        return ""
    if len(p) < 5:
        return ""
    mn, mx = float(p.min()), float(p.max())
    rng = max(0.001, mx - mn)
    step_x = width / (len(p) - 1)
    pts = [(i * step_x, height - ((v - mn) / rng) * (height - 6) - 3) for i, v in enumerate(p)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(pts))
    area = f"{path} L{width},{height} L0,{height} Z"
    grad_id = f"sg-{abs(hash(color + str(len(p)))) % 100000}"
    last_x, last_y = pts[-1]
    fill = ""
    if mode == "filled":
        fill = (
            f'<defs><linearGradient id="{grad_id}" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0%" stop-color="{color}" stop-opacity="0.32"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{area}" fill="url(#{grad_id})"/>'
        )
    return (
        f'<svg class="pick-spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'{fill}'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="2.2" fill="{color}"/>'
        f'</svg>'
    )
