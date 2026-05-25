"""Local position P&L helpers for B-131."""
from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from .portfolio import HoldingInput


@dataclass(frozen=True)
class PnlRow:
    ticker: str
    shares: float | None
    cost_basis: float | None
    current_price: float | None
    cost: float | None
    current_value: float | None
    unrealized_pnl: float | None
    unrealized_pct: float | None
    missing_reason: str | None = None


@dataclass(frozen=True)
class PnlAnalysis:
    rows: list[PnlRow]
    total_cost: float
    total_value: float
    unrealized_pnl: float
    unrealized_pct: float | None
    missing_tickers: list[str]


def latest_prices_from_ohlcv(ohlcv: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Extract the last finite close for each loaded ticker."""
    prices: dict[str, float] = {}
    for ticker, frame in ohlcv.items():
        if frame is None or "close" not in frame:
            continue
        closes = pd.to_numeric(frame["close"], errors="coerce").dropna()
        if closes.empty:
            continue
        price = float(closes.iloc[-1])
        if math.isfinite(price) and price > 0:
            prices[str(ticker).upper()] = price
    return prices


def analyze_position_pnl(
    holdings: list[HoldingInput],
    latest_prices: dict[str, float],
) -> PnlAnalysis:
    """Compute local unrealized P&L from holdings plus loaded prices."""
    rows: list[PnlRow] = []
    total_cost = 0.0
    total_value = 0.0
    missing_tickers: list[str] = []

    for holding in holdings:
        row = _pnl_row(holding, latest_prices)
        rows.append(row)
        if row.missing_reason is not None:
            missing_tickers.append(row.ticker)
            continue
        total_cost += float(row.cost or 0.0)
        total_value += float(row.current_value or 0.0)

    unrealized = total_value - total_cost
    unrealized_pct = (unrealized / total_cost) if total_cost > 0 else None
    return PnlAnalysis(
        rows=rows,
        total_cost=total_cost,
        total_value=total_value,
        unrealized_pnl=unrealized,
        unrealized_pct=unrealized_pct,
        missing_tickers=missing_tickers,
    )


def pnl_rows_frame(analysis: PnlAnalysis) -> pd.DataFrame:
    rows = []
    for row in analysis.rows:
        rows.append(
            {
                "Ticker": row.ticker,
                "Shares": _fmt_number(row.shares),
                "Cost": _fmt_money(row.cost),
                "Value": _fmt_money(row.current_value),
                "P&L": _fmt_money(row.unrealized_pnl),
                "P&L %": _fmt_pct(row.unrealized_pct),
                "Status": row.missing_reason or "OK",
            }
        )
    return pd.DataFrame(rows, columns=["Ticker", "Shares", "Cost", "Value", "P&L", "P&L %", "Status"])


def pnl_summary_frame(analysis: PnlAnalysis) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Metric": "Cost", "Value": _fmt_money(analysis.total_cost)},
            {"Metric": "Value", "Value": _fmt_money(analysis.total_value)},
            {"Metric": "Unrealized P&L", "Value": _fmt_money(analysis.unrealized_pnl)},
            {"Metric": "Unrealized P&L %", "Value": _fmt_pct(analysis.unrealized_pct)},
        ]
    )


def _pnl_row(holding: HoldingInput, latest_prices: dict[str, float]) -> PnlRow:
    ticker = holding.ticker.upper()
    shares = _positive(holding.shares)
    if shares is None:
        return _missing(holding, "shares missing")
    cost_basis = _positive(holding.cost_basis)
    if cost_basis is None:
        return _missing(holding, "cost basis missing")

    price = _positive(latest_prices.get(ticker))
    current_value = None
    if price is not None:
        current_value = shares * price
    elif _positive(holding.market_value) is not None:
        current_value = float(holding.market_value or 0.0)
        price = current_value / shares
    else:
        return _missing(holding, "current price missing")

    cost = shares * cost_basis
    pnl = current_value - cost
    return PnlRow(
        ticker=ticker,
        shares=shares,
        cost_basis=cost_basis,
        current_price=price,
        cost=cost,
        current_value=current_value,
        unrealized_pnl=pnl,
        unrealized_pct=pnl / cost if cost > 0 else None,
    )


def _missing(holding: HoldingInput, reason: str) -> PnlRow:
    return PnlRow(
        ticker=holding.ticker.upper(),
        shares=holding.shares,
        cost_basis=holding.cost_basis,
        current_price=None,
        cost=None,
        current_value=None,
        unrealized_pnl=None,
        unrealized_pct=None,
        missing_reason=reason,
    )


def _positive(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.2f}"


def _fmt_number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"
