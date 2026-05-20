from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import backtest
from src.data import fetch_ohlcv


REPORT_PATH = Path("docs/backtest_report.md")
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
REQUIRED_TICKERS = sorted({"AGG", "SPY", *SECTOR_BENCHMARK_TICKERS})


def main() -> int:
    try:
        ohlcv = fetch_ohlcv(REQUIRED_TICKERS, period="max")
        prices = backtest.close_matrix_from_ohlcv(ohlcv).loc["2003-01-01":]
    except Exception as exc:
        print(f"Manual backtest data download failed: {exc}")
        return 2
    missing = sorted(set(REQUIRED_TICKERS).difference(prices.columns))
    if missing:
        print(f"Missing required price data for manual backtest: {', '.join(missing)}")
        return 2
    try:
        rebalance_dates = backtest.weekly_rebalance_dates(prices)
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
        cost_scenarios = backtest.run_cost_scenarios(
            prices[["AGG", "SPY"]],
            sixty_forty,
            cost_bps_values=[3, 5, 10],
        )
        gates = backtest.evaluate_acceptance_gates(
            strategy_metrics={**sixty_forty_result.metrics, "state_transitions_per_ticker_year": 0.0},
            equal_weight_metrics=sector_result.metrics,
        )
        report = backtest.format_backtest_report(
            strategy_metrics=sixty_forty_result.metrics,
            benchmark_metrics={
                "60/40 SPY/AGG": sixty_forty_result.metrics,
                "Equal-weight sectors": sector_result.metrics,
            },
            cost_scenarios=cost_scenarios,
            gates=gates,
            title="Manual Backtest Smoke Report",
        )
        REPORT_PATH.write_text(report, encoding="utf-8")
    except Exception as exc:
        print(f"Manual backtest data validation failed: {exc}")
        return 2
    print(f"Wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
