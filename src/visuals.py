"""Plotly visualizations for the dashboard."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go


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
