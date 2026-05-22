from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import flow
from src.provider_snapshots import DEFAULT_SNAPSHOT_DB_PATH, upsert_provider_snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture Massive provider snapshots for later historical as-of replay."
    )
    parser.add_argument("--ticker", action="append", required=True, help="Ticker to capture. Repeat per ticker.")
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv or [])
    tickers = [str(ticker).strip().upper() for ticker in args.ticker if str(ticker).strip()]
    if not tickers:
        print("No tickers were provided.")
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
                payload={
                    "source": "massive/v3/trades",
                    "ticker": ticker,
                    "as_of": args.as_of,
                    "trades": trades,
                },
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
