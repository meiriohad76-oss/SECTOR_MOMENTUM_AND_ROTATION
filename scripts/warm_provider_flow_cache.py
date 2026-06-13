"""Warm cached Massive/FINRA provider-flow lanes for dashboard tickers.

This is an operational cache warmer, not a historical evidence collector. It
uses the same provider fetch functions as the dashboard so cache keys match the
live scoring path.
"""
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

from src.config_resolver import resolve_config_value  # noqa: E402
from src.provider_flow_cache import provider_flow_cache_status  # noqa: E402
from src.universe import ALL_TICKERS, SCORED_TICKERS, US_SECTORS  # noqa: E402


UNIVERSE_CHOICES = ("us-sectors", "scored", "dashboard", "all")
LANE_CHOICES = ("massive_block_trades", "finra_ats_dark_pool", "finra_short_interest")


def _tickers_for_universe(name: str) -> list[str]:
    normalized = str(name).strip().lower()
    if normalized == "us-sectors":
        return list(US_SECTORS)
    if normalized in {"scored", "dashboard"}:
        return list(SCORED_TICKERS)
    if normalized == "all":
        return list(ALL_TICKERS)
    raise ValueError(f"unknown universe: {name}")


def _bootstrap_runtime_config() -> None:
    for name in (
        "MASSIVE_API_KEY",
        "MASSIVE_VERIFY_SSL",
        "PROVIDER_FLOW_CACHE_PATH",
    ):
        value = resolve_config_value(name, root=ROOT)
        if value:
            os.environ.setdefault(name, value)


def _enable_live_cached_lanes(flow_module) -> None:
    flow_module.MASSIVE_TRADES_STUB_MODE = False
    flow_module.FINRA_ATS_STUB_MODE = False
    flow_module.FINRA_SHORT_INTEREST_STUB_MODE = False
    flow_module.SEC_13F_STUB_MODE = True
    flow_module.ETF_PRIMARY_FLOW_STUB_MODE = True


def _import_flow_module():
    from src import flow

    return flow


def _lane_fetchers(flow_module, *, massive_limit: int, finra_limit: int, timeout: int) -> dict[str, Callable[[str], list[dict]]]:
    return {
        "massive_block_trades": lambda ticker: flow_module._fetch_massive_stock_trades(
            ticker,
            limit=massive_limit,
            timeout=timeout,
        ),
        "finra_ats_dark_pool": lambda ticker: flow_module._fetch_finra_ats_weekly_summary(
            ticker,
            limit=finra_limit,
            timeout=timeout,
        ),
        "finra_short_interest": lambda ticker: flow_module._fetch_finra_short_interest(
            ticker,
            timeout=timeout,
        ),
    }


def _warm_tickers(
    tickers: list[str],
    *,
    lanes: list[str],
    massive_limit: int,
    finra_limit: int,
    timeout: int,
) -> dict[str, object]:
    _bootstrap_runtime_config()
    flow = _import_flow_module()

    _enable_live_cached_lanes(flow)
    fetchers = _lane_fetchers(flow, massive_limit=massive_limit, finra_limit=finra_limit, timeout=timeout)
    rows = []
    for ticker in tickers:
        for lane in lanes:
            try:
                records = fetchers[lane](ticker)
            except Exception as exc:
                rows.append(
                    {
                        "ticker": ticker,
                        "lane": lane,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "records": 0,
                    }
                )
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "lane": lane,
                    "status": "ok",
                    "records": len(records),
                }
            )
    failed = sum(1 for row in rows if row["status"] != "ok")
    return {
        "ok": failed == 0,
        "ticker_count": len(tickers),
        "lane_count": len(lanes),
        "requested": len(rows),
        "succeeded": len(rows) - failed,
        "failed": failed,
        "sample_rows": rows[:10],
        "cache": provider_flow_cache_status(),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", default=[], help="Ticker to warm. Repeat per ticker.")
    parser.add_argument(
        "--universe",
        action="append",
        choices=UNIVERSE_CHOICES,
        default=[],
        help="Ticker universe to warm. Defaults to 'scored' when no ticker/universe is supplied.",
    )
    parser.add_argument(
        "--lane",
        action="append",
        choices=LANE_CHOICES,
        default=[],
        help="Provider lane to warm. Repeatable. Defaults to all cached live Massive/FINRA lanes.",
    )
    parser.add_argument("--massive-limit", type=int, default=5_000)
    parser.add_argument("--finra-limit", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tickers = [str(ticker).strip().upper() for ticker in args.ticker if str(ticker).strip()]
    universes = args.universe or ([] if tickers else ["scored"])
    for universe_name in universes:
        tickers.extend(_tickers_for_universe(universe_name))
    tickers = list(dict.fromkeys(tickers))
    lanes = list(dict.fromkeys(args.lane or list(LANE_CHOICES)))
    if not tickers:
        print(json.dumps({"ok": False, "error": "no_tickers"}, sort_keys=True))
        return 2
    payload = _warm_tickers(
        tickers,
        lanes=lanes,
        massive_limit=args.massive_limit,
        finra_limit=args.finra_limit,
        timeout=args.timeout,
    )
    print(json.dumps(payload, sort_keys=True))
    if payload["failed"] == 0:
        return 0
    return 1 if payload["succeeded"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
