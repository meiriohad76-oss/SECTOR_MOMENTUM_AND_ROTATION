from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import backtest
from src.data import fetch_ohlcv


REPORT_PATH = Path("docs/backtest_report.md")


def main() -> int:
    required = {"AGG", "SPY"}
    try:
        ohlcv = fetch_ohlcv(sorted(required), period="max")
        prices = backtest.close_matrix_from_ohlcv(ohlcv).loc["2003-01-01":]
    except Exception as exc:
        print(f"Manual backtest data download failed: {exc}")
        return 2
    missing = sorted(required.difference(prices.columns))
    if missing:
        print(f"Missing required price data for manual backtest: {', '.join(missing)}")
        return 2
    try:
        rebalance_dates = backtest.weekly_rebalance_dates(prices)
        sixty_forty = backtest.sixty_forty_targets(rebalance_dates)
        result = backtest.run_weight_backtest(
            prices[["AGG", "SPY"]],
            sixty_forty,
            transaction_cost_bps=5.0,
        )
        gates = backtest.evaluate_acceptance_gates(
            strategy_metrics={**result.metrics, "state_transitions_per_ticker_year": 0.0},
            equal_weight_metrics={"max_drawdown": result.metrics["max_drawdown"]},
        )
        REPORT_PATH.write_text(backtest.format_gate_report(gates), encoding="utf-8")
    except Exception as exc:
        print(f"Manual backtest data validation failed: {exc}")
        return 2
    print(f"Wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
