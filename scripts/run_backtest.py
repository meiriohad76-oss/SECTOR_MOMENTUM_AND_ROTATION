from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import backtest
from src.data import fetch_ohlcv


REPORT_PATH = ROOT / "docs" / "backtest_report.md"
EQUITY_PATH = ROOT / "docs" / "backtest_equity.csv"
METADATA_PATH = ROOT / "docs" / "backtest_metadata.json"
SECTOR_BENCHMARK_TICKERS = [
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLY",
    "XLP",
    "XLU",
    "XLB",
    "XLRE",
    "XLC",
]
REQUIRED_TICKERS = sorted({"AGG", "BIL", "SPY", *SECTOR_BENCHMARK_TICKERS})
DEFAULT_OHLCV_PROVIDER = "auto"
DEFAULT_LIVE_SMOKE_PERIOD = "2mo"


def _sha256_bytes(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _replace_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(path)


def _write_artifacts(
    report: str,
    equity,
    required_tickers: list[str],
    simulation_summary: dict | None = None,
) -> None:
    report_bytes = report.encode("utf-8")
    equity_csv = equity.to_csv()
    equity_bytes = equity_csv.encode("utf-8")
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report_sha256": _sha256_bytes(report_bytes),
        "equity_sha256": _sha256_bytes(equity_bytes),
        "required_tickers": required_tickers,
        "equity_rows": int(len(equity)),
        "equity_columns": list(equity.columns),
        "simulation_summary": simulation_summary or {},
    }

    metadata_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _replace_bytes(REPORT_PATH, report_bytes)
    _replace_bytes(EQUITY_PATH, equity_bytes)
    _replace_bytes(METADATA_PATH, metadata_bytes)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the B-011 manual backtest harness.")
    parser.add_argument(
        "--live-smoke",
        action="store_true",
        help="Fetch and validate live OHLCV only; skip the expensive historical simulation.",
    )
    parser.add_argument(
        "--smoke-period",
        default=DEFAULT_LIVE_SMOKE_PERIOD,
        help=f"Market-data period for --live-smoke (default: {DEFAULT_LIVE_SMOKE_PERIOD}).",
    )
    return parser


def _provider() -> str:
    return os.environ.get("OHLCV_PROVIDER", DEFAULT_OHLCV_PROVIDER)


def _download_prices(period: str, provider: str):
    ohlcv = fetch_ohlcv(REQUIRED_TICKERS, period=period, provider=provider)
    prices = backtest.close_matrix_from_ohlcv(ohlcv).loc["2003-01-01":]
    return ohlcv, prices


def _validate_required_prices(prices) -> list[str]:
    return sorted(set(REQUIRED_TICKERS).difference(prices.columns))


def _run_live_smoke(period: str) -> int:
    provider = _provider()
    try:
        _, prices = _download_prices(period=period, provider=provider)
    except Exception as exc:
        print(f"Manual backtest data download failed: {exc}")
        return 2
    missing = _validate_required_prices(prices)
    if missing:
        print(f"Missing required price data for manual backtest: {', '.join(missing)}")
        return 2
    print(
        f"Live backtest smoke passed for {len(REQUIRED_TICKERS)} tickers "
        f"with provider={provider} period={period}; artifacts were not written."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv or [])
    if args.live_smoke:
        return _run_live_smoke(args.smoke_period)
    try:
        ohlcv, prices = _download_prices(period="max", provider=_provider())
    except Exception as exc:
        print(f"Manual backtest data download failed: {exc}")
        return 2
    missing = _validate_required_prices(prices)
    if missing:
        print(f"Missing required price data for manual backtest: {', '.join(missing)}")
        return 2
    try:
        rebalance_dates = backtest.weekly_rebalance_dates(prices)
        methodology_targets = backtest.build_historical_methodology_targets(
            ohlcv,
            rebalance_dates=rebalance_dates,
            phase="MID",
        )
        strategy_columns = list(methodology_targets.target_weights.columns)
        if not strategy_columns:
            raise ValueError("methodology target builder produced no target columns")
        simulation_summary = backtest.historical_simulation_summary(methodology_targets)
        methodology_result = backtest.run_weight_backtest(
            prices[strategy_columns],
            methodology_targets.target_weights,
            transaction_cost_bps=5.0,
        )
        sixty_forty = backtest.sixty_forty_targets(rebalance_dates)
        sixty_forty_result = backtest.run_weight_backtest(
            prices[["AGG", "SPY"]],
            sixty_forty,
            transaction_cost_bps=5.0,
        )
        sector_targets = backtest.equal_weight_targets(rebalance_dates, SECTOR_BENCHMARK_TICKERS)
        sector_result = backtest.run_weight_backtest(
            prices[SECTOR_BENCHMARK_TICKERS],
            sector_targets,
            transaction_cost_bps=5.0,
        )
        methodology_windows = backtest.split_backtest_metrics(methodology_result)
        sixty_forty_windows = backtest.split_backtest_metrics(sixty_forty_result)
        sector_windows = backtest.split_backtest_metrics(sector_result)
        cost_scenarios = backtest.run_cost_scenarios(
            prices[strategy_columns],
            methodology_targets.target_weights,
            cost_bps_values=[3, 5, 10],
        )
        methodology_oos_metrics = methodology_windows["Out-of-sample"]
        sector_oos_metrics = sector_windows["Out-of-sample"]
        gates = backtest.evaluate_acceptance_gates(
            strategy_metrics={
                **methodology_oos_metrics,
                "state_transitions_per_ticker_year": simulation_summary[
                    "state_transitions_per_ticker_year"
                ],
            },
            equal_weight_metrics=sector_oos_metrics,
        )
        report = backtest.format_backtest_report(
            strategy_metrics=methodology_result.metrics,
            benchmark_metrics={
                "Methodology": methodology_result.metrics,
                "60/40 SPY/AGG": sixty_forty_result.metrics,
                "Equal-weight sectors": sector_result.metrics,
            },
            cost_scenarios=cost_scenarios,
            gates=gates,
            window_metrics={
                "Methodology full period": methodology_windows["Full period"],
                "Methodology in-sample": methodology_windows["In-sample"],
                "Methodology out-of-sample": methodology_oos_metrics,
                "60/40 out-of-sample": sixty_forty_windows["Out-of-sample"],
                "Equal-weight sectors out-of-sample": sector_oos_metrics,
            },
            simulation_summary=simulation_summary,
            title="Manual Backtest Smoke Report",
        )
        equity = backtest.equity_frame(
            {
                "Methodology": methodology_result,
                "60/40 SPY/AGG": sixty_forty_result,
                "Equal-weight sectors": sector_result,
            }
        )
        _write_artifacts(report, equity, REQUIRED_TICKERS, simulation_summary=simulation_summary)
    except Exception as exc:
        print(f"Manual backtest data validation failed: {exc}")
        return 2
    print(f"Wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
