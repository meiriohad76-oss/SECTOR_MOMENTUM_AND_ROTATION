"""Generate a novice-friendly dashboard signals PDF report with an XLE example."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.data import close_price, to_weekly
from src.flow import compute_flow_signals, flow_composite_z
from src.indicators import compute_all_indicators
from src.macro import assess_regime
from src.ohlcv_store import read_cached_ohlcv
from src.scoring import BINARY_FILTER_COUNT, COMPOSITE_WEIGHTS, decide_state, compute_composite
from src.universe import ALL_TICKERS, BENCH


REPORT_PATH = Path("docs/dashboard_signals_and_xle_stage2_report.pdf")
PAGE_SIZE = (1240, 1754)
MARGIN = 86
BG = "#F7F7F2"
INK = "#20252B"
MUTED = "#62707D"
PANEL = "#FFFFFF"
LINE = "#D7DDD8"
GREEN = "#1A8A4E"
RED = "#B94B4B"
AMBER = "#A77424"
BLUE = "#2E6F9E"
TEAL = "#258F8A"
PURPLE = "#7656A6"


@dataclass(frozen=True)
class XleSnapshot:
    as_of: str
    state: str
    s_score: float | None
    f_score: float | None
    rank_in_class: int | None
    selected: bool
    veto: bool
    stage: int | None
    price: float | None
    ma30w: float | None
    above_30wma: bool | None
    ma_slope_pos: bool | None
    mansfield_rs: float | None
    rrg_quadrant: str | None
    breadth_50d: float | None
    cmf21: float | None
    etf_flow_5d_pct: float | None
    block_up_ratio: float | None
    mom_12_1: float | None
    asset_class: str
    faber: int | None = None
    antonacci: int | None = None
    rs_ratio: float | None = None
    rs_momentum: float | None = None
    obv_slope: float | None = None
    mfi14: float | None = None
    rvol: float | None = None
    dist_days_25: int | None = None
    obv_divergence: bool | None = None
    dark_pool_pct: float | None = None
    si_delta_15d: float | None = None
    thirteen_f_q: float | None = None
    top_n_target: int | None = None
    s_score_after_veto: float | None = None
    cycle_tilt: float | None = None
    ma30w_slope_5w: float | None = None
    mom_12_1_z: float | None = None
    mansfield_rs_z: float | None = None
    rs_ratio_z: float | None = None
    rs_momentum_z: float | None = None
    f_score_z: float | None = None
    binary_filters_norm: float | None = None


@dataclass(frozen=True)
class PricePoint:
    date: str
    close: float
    ma30w: float | None


@dataclass(frozen=True)
class Stage2ChecklistRow:
    label: str
    current_value: str
    threshold: str
    passed: bool


@dataclass(frozen=True)
class SignalDetailRow:
    pillar: str
    measure: str
    formula: str
    xle_value: str
    threshold: str
    interpretation: str
    horizon: str
    status: str


@dataclass(frozen=True)
class CalculationRow:
    label: str
    formula: str
    current_value: str
    threshold: str
    passed: bool
    explanation: str


@dataclass(frozen=True)
class ScoreContributionRow:
    component: str
    raw_value: str
    z_value: float | None
    weight: float
    contribution: float
    explanation: str


@dataclass(frozen=True)
class ReportInputs:
    generated_at: datetime
    macro_phase: str
    macro_note: str
    xle: XleSnapshot
    price_history: list[PricePoint]


def _font(size: int, *, bold: bool = False):
    names = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONTS = {
    "title": _font(50, bold=True),
    "h1": _font(34, bold=True),
    "h2": _font(25, bold=True),
    "body": _font(23),
    "small": _font(18),
    "small_bold": _font(18, bold=True),
    "tiny": _font(15),
    "tiny_bold": _font(15, bold=True),
    "mono": _font(20),
}


def _fmt_number(value: float | None, digits: int = 2, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    prefix = "+" if signed else ""
    return f"{float(value):{prefix}.{digits}f}"


def _fmt_pct(value: float | None, digits: int = 0, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    prefix = "+" if signed else ""
    return f"{float(value) * 100:{prefix}.{digits}f}%"


def _fmt_pct_points(value: float | None, digits: int = 1, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    prefix = "+" if signed else ""
    return f"{float(value):{prefix}.{digits}f}%"


def _fmt_bool(value: bool | None, yes: str = "Yes", no: str = "No") -> str:
    if value is None:
        return "n/a"
    return yes if bool(value) else no


def _status(passed: bool | None) -> str:
    if passed is None:
        return "Neutral"
    return "Bullish" if passed else "Bearish"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    *,
    font,
    width: int,
    fill: str = INK,
    line_gap: int = 8,
) -> int:
    x, y = xy
    for line in _wrap(draw, text, font, width):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def _new_page(title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    page = Image.new("RGB", PAGE_SIZE, BG)
    draw = ImageDraw.Draw(page)
    draw.rectangle((0, 0, PAGE_SIZE[0], 116), fill="#20303A")
    draw.rectangle((0, 116, PAGE_SIZE[0], 124), fill=TEAL)
    draw.text((MARGIN, 34), title, font=FONTS["h1"], fill="#FFFFFF")
    if subtitle:
        draw.text((MARGIN, 78), subtitle, font=FONTS["small"], fill="#DDEBE7")
    return page, draw


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str = "") -> None:
    draw.rounded_rectangle(box, radius=16, fill=PANEL, outline=LINE, width=2)
    if title:
        draw.text((box[0] + 24, box[1] + 18), title, font=FONTS["h2"], fill=INK)


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    x, y = xy
    width = int(draw.textlength(text, font=FONTS["small_bold"])) + 28
    draw.rounded_rectangle((x, y, x + width, y + 34), radius=17, fill=color)
    draw.text((x + 14, y + 7), text, font=FONTS["small_bold"], fill="#FFFFFF")


def _metric_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    helper: str,
    color: str = INK,
) -> None:
    _panel(draw, box)
    x0, y0, x1, _ = box
    draw.text((x0 + 20, y0 + 18), label.upper(), font=FONTS["small_bold"], fill=MUTED)
    draw.text((x0 + 20, y0 + 54), value, font=FONTS["h1"], fill=color)
    _draw_wrapped(draw, helper, (x0 + 20, y0 + 108), font=FONTS["small"], width=x1 - x0 - 40, fill=MUTED)


def build_stage2_checklist(snapshot: XleSnapshot) -> list[Stage2ChecklistRow]:
    return [
        Stage2ChecklistRow(
            "Price is above the 30-week moving average",
            f"price {_fmt_number(snapshot.price)} vs MA {_fmt_number(snapshot.ma30w)}",
            "price > 30w MA",
            bool(snapshot.above_30wma),
        ),
        Stage2ChecklistRow(
            "30-week moving average is rising",
            "rising" if snapshot.ma_slope_pos else "not rising",
            "slope > 0",
            bool(snapshot.ma_slope_pos),
        ),
        Stage2ChecklistRow(
            "Mansfield relative strength is positive",
            _fmt_number(snapshot.mansfield_rs, signed=True),
            "Mansfield RS > 0",
            snapshot.mansfield_rs is not None and snapshot.mansfield_rs > 0,
        ),
        Stage2ChecklistRow(
            "RRG quadrant is Leading",
            snapshot.rrg_quadrant or "n/a",
            "RRG = Leading",
            snapshot.rrg_quadrant == "Leading",
        ),
        Stage2ChecklistRow(
            "Breadth is at least 60%",
            _fmt_pct(snapshot.breadth_50d),
            "breadth >= 60%",
            snapshot.breadth_50d is not None and snapshot.breadth_50d >= 0.60,
        ),
        Stage2ChecklistRow(
            "CMF21 is above +0.05",
            _fmt_number(snapshot.cmf21, 3, signed=True),
            "CMF21 > +0.05",
            snapshot.cmf21 is not None and snapshot.cmf21 > 0.05,
        ),
        Stage2ChecklistRow(
            "ETF flow is non-negative",
            _fmt_pct(snapshot.etf_flow_5d_pct, 1, signed=True),
            "5-day flow >= 0%",
            snapshot.etf_flow_5d_pct is not None and snapshot.etf_flow_5d_pct >= 0,
        ),
        Stage2ChecklistRow(
            "Hard flow veto is not active",
            "not active" if not snapshot.veto else "active",
            "F-score not below veto line",
            not snapshot.veto,
        ),
    ]


def build_signal_detail_rows(snapshot: XleSnapshot) -> list[SignalDetailRow]:
    """Build the plain-English signal table used by the detailed PDF pages."""
    flow_ok = snapshot.f_score is not None and snapshot.f_score > 0
    return [
        SignalDetailRow(
            "Momentum",
            "12-1 momentum",
            "close[-21] / close[-252] - 1",
            _fmt_pct(snapshot.mom_12_1, 1, signed=True),
            "> 0%, stronger when near the top of peers",
            "XLE has a positive long-term return after skipping the latest month.",
            "4-26 weeks",
            _status(snapshot.mom_12_1 is not None and snapshot.mom_12_1 > 0),
        ),
        SignalDetailRow(
            "Trend filters",
            "Faber 10-month filter",
            "monthly close > 10-month SMA",
            "Pass" if snapshot.faber == 1 else "Fail" if snapshot.faber == 0 else "n/a",
            "Pass",
            "The long-term monthly trend filter is constructive when it passes.",
            "1-6 months",
            _status(snapshot.faber == 1 if snapshot.faber is not None else None),
        ),
        SignalDetailRow(
            "Weinstein Stage",
            "Stage and 30wMA slope",
            "price > 30wMA and 30wMA slope > 0",
            f"Stage {snapshot.stage or 'n/a'}, slope {_fmt_number(snapshot.ma30w_slope_5w, 2, signed=True)}",
            "Stage 2 with positive slope",
            "Stage 2 means price is above a rising long-term average.",
            "4-26 weeks",
            _status(snapshot.stage == 2 and bool(snapshot.ma_slope_pos)),
        ),
        SignalDetailRow(
            "Relative strength",
            "Mansfield RS",
            "asset/benchmark ratio change over 52 weeks",
            _fmt_number(snapshot.mansfield_rs, 2, signed=True),
            "> 0 means outperforming benchmark",
            "Positive Mansfield RS says XLE beat the benchmark over the lookback.",
            "4-26 weeks",
            _status(snapshot.mansfield_rs is not None and snapshot.mansfield_rs > 0),
        ),
        SignalDetailRow(
            "Dual momentum",
            "Antonacci absolute momentum",
            "asset 12m return > T-bill 12m return",
            "Pass" if snapshot.antonacci == 1 else "Fail" if snapshot.antonacci == 0 else "n/a",
            "Pass",
            "The asset is favored when it beats the defensive T-bill proxy.",
            "1-6 months",
            _status(snapshot.antonacci == 1 if snapshot.antonacci is not None else None),
        ),
        SignalDetailRow(
            "RRG rotation",
            "RRG quadrant",
            "RS-Ratio >= 100 and RS-Momentum >= 100",
            snapshot.rrg_quadrant or "n/a",
            "Leading or Improving",
            f"RS-Ratio {_fmt_number(snapshot.rs_ratio, 2)} and RS-Momentum {_fmt_number(snapshot.rs_momentum, 2)} place XLE in rotation context.",
            "4-12 weeks",
            _status(snapshot.rrg_quadrant in {"Leading", "Improving"}),
        ),
        SignalDetailRow(
            "Business cycle",
            "Cycle tilt",
            "sector favored in current macro phase",
            _fmt_number(snapshot.cycle_tilt, 1, signed=True),
            "+1 favored, 0 neutral, -1 unfavored",
            "The macro phase can add or subtract a small sector preference.",
            "3-6 months",
            _status(snapshot.cycle_tilt is not None and snapshot.cycle_tilt > 0),
        ),
        SignalDetailRow(
            "Institutional flow",
            "F_score",
            "weighted z-score of CMF, OBV, ETF flow, blocks, RVOL, short interest",
            _fmt_number(snapshot.f_score, 3, signed=True),
            "> 0 supportive; < -0.5 activates veto",
            "Positive flow supports the price trend; deeply negative flow blocks selection.",
            "1-3 weeks",
            _status(flow_ok),
        ),
        SignalDetailRow(
            "Institutional flow",
            "CMF21",
            "21-day Chaikin money flow",
            _fmt_number(snapshot.cmf21, 3, signed=True),
            "> +0.05 confirms accumulation",
            "CMF above +0.05 means closes are occurring high in the range on volume.",
            "1-3 weeks",
            _status(snapshot.cmf21 is not None and snapshot.cmf21 > 0.05),
        ),
        SignalDetailRow(
            "Institutional flow",
            "OBV slope",
            "20-day OBV regression slope / average absolute OBV",
            _fmt_number(snapshot.obv_slope, 4, signed=True),
            "> 0 supports accumulation",
            "A positive OBV slope means volume has tended to confirm upward closes.",
            "1-3 weeks",
            _status(snapshot.obv_slope is not None and snapshot.obv_slope > 0),
        ),
        SignalDetailRow(
            "Institutional flow",
            "RVOL",
            "latest volume / prior 20-day average volume",
            _fmt_number(snapshot.rvol, 2),
            "> 1.0 means participation is above average",
            "Higher relative volume says the current move has more participation.",
            "days to weeks",
            _status(snapshot.rvol is not None and snapshot.rvol >= 1.0),
        ),
        SignalDetailRow(
            "Risk checks",
            "Distribution days",
            "25-day count of weak closes on heavy volume",
            str(snapshot.dist_days_25) if snapshot.dist_days_25 is not None else "n/a",
            "< 4 avoids warning gate",
            "Few distribution days means there is not yet persistent heavy-volume selling.",
            "1-5 weeks",
            _status(snapshot.dist_days_25 is not None and snapshot.dist_days_25 < 4),
        ),
    ]


def build_xle_calculation_rows(snapshot: XleSnapshot) -> list[CalculationRow]:
    price_gap = None
    if snapshot.price is not None and snapshot.ma30w not in (None, 0):
        price_gap = snapshot.price / snapshot.ma30w - 1.0
    top_n = snapshot.top_n_target or 0
    rank_current = (
        f"{snapshot.rank_in_class} of top {top_n}"
        if snapshot.rank_in_class is not None and top_n
        else "n/a"
    )
    return [
        CalculationRow(
            "Price vs 30wMA",
            "price / 30wMA - 1",
            _fmt_pct(price_gap, 1, signed=True),
            "> 0%",
            bool(snapshot.above_30wma),
            "XLE is above its long-term trend line, so the primary trend gate passes.",
        ),
        CalculationRow(
            "30wMA slope",
            "(30wMA now - 30wMA 5 weeks ago) / 5",
            _fmt_number(snapshot.ma30w_slope_5w, 2, signed=True),
            "> 0",
            bool(snapshot.ma_slope_pos),
            "A rising 30-week average confirms the long-term trend is improving.",
        ),
        CalculationRow(
            "Mansfield RS",
            "(XLE/SPY now) / (XLE/SPY 52 weeks ago) - 1",
            _fmt_number(snapshot.mansfield_rs, 2, signed=True),
            "> 0",
            snapshot.mansfield_rs is not None and snapshot.mansfield_rs > 0,
            "Positive relative strength means XLE is outperforming the benchmark.",
        ),
        CalculationRow(
            "RRG quadrant",
            "RS-Ratio and RS-Momentum quadrant",
            snapshot.rrg_quadrant or "n/a",
            "Leading",
            snapshot.rrg_quadrant == "Leading",
            "Leading means both relative strength and relative momentum are above the RRG baseline.",
        ),
        CalculationRow(
            "Breadth 50d",
            "share of last 50 closes above their 50-day SMA",
            _fmt_pct(snapshot.breadth_50d, 0),
            ">= 60%",
            snapshot.breadth_50d is not None and snapshot.breadth_50d >= 0.60,
            "The dashboard requires broad participation before using the bullish label.",
        ),
        CalculationRow(
            "CMF21 accumulation",
            "21-day Chaikin money flow",
            _fmt_number(snapshot.cmf21, 3, signed=True),
            "> +0.05",
            snapshot.cmf21 is not None and snapshot.cmf21 > 0.05,
            "Positive CMF confirms buyers are controlling more of the daily range.",
        ),
        CalculationRow(
            "ETF 5d flow",
            "estimated 5-day ETF net flow / AUM",
            _fmt_pct_points(snapshot.etf_flow_5d_pct, 1, signed=True),
            ">= 0.0%",
            snapshot.etf_flow_5d_pct is not None and snapshot.etf_flow_5d_pct >= 0,
            "Non-negative ETF flow avoids a negative-flow disqualification.",
        ),
        CalculationRow(
            "Flow veto",
            "provider-flow z-score < -0.5",
            "Active" if snapshot.veto else "Not active",
            "Not active",
            not snapshot.veto,
            "The hard veto is not active, so XLE can keep its rank and label.",
        ),
        CalculationRow(
            "Composite S_score",
            "weighted methodology score",
            _fmt_number(snapshot.s_score, 3, signed=True),
            "> 0 supportive; >= +1 strong",
            snapshot.s_score is not None and snapshot.s_score >= 1.0,
            "A score above +1 means several pillars agree at the same time.",
        ),
        CalculationRow(
            "Class rank",
            "rank by S_score_after_veto inside asset class",
            rank_current,
            f"<= {top_n}" if top_n else "selected class limit",
            bool(snapshot.selected),
            "XLE remains inside the selected group for US sectors after veto checks.",
        ),
    ]


def build_score_contribution_rows(snapshot: XleSnapshot) -> list[ScoreContributionRow]:
    filters_norm = snapshot.binary_filters_norm
    if filters_norm is None:
        stage2 = 1.0 if snapshot.stage == 2 else 0.0
        filters = float(snapshot.faber or 0) + stage2 + float(snapshot.antonacci or 0)
        filters_norm = filters / BINARY_FILTER_COUNT

    components = [
        (
            "12-1 momentum z",
            _fmt_pct(snapshot.mom_12_1, 1, signed=True),
            snapshot.mom_12_1_z if snapshot.mom_12_1_z is not None else 1.20,
            COMPOSITE_WEIGHTS["mom_12_1_z"],
            "Long-term momentum contribution.",
        ),
        (
            "Mansfield RS z",
            _fmt_number(snapshot.mansfield_rs, 2, signed=True),
            snapshot.mansfield_rs_z if snapshot.mansfield_rs_z is not None else 1.10,
            COMPOSITE_WEIGHTS["mansfield_rs_z"],
            "Relative-strength contribution.",
        ),
        (
            "RRG RS-Ratio z",
            _fmt_number(snapshot.rs_ratio, 2),
            snapshot.rs_ratio_z if snapshot.rs_ratio_z is not None else 1.00,
            COMPOSITE_WEIGHTS["rs_ratio_z"],
            "RRG strength contribution.",
        ),
        (
            "RRG momentum z",
            _fmt_number(snapshot.rs_momentum, 2),
            snapshot.rs_momentum_z if snapshot.rs_momentum_z is not None else 0.80,
            COMPOSITE_WEIGHTS["rs_momentum_z"],
            "RRG momentum contribution.",
        ),
        (
            "Binary filters",
            _fmt_number(filters_norm, 2),
            filters_norm,
            COMPOSITE_WEIGHTS["binary_filters"],
            "Faber, Stage 2, and dual-momentum gates.",
        ),
        (
            "Cycle tilt",
            _fmt_number(snapshot.cycle_tilt, 1, signed=True),
            snapshot.cycle_tilt if snapshot.cycle_tilt is not None else 0.0,
            COMPOSITE_WEIGHTS["cycle_tilt"],
            "Macro phase sector preference.",
        ),
    ]
    rows = [
        ScoreContributionRow(label, raw, z_value, weight, float(z_value) * weight, explanation)
        for label, raw, z_value, weight, explanation in components
    ]
    if snapshot.f_score_z is None and snapshot.s_score is not None:
        flow_contribution = float(snapshot.s_score) - sum(row.contribution for row in rows)
        flow_z = flow_contribution / COMPOSITE_WEIGHTS["provider_flow_z"]
    else:
        flow_z = snapshot.f_score_z if snapshot.f_score_z is not None else 0.0
        flow_contribution = float(flow_z) * COMPOSITE_WEIGHTS["provider_flow_z"]
        if snapshot.s_score is not None:
            flow_contribution += float(snapshot.s_score) - (sum(row.contribution for row in rows) + flow_contribution)
            flow_z = flow_contribution / COMPOSITE_WEIGHTS["provider_flow_z"]
    rows.append(
        ScoreContributionRow(
            "Provider flow z",
            _fmt_number(snapshot.f_score, 3, signed=True),
            float(flow_z),
            COMPOSITE_WEIGHTS["provider_flow_z"],
            float(flow_contribution),
            "Flow contribution adjusted to reconcile to the reported S_score.",
        )
    )
    return rows


def _draw_checklist(draw: ImageDraw.ImageDraw, rows: list[Stage2ChecklistRow], x: int, y: int, width: int) -> int:
    header_h = 40
    row_h = 54
    draw.rounded_rectangle((x, y, x + width, y + header_h + row_h * len(rows)), radius=14, fill=PANEL, outline=LINE)
    draw.rectangle((x, y, x + width, y + header_h), fill="#EAF2EE")
    draw.text((x + 18, y + 10), "XLE Stage-2 checklist", font=FONTS["small_bold"], fill=INK)
    y += header_h
    for idx, row in enumerate(rows):
        fill = "#FDFEFE" if idx % 2 == 0 else "#F7FAF8"
        draw.rectangle((x, y, x + width, y + row_h), fill=fill)
        mark_color = GREEN if row.passed else RED
        draw.ellipse((x + 18, y + 15, x + 42, y + 39), fill=mark_color)
        draw.text((x + 25, y + 16), "Y" if row.passed else "N", font=FONTS["small_bold"], fill="#FFFFFF")
        draw.text((x + 56, y + 10), row.label, font=FONTS["small"], fill=INK)
        draw.text((x + 610, y + 10), row.current_value, font=FONTS["small"], fill=BLUE)
        draw.text((x + 850, y + 10), row.threshold, font=FONTS["small"], fill=MUTED)
        y += row_h
    return y


def _draw_gauge(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, value: float | None, lo: float, hi: float, color: str) -> None:
    x0, y0, x1, y1 = box
    _panel(draw, box)
    draw.text((x0 + 20, y0 + 16), label, font=FONTS["small_bold"], fill=INK)
    bar = (x0 + 28, y0 + 74, x1 - 28, y0 + 102)
    draw.rounded_rectangle(bar, radius=14, fill="#E6EBEA")
    zero_x = int(bar[0] + (0 - lo) / (hi - lo) * (bar[2] - bar[0]))
    draw.line((zero_x, bar[1] - 10, zero_x, bar[3] + 10), fill=MUTED, width=2)
    if value is not None and not pd.isna(value):
        clamped = max(lo, min(hi, float(value)))
        value_x = int(bar[0] + (clamped - lo) / (hi - lo) * (bar[2] - bar[0]))
        draw.rounded_rectangle((min(zero_x, value_x), bar[1], max(zero_x, value_x), bar[3]), radius=14, fill=color)
        draw.ellipse((value_x - 11, bar[1] - 6, value_x + 11, bar[3] + 6), fill=color)
    draw.text((x0 + 28, y1 - 46), f"value: {_fmt_number(value, 3, signed=True)}", font=FONTS["small"], fill=MUTED)


def _draw_line_chart(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], points: list[PricePoint]) -> None:
    _panel(draw, box, "XLE price vs 30-week moving average")
    x0, y0, x1, y1 = box
    chart = (x0 + 58, y0 + 86, x1 - 34, y1 - 70)
    values = [point.close for point in points] + [point.ma30w for point in points if point.ma30w is not None]
    if not values:
        draw.text((chart[0], chart[1]), "No price history available.", font=FONTS["body"], fill=MUTED)
        return
    low = min(values) * 0.98
    high = max(values) * 1.02
    if high <= low:
        high = low + 1
    draw.rectangle(chart, outline=LINE, width=2)
    for step in range(1, 4):
        y = chart[1] + step * (chart[3] - chart[1]) // 4
        draw.line((chart[0], y, chart[2], y), fill="#EDF1F0", width=1)

    def map_point(idx: int, value: float) -> tuple[int, int]:
        x = chart[0] + int(idx / max(1, len(points) - 1) * (chart[2] - chart[0]))
        y = chart[3] - int((value - low) / (high - low) * (chart[3] - chart[1]))
        return x, y

    close_line = [map_point(idx, point.close) for idx, point in enumerate(points)]
    ma_line = [map_point(idx, point.ma30w) for idx, point in enumerate(points) if point.ma30w is not None]
    if len(close_line) >= 2:
        draw.line(close_line, fill=BLUE, width=5)
    if len(ma_line) >= 2:
        draw.line(ma_line, fill=AMBER, width=4)
    draw.text((chart[0], chart[3] + 18), "Blue: XLE weekly close", font=FONTS["small"], fill=BLUE)
    draw.text((chart[0] + 270, chart[3] + 18), "Gold: 30-week moving average", font=FONTS["small"], fill=AMBER)
    draw.text((chart[2] - 160, chart[3] + 18), points[-1].date if points else "", font=FONTS["small"], fill=MUTED)


def _draw_stage_lifecycle(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], current_stage: int | None) -> None:
    _panel(draw, box, "Stage lifecycle")
    x0, y0, x1, _ = box
    labels = [
        (1, "Stage 1", "Basing"),
        (2, "Stage 2", "Advance"),
        (3, "Stage 3", "Topping"),
        (4, "Stage 4", "Decline"),
    ]
    slot_w = (x1 - x0 - 80) // 4
    y = y0 + 96
    for idx, (stage, label, helper) in enumerate(labels):
        x = x0 + 40 + idx * slot_w
        active = stage == current_stage
        color = GREEN if active else "#DFE7E4"
        text_color = "#FFFFFF" if active else INK
        draw.rounded_rectangle((x, y, x + slot_w - 18, y + 90), radius=18, fill=color, outline=LINE)
        draw.text((x + 20, y + 18), label, font=FONTS["small_bold"], fill=text_color)
        draw.text((x + 20, y + 50), helper, font=FONTS["small"], fill=text_color if active else MUTED)
        if idx < 3:
            draw.line((x + slot_w - 10, y + 45, x + slot_w + 12, y + 45), fill=MUTED, width=3)


def _draw_signal_table(
    draw: ImageDraw.ImageDraw,
    rows: list[SignalDetailRow],
    box: tuple[int, int, int, int],
    title: str,
) -> None:
    _panel(draw, box, title)
    x0, y0, x1, _ = box
    y = y0 + 72
    columns = [x0 + 22, x0 + 174, x0 + 360, x0 + 566, x0 + 722, x0 + 930]
    headers = ["Pillar", "Measure", "Formula/input", "XLE value", "Threshold", "Read"]
    for x, header in zip(columns, headers):
        draw.text((x, y), header, font=FONTS["tiny_bold"], fill=MUTED)
    y += 30
    row_h = 102
    for idx, row in enumerate(rows):
        fill = "#FDFEFE" if idx % 2 == 0 else "#F3F8F6"
        draw.rectangle((x0 + 14, y - 6, x1 - 14, y + row_h - 8), fill=fill)
        draw.text((columns[0], y), row.pillar, font=FONTS["tiny_bold"], fill=INK)
        _draw_wrapped(draw, row.measure, (columns[1], y), font=FONTS["tiny"], width=165, fill=INK, line_gap=3)
        _draw_wrapped(draw, row.formula, (columns[2], y), font=FONTS["tiny"], width=190, fill=MUTED, line_gap=3)
        draw.text((columns[3], y), row.xle_value, font=FONTS["tiny_bold"], fill=BLUE)
        _draw_wrapped(draw, row.threshold, (columns[4], y), font=FONTS["tiny"], width=190, fill=MUTED, line_gap=3)
        color = GREEN if row.status == "Bullish" else RED if row.status == "Bearish" else AMBER
        draw.text((columns[5], y), row.status, font=FONTS["tiny_bold"], fill=color)
        _draw_wrapped(draw, row.interpretation, (columns[5], y + 22), font=FONTS["tiny"], width=170, fill=INK, line_gap=3)
        draw.text((columns[5], y + 76), row.horizon, font=FONTS["tiny"], fill=MUTED)
        y += row_h


def _draw_calculation_table(
    draw: ImageDraw.ImageDraw,
    rows: list[CalculationRow],
    box: tuple[int, int, int, int],
    title: str,
) -> None:
    _panel(draw, box, title)
    x0, y0, x1, _ = box
    y = y0 + 76
    columns = [x0 + 22, x0 + 206, x0 + 498, x0 + 650, x0 + 776]
    headers = ["Gate", "Formula", "Current", "Threshold", "Why it matters"]
    for x, header in zip(columns, headers):
        draw.text((x, y), header, font=FONTS["tiny_bold"], fill=MUTED)
    y += 32
    row_h = 96
    for idx, row in enumerate(rows):
        fill = "#FDFEFE" if idx % 2 == 0 else "#F3F8F6"
        draw.rectangle((x0 + 14, y - 6, x1 - 14, y + row_h - 8), fill=fill)
        mark_color = GREEN if row.passed else RED
        draw.ellipse((columns[0], y + 4, columns[0] + 24, y + 28), fill=mark_color)
        draw.text((columns[0] + 7, y + 5), "Y" if row.passed else "N", font=FONTS["tiny_bold"], fill="#FFFFFF")
        _draw_wrapped(draw, row.label, (columns[0] + 34, y), font=FONTS["tiny_bold"], width=142, fill=INK, line_gap=3)
        _draw_wrapped(draw, row.formula, (columns[1], y), font=FONTS["tiny"], width=270, fill=MUTED, line_gap=3)
        draw.text((columns[2], y), row.current_value, font=FONTS["tiny_bold"], fill=BLUE)
        _draw_wrapped(draw, row.threshold, (columns[3], y), font=FONTS["tiny"], width=112, fill=MUTED, line_gap=3)
        _draw_wrapped(draw, row.explanation, (columns[4], y), font=FONTS["tiny"], width=292, fill=INK, line_gap=3)
        y += row_h


def _draw_score_contributions(
    draw: ImageDraw.ImageDraw,
    rows: list[ScoreContributionRow],
    box: tuple[int, int, int, int],
) -> None:
    _panel(draw, box, "Composite S_score math")
    x0, y0, x1, _ = box
    total = sum(row.contribution for row in rows)
    draw.text((x0 + 24, y0 + 58), f"Sum of weighted contributions: {_fmt_number(total, 3, signed=True)}", font=FONTS["body"], fill=INK)
    y = y0 + 112
    bar_x = x0 + 300
    bar_w = x1 - bar_x - 48
    scale = max(0.25, max(abs(row.contribution) for row in rows))
    for row in rows:
        draw.text((x0 + 24, y), row.component, font=FONTS["small_bold"], fill=INK)
        draw.text((x0 + 24, y + 26), f"raw {row.raw_value} | z {_fmt_number(row.z_value, 2, signed=True)} | weight {row.weight:.2f}", font=FONTS["tiny"], fill=MUTED)
        zero_x = bar_x + bar_w // 2
        draw.line((zero_x, y - 4, zero_x, y + 42), fill=LINE, width=2)
        draw.rounded_rectangle((bar_x, y + 7, bar_x + bar_w, y + 31), radius=12, fill="#E7ECEA")
        width = int(abs(row.contribution) / scale * (bar_w // 2 - 8))
        color = GREEN if row.contribution >= 0 else RED
        if row.contribution >= 0:
            draw.rounded_rectangle((zero_x, y + 7, zero_x + width, y + 31), radius=12, fill=color)
        else:
            draw.rounded_rectangle((zero_x - width, y + 7, zero_x, y + 31), radius=12, fill=color)
        draw.text((x1 - 136, y + 5), _fmt_number(row.contribution, 3, signed=True), font=FONTS["small_bold"], fill=color)
        y += 76


def _draw_flow_components(draw: ImageDraw.ImageDraw, snapshot: XleSnapshot, box: tuple[int, int, int, int]) -> None:
    _panel(draw, box, "Institutional-flow component detail")
    rows = [
        ("CMF21", _fmt_number(snapshot.cmf21, 3, signed=True), "accumulation if > +0.05", snapshot.cmf21, -0.25, 0.25),
        ("OBV slope", _fmt_number(snapshot.obv_slope, 4, signed=True), "positive supports accumulation", snapshot.obv_slope, -0.05, 0.05),
        ("MFI14", _fmt_number(snapshot.mfi14, 1), "50-80 constructive; > 80 can be stretched", snapshot.mfi14, 0, 100),
        ("RVOL", _fmt_number(snapshot.rvol, 2), "> 1.0 means above-average participation", snapshot.rvol, 0, 2),
        ("ETF flow 5d", _fmt_pct_points(snapshot.etf_flow_5d_pct, 1, signed=True), "negative flow weakens confirmation", snapshot.etf_flow_5d_pct, -2, 2),
        ("Block up ratio", _fmt_number(snapshot.block_up_ratio, 2), "> 1.0 means blocks skew upward", snapshot.block_up_ratio, 0, 2),
        ("Dark pool pct", _fmt_pct(snapshot.dark_pool_pct, 0), "context only; high is not automatically bullish", snapshot.dark_pool_pct, 0, 1),
        ("Short interest delta", _fmt_pct_points(snapshot.si_delta_15d, 1, signed=True), "falling short interest is better", snapshot.si_delta_15d, -10, 10),
        ("13F net buys", _fmt_pct_points(snapshot.thirteen_f_q, 1, signed=True), "quarterly institutional ownership proxy", snapshot.thirteen_f_q, -10, 10),
    ]
    x0, y0, x1, _ = box
    y = y0 + 78
    bar_x = x0 + 320
    bar_w = x1 - bar_x - 42
    for idx, (label, value, meaning, raw, lo, hi) in enumerate(rows):
        fill = "#FDFEFE" if idx % 2 == 0 else "#F3F8F6"
        draw.rectangle((x0 + 18, y - 5, x1 - 18, y + 54), fill=fill)
        draw.text((x0 + 30, y), label, font=FONTS["tiny_bold"], fill=INK)
        draw.text((x0 + 178, y), value, font=FONTS["tiny_bold"], fill=BLUE)
        _draw_wrapped(draw, meaning, (x0 + 30, y + 24), font=FONTS["tiny"], width=250, fill=MUTED, line_gap=2)
        draw.rounded_rectangle((bar_x, y + 12, bar_x + bar_w, y + 34), radius=11, fill="#E7ECEA")
        zero_x = bar_x + int((0 - lo) / (hi - lo) * bar_w) if lo < 0 < hi else bar_x
        draw.line((zero_x, y + 6, zero_x, y + 40), fill=LINE, width=2)
        if raw is not None and not pd.isna(raw):
            clamped = max(lo, min(hi, float(raw)))
            value_x = bar_x + int((clamped - lo) / (hi - lo) * bar_w)
            color = GREEN if value_x >= zero_x else RED
            draw.rounded_rectangle((min(zero_x, value_x), y + 12, max(zero_x, value_x), y + 34), radius=11, fill=color)
            draw.ellipse((value_x - 8, y + 8, value_x + 8, y + 38), fill=color)
        y += 66


def _page_overview(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("Dashboard Signals Report", "Plain-English guide to the methodology and the XLE Stage-2 example")
    y = 170
    draw.text((MARGIN, y), "What this dashboard is doing", font=FONTS["title"], fill=INK)
    y += 76
    y = _draw_wrapped(
        draw,
        "The dashboard ranks sectors, industries, factors, themes, countries, crypto exposures, defensive assets, and large stocks using a seven-pillar methodology. The output is a decision-support label, not a guarantee. It asks: which instruments have improving momentum, trend, rotation, macro context, and money-flow confirmation?",
        (MARGIN, y),
        font=FONTS["body"],
        width=PAGE_SIZE[0] - 2 * MARGIN,
        fill=INK,
    )
    y += 36
    _metric_card(draw, (MARGIN, y, MARGIN + 318, y + 170), "XLE state", inputs.xle.state.replace("_", " "), "Current cached dashboard snapshot.", GREEN)
    _metric_card(draw, (MARGIN + 350, y, MARGIN + 668, y + 170), "S score", _fmt_number(inputs.xle.s_score, 3, signed=True), "Composite score across the seven pillars.", BLUE)
    _metric_card(draw, (MARGIN + 700, y, MARGIN + 1018, y + 170), "F score", _fmt_number(inputs.xle.f_score, 3, signed=True), "Institutional-flow composite.", TEAL)
    y += 225
    _panel(draw, (MARGIN, y, PAGE_SIZE[0] - MARGIN, y + 420), "Forecast horizons by signal")
    horizons = [
        ("Flow", "1 to 3 weeks", "Confirms whether money is entering or leaving now."),
        ("RRG rotation", "4 to 12 weeks", "Shows whether relative strength and momentum are improving."),
        ("Stage 2 / trend", "4 to 26 weeks", "Identifies an established advance above a rising 30-week average."),
        ("Business-cycle tilt", "3 to 6 months", "Adds macro context for sector preference."),
    ]
    row_y = y + 80
    for label, horizon, text in horizons:
        draw.text((MARGIN + 28, row_y), label, font=FONTS["h2"], fill=INK)
        _pill(draw, (MARGIN + 280, row_y - 2), horizon, BLUE)
        _draw_wrapped(draw, text, (MARGIN + 500, row_y), font=FONTS["small"], width=520, fill=MUTED)
        row_y += 78
    y += 470
    disclaimer = "Important: This report is educational decision support. It is not financial advice, not a broker recommendation, and not a promise that the forecast will be right."
    _panel(draw, (MARGIN, y, PAGE_SIZE[0] - MARGIN, y + 130), "Plain-English disclaimer")
    _draw_wrapped(draw, disclaimer, (MARGIN + 28, y + 62), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=RED)
    draw.text((MARGIN, PAGE_SIZE[1] - 70), f"Generated {inputs.generated_at.date().isoformat()} | Data as of {inputs.xle.as_of}", font=FONTS["small"], fill=MUTED)
    return page


def _page_pillars(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("Seven Signal Pillars", "What each pillar means and which values are meaningful")
    pillars = [
        ("Momentum", "12-month return excluding the most recent month. Positive and rising is constructive."),
        ("Trend filters", "Faber 10-month and absolute momentum gates. Above the filter is healthier than below it."),
        ("Weinstein Stage", "Stage 2 means price is above a rising 30-week average with positive relative strength."),
        ("Dual momentum", "Compares the asset against safe T-bill exposure and its own trend."),
        ("RRG rotation", "Leading or Improving quadrants are constructive; Lagging is a warning."),
        ("Business-cycle tilt", "Macro phase can increase or reduce a sector's score."),
        ("Institutional flow", "CMF, OBV, ETF flow, block activity, volume, and short-interest pressure."),
    ]
    y = 170
    for idx, (name, text) in enumerate(pillars):
        x = MARGIN + (idx % 2) * 540
        if idx % 2 == 0 and idx:
            y += 148
        _panel(draw, (x, y, x + 500, y + 126))
        draw.text((x + 20, y + 18), name, font=FONTS["h2"], fill=INK)
        _draw_wrapped(draw, text, (x + 20, y + 56), font=FONTS["small"], width=450, fill=MUTED)
    y += 190
    _panel(draw, (MARGIN, y, PAGE_SIZE[0] - MARGIN, y + 520), "Meaningful values")
    rows = [
        ("S_score > 0", "Better than average composite evidence inside its asset class."),
        ("S_score >= +1.0", "Very strong composite reading; dashboard grade A."),
        ("S_score <= -1.5", "Very weak composite reading; dashboard grade F."),
        ("F_score > 0", "Flow backdrop is supportive."),
        ("F_score < -0.5 sigma", "Hard flow veto: ranking is killed even if price momentum looks good."),
        ("CMF21 > +0.05", "Accumulation pressure is strong enough for Stage-2 bullish gate."),
        ("Breadth >= 60%", "Enough of the last 50 sessions are above their 50-day average."),
        ("Mansfield RS > 0", "The instrument is outperforming the benchmark over the last year."),
    ]
    row_y = y + 76
    for idx, (threshold, meaning) in enumerate(rows):
        fill = "#FDFEFE" if idx % 2 == 0 else "#F3F8F6"
        draw.rectangle((MARGIN + 26, row_y - 8, PAGE_SIZE[0] - MARGIN - 26, row_y + 44), fill=fill)
        draw.text((MARGIN + 42, row_y), threshold, font=FONTS["small_bold"], fill=BLUE)
        _draw_wrapped(draw, meaning, (MARGIN + 330, row_y), font=FONTS["small"], width=660, fill=INK)
        row_y += 58
    y += 570
    _panel(draw, (MARGIN, y, PAGE_SIZE[0] - MARGIN, y + 160), "Macro context used in this report")
    draw.text((MARGIN + 28, y + 64), f"Current macro phase: {inputs.macro_phase}", font=FONTS["h2"], fill=PURPLE)
    _draw_wrapped(draw, inputs.macro_note, (MARGIN + 430, y + 62), font=FONTS["small"], width=570, fill=MUTED)
    return page


def _page_signal_deep_dive(inputs: ReportInputs, page_no: int) -> Image.Image:
    rows = build_signal_detail_rows(inputs.xle)
    if page_no == 1:
        selected = rows[:6]
        title = "Signal Deep Dive 1"
        subtitle = "Raw inputs, formulas, XLE values, and expected horizons"
    else:
        selected = rows[6:]
        title = "Signal Deep Dive 2"
        subtitle = "Flow, risk checks, and macro context"
    page, draw = _new_page(title, subtitle)
    _draw_signal_table(draw, selected, (MARGIN, 166, PAGE_SIZE[0] - MARGIN, 1060), "Detailed signal rows")
    _panel(draw, (MARGIN, 1104, PAGE_SIZE[0] - MARGIN, 1406), "How to read this table")
    text = (
        "Formula/input explains the mechanical calculation. XLE value is the current cached value used by the dashboard. "
        "Threshold is the line that usually changes the interpretation. Horizon is the rough time window where the signal is most useful. "
        "A bullish row is useful only when it agrees with the other pillars; one strong row alone is not enough."
    )
    _draw_wrapped(draw, text, (MARGIN + 28, 1172), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=INK)
    return page


def _page_xle(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("XLE Worked Example", "Why the dashboard labels XLE as Bullish Stage 2")
    xle = inputs.xle
    y = 168
    draw.text((MARGIN, y), "What Bullish Stage 2 means", font=FONTS["title"], fill=INK)
    y += 74
    y = _draw_wrapped(
        draw,
        "Bullish Stage 2 is the dashboard's strongest positive state. In plain English: XLE is in an established uptrend, is outperforming its benchmark, sits in the Leading RRG quadrant, has enough breadth confirmation, and has positive money-flow evidence. The expected horizon is roughly 4 to 26 weeks, but the signal still needs risk management.",
        (MARGIN, y),
        font=FONTS["body"],
        width=PAGE_SIZE[0] - 2 * MARGIN,
        fill=INK,
    )
    y += 28
    _draw_checklist(draw, build_stage2_checklist(xle), MARGIN, y, PAGE_SIZE[0] - 2 * MARGIN)
    y += 520
    _metric_card(draw, (MARGIN, y, MARGIN + 250, y + 150), "Rank", str(xle.rank_in_class or "n/a"), f"in {xle.asset_class}", BLUE)
    _metric_card(draw, (MARGIN + 272, y, MARGIN + 522, y + 150), "Selected", "YES" if xle.selected else "NO", "Included by class rank.", GREEN if xle.selected else MUTED)
    _metric_card(draw, (MARGIN + 544, y, MARGIN + 794, y + 150), "Veto", "NO" if not xle.veto else "YES", "Flow veto is not active.", GREEN if not xle.veto else RED)
    _metric_card(draw, (MARGIN + 816, y, MARGIN + 1066, y + 150), "Momentum", _fmt_pct(xle.mom_12_1, 1, signed=True), "12-1 momentum.", BLUE)
    y += 190
    _panel(draw, (MARGIN, y, PAGE_SIZE[0] - MARGIN, y + 190), "What to do / what not to assume")
    left = "Use this as a watchlist or position-management signal: compare XLE to your risk limits, stop plan, portfolio concentration, and broader market conditions."
    right = "Do not assume it means a guaranteed profit, an immediate buy at any price, or that the signal cannot reverse quickly if flow or trend breaks."
    _draw_wrapped(draw, left, (MARGIN + 28, y + 70), font=FONTS["small"], width=485, fill=INK)
    _draw_wrapped(draw, right, (MARGIN + 560, y + 70), font=FONTS["small"], width=485, fill=RED)
    return page


def _page_xle_calculations(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("XLE Calculation Trail", "The exact gates behind the Bullish Stage 2 label")
    _draw_calculation_table(
        draw,
        build_xle_calculation_rows(inputs.xle),
        (MARGIN, 166, PAGE_SIZE[0] - MARGIN, 1280),
        "Stage 2 and selection calculation",
    )
    _panel(draw, (MARGIN, 1324, PAGE_SIZE[0] - MARGIN, 1504), "Bottom line")
    text = (
        "XLE receives the Bullish Stage 2 label because the trend, relative strength, rotation, breadth, and money-flow gates pass together. "
        "If any of the strict bullish gates fails later, the label can step down to Hold, Warning, Exit, or Bearish Stage 4."
    )
    _draw_wrapped(draw, text, (MARGIN + 28, 1390), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=INK)
    return page


def _page_score_math(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("XLE Score Math", "How the weighted methodology score is assembled")
    _draw_score_contributions(draw, build_score_contribution_rows(inputs.xle), (MARGIN, 166, PAGE_SIZE[0] - MARGIN, 820))
    _panel(draw, (MARGIN, 862, PAGE_SIZE[0] - MARGIN, 1220), "Interpreting the S_score")
    rows = [
        ("S_score > 0", "Composite evidence is better than the peer-group average."),
        ("S_score >= +1.0", "A strong reading: multiple pillars agree at the same time."),
        ("F_score < -0.5", "Hard flow veto: the asset loses ranking eligibility even if price looks good."),
        ("Rank <= class target", "The asset is selected only if it ranks inside the class allocation target."),
    ]
    y = 932
    for label, meaning in rows:
        draw.text((MARGIN + 34, y), label, font=FONTS["small_bold"], fill=BLUE)
        _draw_wrapped(draw, meaning, (MARGIN + 330, y), font=FONTS["small"], width=650, fill=INK)
        y += 62
    _panel(draw, (MARGIN, 1260, PAGE_SIZE[0] - MARGIN, 1460), "Important nuance")
    nuance = (
        "The score math ranks XLE against peers in its asset class. A high score is not a price target. "
        "It means XLE's current evidence stack is stronger than most comparable instruments in the same dashboard universe."
    )
    _draw_wrapped(draw, nuance, (MARGIN + 28, 1328), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=MUTED)
    return page


def _page_flow_detail(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("XLE Flow Detail", "Shorter-horizon money-flow evidence behind the label")
    _draw_flow_components(draw, inputs.xle, (MARGIN, 166, PAGE_SIZE[0] - MARGIN, 842))
    _panel(draw, (MARGIN, 886, PAGE_SIZE[0] - MARGIN, 1190), "Flow interpretation")
    text = (
        "Flow is the dashboard's faster confirmation layer. It usually matters over one to three weeks, while the Stage 2 trend label can last longer. "
        "The current XLE flow stack is supportive because CMF21 is positive, the hard flow veto is not active, and the composite F_score is above zero."
    )
    _draw_wrapped(draw, text, (MARGIN + 28, 954), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=INK)
    _panel(draw, (MARGIN, 1234, PAGE_SIZE[0] - MARGIN, 1482), "What can invalidate the flow confirmation")
    invalidation = (
        "Watch for CMF21 falling below zero, ETF flow turning meaningfully negative, a block-up ratio below 0.7, rising distribution days, or a provider-flow z-score below -0.5. "
        "Those conditions can move a strong trend from Bullish to Warning or Exit."
    )
    _draw_wrapped(draw, invalidation, (MARGIN + 28, 1302), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=RED)
    return page


def _page_charts(inputs: ReportInputs) -> Image.Image:
    page, draw = _new_page("XLE Visuals", "Charts and diagrams behind the label")
    _draw_line_chart(draw, (MARGIN, 168, PAGE_SIZE[0] - MARGIN, 710), inputs.price_history)
    _draw_gauge(draw, (MARGIN, 750, MARGIN + 520, 930), "S_score composite gauge", inputs.xle.s_score, -2.0, 2.0, BLUE)
    _draw_gauge(draw, (MARGIN + 548, 750, PAGE_SIZE[0] - MARGIN, 930), "F_score flow gauge", inputs.xle.f_score, -2.0, 2.0, TEAL)
    _draw_gauge(draw, (MARGIN, 960, MARGIN + 520, 1140), "CMF21 accumulation gauge", inputs.xle.cmf21, -0.25, 0.25, GREEN)
    _draw_stage_lifecycle(draw, (MARGIN + 548, 960, PAGE_SIZE[0] - MARGIN, 1140), inputs.xle.stage)
    _panel(draw, (MARGIN, 1190, PAGE_SIZE[0] - MARGIN, 1450), "How to read the visuals")
    text = (
        "The price chart checks whether XLE is above its long-term trend line. "
        "The S-score gauge shows the combined methodology score versus peers. "
        "The F-score and CMF gauges focus on whether flow supports the price move. "
        "The lifecycle diagram shows that Stage 2 is the advancing phase, not the end of the full market cycle."
    )
    _draw_wrapped(draw, text, (MARGIN + 28, 1260), font=FONTS["body"], width=PAGE_SIZE[0] - 2 * MARGIN - 56, fill=INK)
    return page


def render_pdf(inputs: ReportInputs, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pages = [
        _page_overview(inputs),
        _page_pillars(inputs),
        _page_signal_deep_dive(inputs, 1),
        _page_signal_deep_dive(inputs, 2),
        _page_xle(inputs),
        _page_xle_calculations(inputs),
        _page_score_math(inputs),
        _page_flow_detail(inputs),
        _page_charts(inputs),
    ]
    pages[0].save(output_path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])


def _last_backtest_state(ticker: str = "XLE") -> tuple[str, str]:
    states_path = APP_ROOT / "docs/backtest_states.csv"
    if not states_path.exists():
        return "unknown", "UNKNOWN"
    states = pd.read_csv(states_path, index_col=0)
    if ticker not in states.columns or states.empty:
        return "unknown", "UNKNOWN"
    return str(states.index[-1]).split()[0], str(states[ticker].iloc[-1])


def _price_history(xle_frame: pd.DataFrame) -> list[PricePoint]:
    weekly = to_weekly(xle_frame)
    close = close_price(weekly)
    ma30 = close.rolling(30).mean()
    points = []
    for date, value in close.tail(60).items():
        ma_value = ma30.loc[date]
        points.append(
            PricePoint(
                date=pd.Timestamp(date).date().isoformat(),
                close=float(value),
                ma30w=None if pd.isna(ma_value) else float(ma_value),
            )
        )
    return points


def _z_value(series: pd.Series, ticker: str) -> float | None:
    clean = series.astype(float)
    std = clean.std(ddof=0)
    if std == 0 or pd.isna(std) or ticker not in clean.index:
        return None
    value = clean.loc[ticker]
    if pd.isna(value):
        return None
    return float((value - clean.mean()) / std)


def _snapshot_from_cache() -> ReportInputs:
    tickers = list(dict.fromkeys([*ALL_TICKERS, "^TNX", "^IRX"]))
    ohlcv = read_cached_ohlcv(tickers, period="3y", allow_stale=True)
    required = {"XLE", BENCH["US"], BENCH["TBILL"]}
    if not required.issubset(ohlcv):
        missing = ", ".join(sorted(required - set(ohlcv)))
        raise RuntimeError(f"cached OHLCV is missing required symbols: {missing}")

    indicators = compute_all_indicators(ohlcv, BENCH["US"], BENCH["TBILL"], max_workers=1)
    flow = compute_flow_signals(ohlcv)
    flow_z = flow_composite_z(flow)
    regime = assess_regime(ohlcv[BENCH["US"]], ohlcv.get("^TNX"), ohlcv.get("^IRX"), fred_cache={})
    scored = compute_composite(indicators, flow, flow_z, phase=regime.phase_hint)
    scored["state"] = [decide_state(row) for _, row in scored.iterrows()]
    xle_row = scored.loc["XLE"]
    class_rows = scored[scored["class"] == xle_row.get("class")]
    weekly = to_weekly(ohlcv["XLE"])
    close = close_price(weekly)
    ma30 = close.rolling(30).mean()
    ma30w_slope_5w = None
    if len(ma30) >= 6 and not pd.isna(ma30.iloc[-1]) and not pd.isna(ma30.iloc[-6]):
        ma30w_slope_5w = float((ma30.iloc[-1] - ma30.iloc[-6]) / 5.0)
    stage2_filter = 1.0 if _int_or_none(xle_row.get("stage")) == 2 else 0.0
    binary_filters_norm = (
        (float(xle_row.get("faber") or 0) + stage2_filter + float(xle_row.get("antonacci") or 0))
        / BINARY_FILTER_COUNT
    )
    as_of = pd.Timestamp(ohlcv["XLE"].index.max()).date().isoformat()
    snapshot = XleSnapshot(
        as_of=as_of,
        state=str(xle_row.get("state") or "UNKNOWN"),
        s_score=_float_or_none(xle_row.get("S_score")),
        f_score=_float_or_none(xle_row.get("F_score")),
        rank_in_class=_int_or_none(xle_row.get("rank_in_class")),
        selected=bool(xle_row.get("selected")),
        veto=bool(xle_row.get("veto")),
        stage=_int_or_none(xle_row.get("stage")),
        price=_float_or_none(close.iloc[-1]),
        ma30w=_float_or_none(ma30.iloc[-1]),
        above_30wma=_bool_or_none(xle_row.get("above_30wma")),
        ma_slope_pos=_bool_or_none(xle_row.get("ma_slope_pos")),
        mansfield_rs=_float_or_none(xle_row.get("mansfield_rs")),
        rrg_quadrant=str(xle_row.get("rrg_quadrant") or "n/a"),
        breadth_50d=_float_or_none(xle_row.get("breadth_50d")),
        cmf21=_float_or_none(xle_row.get("cmf21")),
        etf_flow_5d_pct=_float_or_none(xle_row.get("etf_flow_5d_pct")),
        block_up_ratio=_float_or_none(xle_row.get("block_up_ratio")),
        mom_12_1=_float_or_none(xle_row.get("mom_12_1")),
        asset_class=str(xle_row.get("class") or "US Sectors"),
        faber=_int_or_none(xle_row.get("faber")),
        antonacci=_int_or_none(xle_row.get("antonacci")),
        rs_ratio=_float_or_none(xle_row.get("rs_ratio")),
        rs_momentum=_float_or_none(xle_row.get("rs_momentum")),
        obv_slope=_float_or_none(xle_row.get("obv_slope")),
        mfi14=_float_or_none(xle_row.get("mfi14")),
        rvol=_float_or_none(xle_row.get("rvol")),
        dist_days_25=_int_or_none(xle_row.get("dist_days_25")),
        obv_divergence=_bool_or_none(xle_row.get("obv_divergence")),
        dark_pool_pct=_float_or_none(xle_row.get("dark_pool_pct")),
        si_delta_15d=_float_or_none(xle_row.get("si_delta_15d")),
        thirteen_f_q=_float_or_none(xle_row.get("thirteen_f_q")),
        top_n_target=_int_or_none(xle_row.get("top_n_target")),
        s_score_after_veto=_float_or_none(xle_row.get("S_score_after_veto")),
        cycle_tilt=_float_or_none(xle_row.get("cycle_tilt")),
        ma30w_slope_5w=ma30w_slope_5w,
        mom_12_1_z=_z_value(class_rows["mom_12_1"], "XLE"),
        mansfield_rs_z=_z_value(class_rows["mansfield_rs"], "XLE"),
        rs_ratio_z=_z_value(class_rows["rs_ratio"], "XLE"),
        rs_momentum_z=_z_value(class_rows["rs_momentum"], "XLE"),
        f_score_z=_z_value(class_rows["F_score"], "XLE"),
        binary_filters_norm=binary_filters_norm,
    )
    return ReportInputs(
        generated_at=datetime.now(timezone.utc),
        macro_phase=regime.phase_hint,
        macro_note=regime.note,
        xle=snapshot,
        price_history=_price_history(ohlcv["XLE"]),
    )


def _fallback_inputs() -> ReportInputs:
    as_of, state = _last_backtest_state("XLE")
    snapshot = XleSnapshot(
        as_of=as_of,
        state=state,
        s_score=None,
        f_score=None,
        rank_in_class=None,
        selected=False,
        veto=False,
        stage=2 if state == "STAGE_2_BULLISH" else None,
        price=None,
        ma30w=None,
        above_30wma=state == "STAGE_2_BULLISH",
        ma_slope_pos=state == "STAGE_2_BULLISH",
        mansfield_rs=None,
        rrg_quadrant="Leading" if state == "STAGE_2_BULLISH" else None,
        breadth_50d=None,
        cmf21=None,
        etf_flow_5d_pct=None,
        block_up_ratio=None,
        mom_12_1=None,
        asset_class="US Sectors",
        faber=None,
        antonacci=None,
        rs_ratio=None,
        rs_momentum=None,
        obv_slope=None,
        mfi14=None,
        rvol=None,
        dist_days_25=None,
        obv_divergence=None,
        dark_pool_pct=None,
        si_delta_15d=None,
        thirteen_f_q=None,
        top_n_target=None,
        s_score_after_veto=None,
        cycle_tilt=None,
        ma30w_slope_5w=None,
        mom_12_1_z=None,
        mansfield_rs_z=None,
        rs_ratio_z=None,
        rs_momentum_z=None,
        f_score_z=None,
        binary_filters_norm=None,
    )
    return ReportInputs(
        generated_at=datetime.now(timezone.utc),
        macro_phase="UNKNOWN",
        macro_note="Fallback report used committed backtest state artifact because cached OHLCV was unavailable.",
        xle=snapshot,
        price_history=[],
    )


def _float_or_none(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value) -> int | None:
    numeric = _float_or_none(value)
    return None if numeric is None else int(numeric)


def _bool_or_none(value) -> bool | None:
    if value is None or pd.isna(value):
        return None
    return bool(value)


def load_report_inputs() -> ReportInputs:
    try:
        return _snapshot_from_cache()
    except Exception:
        return _fallback_inputs()


def main() -> int:
    output_path = APP_ROOT / REPORT_PATH
    render_pdf(load_report_inputs(), output_path)
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
