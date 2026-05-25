"""HTML helpers for full-table hover previews."""
from __future__ import annotations

import math
import re
from html import escape
from typing import Any, Mapping


def _value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(key, default)
    return default


def _finite_float(value: Any, default: float = 100.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _signed(value: Any) -> str:
    result = _finite_float(value, 0.0)
    return f"{result:+.2f}"


def _css_token(value: Any) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "UNKNOWN"))
    return token or "UNKNOWN"


def rrg_preview_position(rs_ratio: Any, rs_momentum: Any) -> tuple[float, float]:
    """Normalize RRG coordinates into mini-chart CSS percentages."""
    ratio = _finite_float(rs_ratio)
    momentum = _finite_float(rs_momentum)

    def normalize(value: float) -> float:
        return max(0.0, min(100.0, ((value - 80.0) / 40.0) * 100.0))

    return (round(normalize(ratio), 1), round(normalize(momentum), 1))


def table_row_rrg_preview_html(ticker: str, row: Mapping[str, Any]) -> str:
    """Return safe hover-preview HTML for a full-table ticker row."""
    state = str(_value(row, "state", "UNKNOWN") or "UNKNOWN")
    quadrant = str(_value(row, "rrg_quadrant", "Unknown") or "Unknown")
    rs_ratio = _finite_float(_value(row, "rs_ratio"))
    rs_momentum = _finite_float(_value(row, "rs_momentum"))
    x, y = rrg_preview_position(rs_ratio, rs_momentum)

    return f"""
    <span class="row-preview" aria-hidden="true">
      <span class="row-preview-head">
        <strong>{escape(str(ticker), quote=True)}</strong>
        <em>{escape(quadrant, quote=True)}</em>
      </span>
      <span class="mini-rrg" style="--rrg-x:{x:.1f}%;--rrg-y:{y:.1f}%;">
        <span class="mini-rrg-axis x"></span>
        <span class="mini-rrg-axis y"></span>
        <span class="mini-rrg-label lead">Leading</span>
        <span class="mini-rrg-label lag">Lagging</span>
        <span class="mini-rrg-dot {_css_token(state)}"></span>
      </span>
      <span class="row-preview-meta">
        RS {rs_ratio:.1f} &middot; MOM {rs_momentum:.1f} &middot; S {_signed(_value(row, "S_score"))} &middot; F {_signed(_value(row, "F_score"))}
      </span>
    </span>
    """
