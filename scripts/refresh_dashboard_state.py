"""Headless dashboard methodology refresh for Pi state/run persistence.

This script mirrors the app's pure compute path without importing Streamlit UI
code. It refreshes `state.json`, the transition journal, and the run journal so
the Pi keeps decision evidence even when nobody has a browser session open.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_resolver import resolve_config_value  # noqa: E402
from src.data import fetch_ohlcv_result, _select_ohlcv_provider  # noqa: E402
from src.flow import compute_flow_signals, flow_composite_z  # noqa: E402
from src.fred_data import fetch_fred, fred_available  # noqa: E402
from src.indicators import compute_all_indicators  # noqa: E402
from src.macro import assess_regime  # noqa: E402
from src.macro_tiles import MACRO_CONTEXT_SYMBOLS  # noqa: E402
from src.provider_flow_cache import read_provider_flow_cache  # noqa: E402
from src.run_journal import DEFAULT_JOURNAL_PATH, append_dashboard_run  # noqa: E402
from src.scoring import apply_state_machine, compute_composite, state_storage_health  # noqa: E402
from src.universe import ALL_TICKERS, BENCH  # noqa: E402


APP_VERSION = "2026.05.26-ux-hardening"
DATA_SYMBOLS = list(dict.fromkeys(ALL_TICKERS + list(MACRO_CONTEXT_SYMBOLS) + ["^TNX", "^IRX"]))
PROVIDER_FLOW_MODES = ("cache-only", "live", "stubbed")


def _bootstrap_runtime_config() -> None:
    for name in (
        "OHLCV_PROVIDER",
        "MASSIVE_API_KEY",
        "MASSIVE_VERIFY_SSL",
        "FRED_API_KEY",
        "PROVIDER_FLOW_CACHE_PATH",
        "MASSIVE_TRADES_STUB_MODE",
        "FINRA_ATS_STUB_MODE",
        "FINRA_SHORT_INTEREST_STUB_MODE",
        "FLOW_STUB_MODE",
        "SEC_13F_STUB_MODE",
    ):
        value = resolve_config_value(name, root=ROOT)
        if value:
            os.environ.setdefault(name, value)


def _current_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _finra_ats_params(limit: int) -> dict[str, Any]:
    fields = [
        "issueSymbolIdentifier",
        "weekStartDate",
        "summaryTypeCode",
        "totalWeeklyShareQuantity",
        "totalWeeklyTradeCount",
    ]
    return {
        "limit": int(limit),
        "fields": fields,
        "filters": [
            {
                "compareType": "EQUAL",
                "fieldName": "issueSymbolIdentifier",
                "fieldValue": "",
            }
        ],
    }


def _finra_short_params(limit: int) -> dict[str, Any]:
    fields = [
        "symbolCode",
        "settlementDate",
        "currentShortPositionQuantity",
        "previousShortPositionQuantity",
        "changePercent",
        "daysToCoverQuantity",
    ]
    return {
        "limit": int(limit),
        "fields": fields,
        "filters": [
            {
                "compareType": "EQUAL",
                "fieldName": "symbolCode",
                "fieldValue": "",
            }
        ],
    }


def _install_cache_only_provider_flow(allow_stale: bool) -> None:
    from src import flow

    flow.MASSIVE_TRADES_STUB_MODE = False
    flow.FINRA_ATS_STUB_MODE = False
    flow.FINRA_SHORT_INTEREST_STUB_MODE = False
    flow.ETF_PRIMARY_FLOW_STUB_MODE = True
    flow.SEC_13F_STUB_MODE = True

    def cache_fetch(provider: str, lane: str, ticker: str, params: dict, ttl_seconds: int) -> list[dict]:
        fresh = read_provider_flow_cache(
            provider=provider,
            lane=lane,
            ticker=ticker,
            params=params,
            ttl_seconds=ttl_seconds,
        )
        record = fresh
        source = "fresh_cache"
        if record is None and allow_stale:
            record = read_provider_flow_cache(
                provider=provider,
                lane=lane,
                ticker=ticker,
                params=params,
                ttl_seconds=ttl_seconds,
                allow_stale=True,
            )
            source = "stale_cache"
        if record is None:
            return []
        flow._remember_provider_fetch_source(lane, ticker, source=source, age_seconds=record.age_seconds)
        return record.payload

    def massive(ticker: str, start_date=None, end_date=None, limit: int = 5_000, timeout: int = 20) -> list[dict]:
        params = {
            "start_date": start_date or "",
            "end_date": end_date or "",
            "limit": int(limit),
            "sort": "timestamp",
            "order": "desc",
        }
        return cache_fetch(
            "massive",
            "massive_block_trades",
            ticker,
            params,
            flow.PROVIDER_FLOW_CACHE_TTL_SECONDS["massive_block_trades"],
        )

    def ats(ticker: str, limit: int = 40, timeout: int = 20) -> list[dict]:
        params = _finra_ats_params(limit)
        params["filters"][0]["fieldValue"] = str(ticker).upper()
        return cache_fetch(
            "finra",
            "finra_ats_dark_pool",
            ticker,
            params,
            flow.PROVIDER_FLOW_CACHE_TTL_SECONDS["finra_ats_dark_pool"],
        )

    def short(ticker: str, limit: int = 4, timeout: int = 20) -> list[dict]:
        params = _finra_short_params(limit)
        params["filters"][0]["fieldValue"] = str(ticker).upper()
        return cache_fetch(
            "finra",
            "finra_short_interest",
            ticker,
            params,
            flow.PROVIDER_FLOW_CACHE_TTL_SECONDS["finra_short_interest"],
        )

    flow._fetch_massive_stock_trades = massive
    flow._fetch_finra_ats_weekly_summary = ats
    flow._fetch_finra_short_interest = short


def _configure_provider_flow_mode(mode: str, *, allow_stale_cache: bool) -> None:
    from src import flow

    if mode == "cache-only":
        _install_cache_only_provider_flow(allow_stale_cache)
    elif mode == "stubbed":
        flow.MASSIVE_TRADES_STUB_MODE = True
        flow.FINRA_ATS_STUB_MODE = True
        flow.FINRA_SHORT_INTEREST_STUB_MODE = True
        flow.ETF_PRIMARY_FLOW_STUB_MODE = True
        flow.SEC_13F_STUB_MODE = True
    elif mode == "live":
        flow.MASSIVE_TRADES_STUB_MODE = False
        flow.FINRA_ATS_STUB_MODE = False
        flow.FINRA_SHORT_INTEREST_STUB_MODE = False
        flow.ETF_PRIMARY_FLOW_STUB_MODE = True
        flow.SEC_13F_STUB_MODE = True


def _load_fred_snapshot() -> dict:
    if not fred_available():
        return {}
    try:
        return fetch_fred()
    except Exception:
        return {}


def _build_bluf(scored_df):
    def rows_for(states: set[str], kind: str, label: str):
        sub = scored_df[scored_df["state"].isin(states)].sort_values("S_score", ascending=False)
        return {
            "kind": kind,
            "label": label,
            "state": ", ".join(sorted(states)),
            "tickers": [
                {
                    "t": str(ticker),
                    "note": f"state={row.get('state')}; S={float(row.get('S_score', 0.0)):.2f}; F={float(row.get('F_score', 0.0)):.2f}",
                }
                for ticker, row in sub.iterrows()
            ],
        }

    exit_rows = rows_for({"EXIT", "BEARISH_STAGE_4"}, "exit", "Exit or avoid")
    warn_rows = rows_for({"WARNING"}, "warn", "Watch")
    buy_rows = rows_for({"STAGE_2_BULLISH"}, "buy", "Bullish")
    return {
        "actions": [exit_rows, warn_rows, buy_rows],
        "exits_count": len(exit_rows["tickers"]),
        "warns_count": len(warn_rows["tickers"]),
        "buys_count": len(buy_rows["tickers"]),
    }


def refresh_dashboard_state(
    *,
    period: str,
    force_refresh: bool,
    provider_flow_mode: str,
    allow_stale_provider_cache: bool,
    journal_path: str | Path,
    dedupe_journal: bool,
) -> dict[str, Any]:
    _bootstrap_runtime_config()
    _configure_provider_flow_mode(provider_flow_mode, allow_stale_cache=allow_stale_provider_cache)
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ohlcv_result = fetch_ohlcv_result(DATA_SYMBOLS, period=period, force_refresh=force_refresh)
    ohlcv = ohlcv_result.data
    bench_ticker = BENCH["US"]
    bil_ticker = BENCH["TBILL"]
    if bench_ticker not in ohlcv or bil_ticker not in ohlcv:
        return {
            "ok": False,
            "error": "missing_required_market_data",
            "missing": sorted(set([bench_ticker, bil_ticker]) - set(ohlcv)),
        }
    scoring_ohlcv = {ticker: ohlcv[ticker] for ticker in ALL_TICKERS if ticker in ohlcv}
    indicators_df = compute_all_indicators(scoring_ohlcv, bench_ticker, bil_ticker)
    flow_df = compute_flow_signals(scoring_ohlcv)
    flow_z = flow_composite_z(flow_df)
    fred_snapshot = _load_fred_snapshot()
    regime = assess_regime(ohlcv[bench_ticker], ohlcv.get("^TNX"), ohlcv.get("^IRX"), fred_cache=fred_snapshot)
    scored = compute_composite(indicators_df, flow_df, flow_z, phase=regime.phase_hint)
    scored = apply_state_machine(scored)
    bluf = _build_bluf(scored)
    provider = str(getattr(ohlcv_result, "provider", "") or _select_ohlcv_provider(None))
    metadata = {
        "headless": True,
        "period": period,
        "phase": regime.phase_hint,
        "risk_on": regime.risk_on,
        "fred_used": regime.fred_used,
        "provider_flow_mode": provider_flow_mode,
        "allow_stale_provider_cache": allow_stale_provider_cache,
        "missing_ohlcv": sorted(set(DATA_SYMBOLS) - set(ohlcv)),
        "fresh_cache_hit_count": len(getattr(ohlcv_result, "fresh_cache_hits", ()) or ()),
        "stale_cache_hit_count": len(getattr(ohlcv_result, "stale_cache_hits", ()) or ()),
        "provider_warning_count": len(getattr(ohlcv_result, "warnings", ()) or ()),
        "cache_refresh_forced": bool(getattr(ohlcv_result, "cache_refresh_forced", False)),
    }
    journal_result = append_dashboard_run(
        journal_path,
        scored,
        bluf,
        started_at_utc=started_at,
        git_sha=_current_git_sha(),
        app_version=APP_VERSION,
        provider=provider,
        metadata=metadata,
        dedupe_content=dedupe_journal,
    )
    state_counts = {str(key): int(value) for key, value in scored["state"].value_counts().sort_index().items()}
    return {
        "ok": bool(journal_result.ok),
        "started_at_utc": started_at,
        "provider": provider,
        "period": period,
        "ticker_count": int(len(scored)),
        "state_counts": state_counts,
        "bluf_counts": {
            "exits": int(bluf["exits_count"]),
            "warnings": int(bluf["warns_count"]),
            "buys": int(bluf["buys_count"]),
        },
        "regime": {"phase": regime.phase_hint, "fred_used": bool(regime.fred_used)},
        "journal": {
            "ok": bool(journal_result.ok),
            "run_id": journal_result.run_id,
            "skipped_duplicate": bool(journal_result.skipped_duplicate),
            "error": journal_result.error,
        },
        "state_storage": state_storage_health(),
        "metadata": metadata,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="3y")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--journal-path", default=str(DEFAULT_JOURNAL_PATH))
    parser.add_argument("--no-journal-dedupe", action="store_true")
    parser.add_argument("--provider-flow-mode", choices=PROVIDER_FLOW_MODES, default="cache-only")
    parser.add_argument("--allow-stale-provider-cache", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = refresh_dashboard_state(
            period=args.period,
            force_refresh=bool(args.force_refresh),
            provider_flow_mode=args.provider_flow_mode,
            allow_stale_provider_cache=bool(args.allow_stale_provider_cache),
            journal_path=args.journal_path,
            dedupe_journal=not bool(args.no_journal_dedupe),
        )
    except Exception as exc:
        payload = {"ok": False, "error": type(exc).__name__}
    print(json.dumps(payload, sort_keys=True, default=str))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
