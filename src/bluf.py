"""Bottom-line-up-front summary for the dashboard.

Every sentence is produced by a fixed rule from the scoring output, so the
wording is stable and testable. Nothing here changes a score or a state; it
only summarizes them. Actions are labels (Review, Hold, Watch), not sizes.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SECTOR_MAP_PATH = Path(__file__).resolve().parents[1] / 'config' / 'ticker-sector-map.json'

ELIGIBLE_STATES = frozenset({"STAGE_2_BULLISH", "HOLD"})
ALERT_STATES = frozenset({"EXIT", "BEARISH_STAGE_4", "WARNING"})
TOP_N = 3


def _is_leading(row: Mapping[str, Any]) -> bool:
    return str(row.get("quadrant", "")).lower() == "leading"


def _eligible(row: Mapping[str, Any]) -> bool:
    return str(row.get("state", "")) in ELIGIBLE_STATES


def _sector_of(ticker: str, sector_map: Mapping[str, str], rows_by_ticker: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Sector ETF for a ticker: a sector ETF maps to itself; others use the map."""
    if ticker in rows_by_ticker and rows_by_ticker[ticker].get("asset_class") == "US Sectors":
        return ticker
    return sector_map.get(ticker)


def leading_sectors(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sectors = [r for r in rows if r.get("asset_class") == "US Sectors" and _is_leading(r) and _eligible(r)]
    return sorted(sectors, key=lambda r: float(r.get("s_score", 0.0)), reverse=True)


def top_leading_stocks(
    rows: Iterable[Mapping[str, Any]],
    sector_map: Mapping[str, str],
    top_n: int = TOP_N,
) -> list[dict[str, Any]]:
    """Top stocks by score that sit in a leading sector and are themselves eligible."""
    rows = list(rows)
    by_ticker = {str(r["ticker"]).upper(): r for r in rows}
    leaders = {str(r["ticker"]).upper() for r in leading_sectors(rows)}
    picks = []
    for row in rows:
        ticker = str(row["ticker"]).upper()
        if row.get("asset_class") == "US Sectors" or not _eligible(row):
            continue
        sector = _sector_of(ticker, sector_map, by_ticker)
        if sector in leaders:
            picks.append({**_summary(row), "sector": sector})
    picks.sort(key=lambda r: float(r.get("s_score", 0.0)), reverse=True)
    return picks[:top_n]


def _summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row["ticker"]).upper(),
        "state": row.get("state"),
        "s_score": float(row.get("s_score", 0.0)),
        "quadrant": row.get("quadrant"),
    }


def portfolio_view(
    rows: Iterable[Mapping[str, Any]],
    sector_map: Mapping[str, str],
    tickers: Sequence[str],
    leaders: set[str],
) -> list[dict[str, Any]]:
    """Each holding or watchlist ticker with its sector and whether that sector leads."""
    rows = list(rows)
    by_ticker = {str(r["ticker"]).upper(): r for r in rows}
    out = []
    for raw in tickers:
        ticker = str(raw).upper()
        sector = _sector_of(ticker, sector_map, by_ticker)
        row = by_ticker.get(ticker)
        out.append({
            "ticker": ticker,
            "sector": sector,
            "sector_leading": sector in leaders if sector else None,
            "state": row.get("state") if row else None,
            "s_score": float(row.get("s_score", 0.0)) if row else None,
            "scored": row is not None,
        })
    return out


def build_bluf(
    *,
    rows: Sequence[Mapping[str, Any]],
    sector_map: Mapping[str, str],
    holdings: Sequence[str],
    watchlist: Sequence[str],
    risk_on: bool | None,
    degraded: bool,
    flow_coverage: float | None,
    flow_ledger: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    leaders = leading_sectors(rows)
    leader_tickers = {str(r["ticker"]).upper() for r in leaders}
    top_stocks = top_leading_stocks(rows, sector_map)
    holding_view = portfolio_view(rows, sector_map, holdings, leader_tickers)
    watch_view = portfolio_view(rows, sector_map, watchlist, leader_tickers)

    buys = [r for r in rows if r.get("state") == "STAGE_2_BULLISH"]
    exits = [r for r in rows if r.get("state") == "EXIT"]
    alerts = [r for r in rows if r.get("state") in ALERT_STATES]

    conclusions: list[str] = []
    if risk_on is True:
        conclusions.append("Regime: risk-on (SPY above its 10-month average).")
    elif risk_on is False:
        conclusions.append("Regime: risk-off (SPY below its 10-month average).")
    if leaders:
        names = ", ".join(str(r["ticker"]) for r in leaders[:3])
        conclusions.append(f"Leading sectors: {names}.")
    else:
        conclusions.append("No sector is currently leading and eligible.")
    if buys:
        conclusions.append(f"{len(buys)} instruments are in Stage 2 (bullish).")
    else:
        conclusions.append("No instrument is in Stage 2 (bullish) this run.")
    if exits:
        conclusions.append(f"{len(exits)} instruments are in EXIT state.")
    if flow_ledger:
        top = flow_ledger[0]
        conclusions.append(f"Largest sector money move: {top['from']} to {top['to']}.")

    actions: list[str] = []
    for item in holding_view:
        if item["scored"] and item["state"] in ALERT_STATES:
            actions.append(f"Review {item['ticker']}: {item['state']}.")
        elif item["scored"] and item["state"] in ELIGIBLE_STATES:
            actions.append(f"Hold {item['ticker']}: {item['state']}.")
    for stock in top_stocks:
        actions.append(f"Watch {stock['ticker']}: leads {stock.get('sector')}, state {stock['state']}.")
    actions = actions[:3]

    if degraded:
        conclusions.insert(0, f"Data warning: degraded run, flow coverage {flow_coverage:.0%}." if flow_coverage is not None else "Data warning: degraded run.")

    return {
        "conclusions": conclusions,
        "actions": actions,
        "leading_sectors": [_summary(r) for r in leaders],
        "top_leading_stocks": top_stocks,
        "holdings": holding_view,
        "watchlist": watch_view,
        "alert_count": len(alerts),
        "degraded": degraded,
        "flow_coverage": flow_coverage,
    }


def load_sector_map(path: str | Path = SECTOR_MAP_PATH) -> dict[str, str]:
    """Ticker -> sector ETF map. A missing file gives an empty map, so tickers show as unmapped."""
    map_path = Path(path)
    if not map_path.exists():
        return {}
    data = json.loads(map_path.read_text(encoding='utf-8'))
    return {str(k).upper(): str(v).upper() for k, v in data.items()}
