from __future__ import annotations

import argparse
from datetime import date, timedelta
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import flow
from src.config_resolver import resolve_config_value
from src.provider_snapshots import DEFAULT_SNAPSHOT_DB_PATH, upsert_provider_snapshot
from src.universe import ALL_TICKERS, SCORED_TICKERS, US_SECTORS


UNIVERSE_CHOICES = ("us-sectors", "scored", "dashboard", "all")


def _tickers_for_universe(name: str) -> list[str]:
    normalized = str(name).strip().lower()
    if normalized == "us-sectors":
        return list(US_SECTORS)
    if normalized in {"scored", "dashboard"}:
        return list(SCORED_TICKERS)
    if normalized == "all":
        return list(ALL_TICKERS)
    raise ValueError(f"unknown universe: {name}")


def _bootstrap_massive_secret() -> bool:
    token = resolve_config_value("MASSIVE_API_KEY", root=ROOT)
    if token:
        os.environ.setdefault("MASSIVE_API_KEY", token)
    return bool(os.environ.get("MASSIVE_API_KEY"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture Massive provider snapshots for later historical as-of replay."
    )
    parser.add_argument("--ticker", action="append", default=[], help="Ticker to capture. Repeat per ticker.")
    parser.add_argument(
        "--universe",
        action="append",
        choices=UNIVERSE_CHOICES,
        default=[],
        help=(
            "Ticker universe to capture. Repeatable. "
            "Use 'scored' or 'dashboard' for the dashboard matrix, 'all' to include benchmarks."
        ),
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Snapshot as-of date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_SNAPSHOT_DB_PATH),
        help=f"Snapshot SQLite path (default: {DEFAULT_SNAPSHOT_DB_PATH}).",
    )
    parser.add_argument("--limit", type=int, default=5_000, help="Maximum Massive trade rows per ticker.")
    parser.add_argument("--timeout", type=int, default=20, help="Provider request timeout in seconds.")
    return parser


def _fetch_massive_trades_for_snapshot(
    ticker: str,
    *,
    as_of: str,
    limit: int,
    timeout: int,
) -> list[dict]:
    end_date = (date.fromisoformat(as_of) + timedelta(days=1)).isoformat()
    return flow._fetch_massive_stock_trades(
        ticker,
        start_date=as_of,
        end_date=end_date,
        limit=limit,
        timeout=timeout,
    )


def _snapshot_payload(
    ticker: str,
    *,
    as_of: str,
    limit: int,
    trades: list[dict],
) -> dict:
    end_date = (date.fromisoformat(as_of) + timedelta(days=1)).isoformat()
    return {
        "source": "massive/v3/trades",
        "ticker": ticker,
        "as_of": as_of,
        "request": {
            "endpoint": flow.MASSIVE_STOCK_TRADES_URL_TEMPLATE,
            "ticker": ticker,
            "params": {
                "limit": int(limit),
                "order": "desc",
                "sort": "timestamp",
                "timestamp.gte": as_of,
                "timestamp.lt": end_date,
            },
        },
        "response": {
            "result_count": len(trades),
            "status": "captured",
        },
        "trades": trades,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv or [])
    tickers = [str(ticker).strip().upper() for ticker in args.ticker if str(ticker).strip()]
    for universe_name in args.universe:
        tickers.extend(_tickers_for_universe(universe_name))
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        print("No tickers were provided. Use --ticker or --universe.")
        return 2
    if not _bootstrap_massive_secret():
        print("Massive provider snapshot capture skipped: MASSIVE_API_KEY is not configured.")
        return 2
    try:
        for ticker in tickers:
            trades = _fetch_massive_trades_for_snapshot(
                ticker,
                as_of=args.as_of,
                limit=args.limit,
                timeout=args.timeout,
            )
            upsert_provider_snapshot(
                args.db_path,
                provider="massive",
                dataset="stock_trades",
                ticker=ticker,
                as_of=args.as_of,
                payload=_snapshot_payload(ticker, as_of=args.as_of, limit=args.limit, trades=trades),
            )
            print(
                f"Saved massive stock_trades snapshot for {ticker} "
                f"as_of={args.as_of} trades={len(trades)}"
            )
    except Exception:
        print("Massive provider snapshot capture failed.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
