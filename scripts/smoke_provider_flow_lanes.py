"""Secret-safe live smoke checks for provider-flow lanes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import flow  # noqa: E402
from src.config_resolver import resolve_config_value  # noqa: E402


def _status_row(
    *,
    lane: str,
    provider: str,
    ticker: str,
    status: str,
    records: int | None = None,
    error: BaseException | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "lane": lane,
        "provider": provider,
        "ticker": ticker.upper(),
        "status": status,
    }
    if records is not None:
        row["records"] = int(records)
    if error is not None:
        row["error_type"] = type(error).__name__
    return row


def _smoke_fetch(
    *,
    lane: str,
    provider: str,
    ticker: str,
    fetcher: Callable[[], list[dict]],
) -> dict[str, object]:
    try:
        records = fetcher()
    except Exception as exc:
        return _status_row(lane=lane, provider=provider, ticker=ticker, status="failed", error=exc)
    return _status_row(
        lane=lane,
        provider=provider,
        ticker=ticker,
        status="ok",
        records=len(records) if isinstance(records, list) else 0,
    )


def smoke_provider_flow_lanes(
    tickers: list[str],
    *,
    timeout: int,
    limit: int,
    require_massive: bool = False,
) -> dict[str, object]:
    clean_tickers = list(dict.fromkeys(str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()))
    if not clean_tickers:
        clean_tickers = ["SPY"]
    massive_key = resolve_config_value("MASSIVE_API_KEY", root=ROOT)
    if massive_key:
        os.environ.setdefault("MASSIVE_API_KEY", massive_key)
    rows: list[dict[str, object]] = []
    for ticker in clean_tickers:
        if massive_key:
            rows.append(
                _smoke_fetch(
                    lane="massive_block_trades",
                    provider="Massive",
                    ticker=ticker,
                    fetcher=lambda ticker=ticker: flow._fetch_massive_stock_trades(
                        ticker,
                        limit=limit,
                        timeout=timeout,
                    ),
                )
            )
        else:
            rows.append(
                _status_row(
                    lane="massive_block_trades",
                    provider="Massive",
                    ticker=ticker,
                    status="missing_config" if require_massive else "skipped_missing_config",
                )
            )
        rows.append(
            _smoke_fetch(
                lane="finra_ats_dark_pool",
                provider="FINRA",
                ticker=ticker,
                fetcher=lambda ticker=ticker: flow._fetch_finra_ats_weekly_summary(
                    ticker,
                    limit=min(limit, 40),
                    timeout=timeout,
                ),
            )
        )
        rows.append(
            _smoke_fetch(
                lane="finra_short_interest",
                provider="FINRA",
                ticker=ticker,
                fetcher=lambda ticker=ticker: flow._fetch_finra_short_interest(
                    ticker,
                    limit=min(limit, 4),
                    timeout=timeout,
                ),
            )
        )
    failed = [row for row in rows if row["status"] == "failed"]
    missing_required = [
        row for row in rows if row["status"] == "missing_config"
    ]
    return {
        "ok": not failed and not missing_required,
        "ticker_count": len(clean_tickers),
        "rows": rows,
        "failed": len(failed),
        "missing_required": len(missing_required),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", default=[], help="Ticker to smoke. Repeatable.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--require-massive", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = smoke_provider_flow_lanes(
        args.ticker,
        timeout=args.timeout,
        limit=args.limit,
        require_massive=args.require_massive,
    )
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
