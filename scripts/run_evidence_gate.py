"""Evidence gate runner — GATED ticket comparison and promotion review.

Compares baseline vs candidate configurations on historical price data and calls
``evaluate_promotion_gate()`` on each of the three CODEX GATED tickets:

  CODEX-4.3   Tiered transaction costs (``run_weight_backtest_tiered``)
  CODEX-1.3   Small-class z-score robustness (rank-pct fallback for n < 5)
  CODEX-2.4   Eligibility gate (``selection_mode="eligibility_then_rank"``)

Governance rule (safety.no_live_scoring_changes):
  Only tickets with ``ready_for_review`` status may proceed to a separate human-
  reviewed promotion patch.  This script never modifies ``DEFAULT_SCORING_CONFIG``,
  ``COMPOSITE_WEIGHTS``, ``FLOW_VETO``, ``STATE_MACHINE_THRESHOLDS``, or the
  10-year calibration baseline config.

Usage (from repo root)::

    python scripts/run_evidence_gate.py --period 10y
    python scripts/run_evidence_gate.py --period 5y --output docs/evidence_gate_report.md

Outputs
-------
* Console table of gate decisions.
* ``docs/evidence_gate_report.md`` (or path set by ``--output``).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.backtest import (
    TRADING_DAYS_PER_YEAR,
    BacktestResult,
    close_matrix_from_ohlcv,
    cost_tiers_by_ticker,
    filter_by_inception_date,
    load_inception_dates,
    max_drawdown,
    performance_metrics,
    run_weight_backtest,
    run_weight_backtest_tiered,
)
from src.config_resolver import resolve_config_value
from src.data import check_ops_readiness, fetch_ohlcv_result
from src.evidence_gates import (
    PromotionGateDecision,
    evaluate_promotion_gate,
    format_evidence_gate_report,
    promotion_gate_decisions_frame,
)
from src.universe import ALL_TICKERS

_log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bootstrap_env() -> None:
    """Populate os.environ from config files (mirrors refresh_dashboard_state)."""
    for name in (
        "OHLCV_PROVIDER",
        "MASSIVE_API_KEY",
        "MASSIVE_VERIFY_SSL",
        "FRED_API_KEY",
    ):
        value = resolve_config_value(name, root=ROOT)
        if value:
            os.environ.setdefault(name, value)


def _weekly_rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Every Friday (or last available trading day of each week) in *index*."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.resample("W-FRI").last().dropna().values)


def _equal_weight_targets(
    prices: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """1/N equal-weight DataFrame at each rebalance date (dates ⊆ prices.index)."""
    valid_dates = rebalance_dates[rebalance_dates.isin(prices.index)]
    if valid_dates.empty:
        raise ValueError("No rebalance dates fall within the prices index")
    n_valid = prices.loc[valid_dates].notna().sum(axis=1)
    weights = prices.loc[valid_dates].copy()
    for date in valid_dates:
        n = int(n_valid.loc[date])
        if n > 0:
            w = 1.0 / n
            weights.loc[date] = prices.loc[date].notna().astype(float) * w
        else:
            weights.loc[date] = 0.0
    return weights.fillna(0.0)


def _oos_start(prices: pd.DataFrame, oos_years: int = 1) -> pd.Timestamp:
    return pd.Timestamp(prices.index[-1]) - pd.DateOffset(years=oos_years)


def _split_backtest(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    oos_start_ts: pd.Timestamp,
) -> tuple[BacktestResult, BacktestResult]:
    """Run backtest separately on IS and OOS slices using equal weights.

    Returns (is_result, oos_result) for a flat 5-bps baseline.
    """
    is_prices  = prices[prices.index <= oos_start_ts]
    oos_prices = prices[prices.index > oos_start_ts]
    is_weights  = weights[weights.index <= oos_start_ts]
    oos_weights = weights[weights.index > oos_start_ts]

    is_result = run_weight_backtest(
        is_prices, is_weights, transaction_cost_bps=5.0
    ) if not is_prices.empty and not is_weights.empty else None

    oos_result = run_weight_backtest(
        oos_prices, oos_weights, transaction_cost_bps=5.0
    ) if not oos_prices.empty and not oos_weights.empty else None

    return is_result, oos_result  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Ticket CODEX-4.3: tiered transaction costs
# ---------------------------------------------------------------------------

_TIERED_COST_CRITERIA = {
    "min_oos_rebalances":   20,
    "min_oos_sharpe_delta": 0.10,
    "min_oos_cagr_delta":   0.0,
    "min_oos_dd_delta":     0.0,   # max_drawdown delta ≥ 0 means candidate is less negative
    "min_fullperiod_sharpe_delta": 0.0,
}

_TIERED_COST_NOTE = (
    "Tiered costs are a realism improvement, not a return-enhancement: they assign "
    "higher per-ticker bps to illiquid asset classes (crypto 40bps, themes 25bps, "
    "country ETFs 20bps vs flat 5bps for liquid sectors).  A tiered portfolio will "
    "therefore have LOWER net returns than a flat-5bps portfolio, so OOS Sharpe "
    "delta will be negative.  This is EXPECTED — the baseline was optimistic.  "
    "The gate will return blocked_no_candidates, which is correct: tiered costs are "
    "available for research via run_weight_backtest_tiered() but should not replace "
    "the default until a separate human-reviewed calibration confirms the new default "
    "is appropriate for the live universe."
)


def run_codex_4_3(
    prices: pd.DataFrame,
    *,
    report_path: str,
) -> PromotionGateDecision:
    """Run the CODEX-4.3 tiered-cost evidence gate."""
    _log.info("CODEX-4.3 — tiered transaction costs")

    oos_ts = _oos_start(prices, oos_years=1)
    oos_prices = prices[prices.index > oos_ts]

    if oos_prices.shape[0] < 50:
        return PromotionGateDecision(
            ticket="CODEX-4.3",
            source="run_evidence_gate.py",
            status="blocked_insufficient_data",
            validation_report_path=report_path,
            candidate_count=0,
            candidate_variants=(),
            rejected_variants=("tiered_costs",),
            blockers=(f"OOS window has only {oos_prices.shape[0]} rows (need ≥ 50)",),
        )

    rebal_dates_oos = _weekly_rebalance_dates(oos_prices.index)
    n_rebalances = int(len(rebal_dates_oos))

    if n_rebalances < _TIERED_COST_CRITERIA["min_oos_rebalances"]:
        return PromotionGateDecision(
            ticket="CODEX-4.3",
            source="run_evidence_gate.py",
            status="blocked_insufficient_data",
            validation_report_path=report_path,
            candidate_count=0,
            candidate_variants=(),
            rejected_variants=("tiered_costs",),
            blockers=(
                f"Only {n_rebalances} OOS rebalances "
                f"(need ≥ {_TIERED_COST_CRITERIA['min_oos_rebalances']})",
            ),
        )

    oos_weights = _equal_weight_targets(oos_prices, rebal_dates_oos)
    per_ticker_bps = cost_tiers_by_ticker(list(oos_prices.columns))

    baseline  = run_weight_backtest(oos_prices, oos_weights, transaction_cost_bps=5.0)
    candidate = run_weight_backtest_tiered(oos_prices, oos_weights, per_ticker_cost_bps=per_ticker_bps)

    oos_sharpe_delta  = candidate.metrics["sharpe"]      - baseline.metrics["sharpe"]
    oos_cagr_delta    = candidate.metrics["cagr"]        - baseline.metrics["cagr"]
    oos_dd_delta      = candidate.metrics["max_drawdown"] - baseline.metrics["max_drawdown"]

    # Full-period (IS+OOS) Sharpe comparison
    rebal_all = _weekly_rebalance_dates(prices.index)
    weights_all = _equal_weight_targets(prices, rebal_all)
    tickers_all = cost_tiers_by_ticker(list(prices.columns))
    fp_baseline  = run_weight_backtest(prices, weights_all, transaction_cost_bps=5.0)
    fp_candidate = run_weight_backtest_tiered(prices, weights_all, per_ticker_cost_bps=tickers_all)
    fp_sharpe_delta = fp_candidate.metrics["sharpe"] - fp_baseline.metrics["sharpe"]

    criteria_pass = [
        ("min_oos_rebalances",        n_rebalances >= _TIERED_COST_CRITERIA["min_oos_rebalances"]),
        ("min_oos_sharpe_delta",       oos_sharpe_delta   >= _TIERED_COST_CRITERIA["min_oos_sharpe_delta"]),
        ("min_oos_cagr_delta",         oos_cagr_delta     >= _TIERED_COST_CRITERIA["min_oos_cagr_delta"]),
        ("min_oos_dd_delta",           oos_dd_delta       >= _TIERED_COST_CRITERIA["min_oos_dd_delta"]),
        ("min_fullperiod_sharpe_delta", fp_sharpe_delta   >= _TIERED_COST_CRITERIA["min_fullperiod_sharpe_delta"]),
    ]
    passed_all = all(ok for _, ok in criteria_pass)
    promotion_label = "candidate" if passed_all else "rejected"

    summary = pd.DataFrame([{
        "variant":            "tiered_costs",
        "oos_rebalances":     n_rebalances,
        "baseline_sharpe":    round(baseline.metrics["sharpe"], 4),
        "candidate_sharpe":   round(candidate.metrics["sharpe"], 4),
        "oos_sharpe_delta":   round(oos_sharpe_delta, 4),
        "oos_cagr_delta":     round(oos_cagr_delta, 4),
        "oos_dd_delta":       round(oos_dd_delta, 4),
        "fp_sharpe_delta":    round(fp_sharpe_delta, 4),
        "note":               _TIERED_COST_NOTE[:120] + "…",
        "promotion_label":    promotion_label,
    }])

    _log.info(
        "CODEX-4.3 metrics | oos_sharpe_delta=%.4f  oos_cagr_delta=%.4f  "
        "oos_dd_delta=%.4f  fp_sharpe_delta=%.4f  rebalances=%d  label=%s",
        oos_sharpe_delta, oos_cagr_delta, oos_dd_delta, fp_sharpe_delta,
        n_rebalances, promotion_label,
    )

    return evaluate_promotion_gate(
        ticket="CODEX-4.3",
        source="run_evidence_gate.py — tiered cost equal-weight OOS",
        summary=summary,
        validation_report_path=report_path,
    )


# ---------------------------------------------------------------------------
# Ticket CODEX-1.3: small-class z-score robustness (rank-pct fallback)
# Ticket CODEX-2.4: eligibility gate (selection_mode="eligibility_then_rank")
# ---------------------------------------------------------------------------

def _needs_walk_forward_decision(
    ticket: str,
    report_path: str,
    reason: str,
) -> PromotionGateDecision:
    """Return a blocked gate for a ticket that requires walk-forward scoring data."""
    summary = pd.DataFrame([{
        "variant":         ticket.lower().replace("-", "_"),
        "note":            reason,
        "promotion_label": "needs_walk_forward",   # intentionally not "candidate"
    }])
    return evaluate_promotion_gate(
        ticket=ticket,
        source="run_evidence_gate.py",
        summary=summary,
        validation_report_path=report_path,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--period",
        default="10y",
        help="Historical OHLCV window (default: 10y)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "evidence_gate_report.md"),
        help="Output path for the gate report (default: docs/evidence_gate_report.md)",
    )
    parser.add_argument(
        "--skip-ops-check",
        action="store_true",
        help="Skip check_ops_readiness() (useful in CI without SSL config)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = str(args.output)

    _bootstrap_env()
    if not args.skip_ops_check:
        try:
            check_ops_readiness()
        except AssertionError as exc:
            _log.warning("ops_readiness_failed: %s  (use --skip-ops-check to bypass)", exc)
            # Continue: evidence gate is research-only, not production

    _log.info("Fetching OHLCV data — period=%s", args.period)
    result = fetch_ohlcv_result(ALL_TICKERS, period=args.period)
    if not result.data:
        _log.error("No OHLCV data returned — aborting")
        return 2

    prices_raw = close_matrix_from_ohlcv(result.data)
    if prices_raw.empty:
        _log.error("close_matrix_from_ohlcv returned an empty DataFrame — aborting")
        return 2

    inception_dates = load_inception_dates()
    prices = filter_by_inception_date(prices_raw, inception_dates)
    _log.info(
        "Prices ready: %d rows × %d tickers  (inception-gate applied to %d tickers)",
        prices.shape[0], prices.shape[1], len(inception_dates),
    )

    generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # --- Run each gate ---
    decisions: list[PromotionGateDecision] = []

    decisions.append(run_codex_4_3(prices, report_path=output_path))

    decisions.append(
        _needs_walk_forward_decision(
            ticket="CODEX-1.3",
            report_path=output_path,
            reason=(
                "Small-class z-score robustness (rank-pct fallback for n < min_class_size_for_z). "
                "Promotion evidence requires a full walk-forward scoring pipeline: run score snapshots "
                "for each rebalance date under both ScoringConfig(min_class_size_for_z=0) and "
                "ScoringConfig(min_class_size_for_z=5, z_ddof=1), compare OOS rank-IC and hit-rate, "
                "then resubmit this gate with the resulting summary DataFrame."
            ),
        )
    )

    decisions.append(
        _needs_walk_forward_decision(
            ticket="CODEX-2.4",
            report_path=output_path,
            reason=(
                "Eligibility gate (selection_mode='eligibility_then_rank'). "
                "Promotion evidence requires a full walk-forward scoring pipeline: run score snapshots "
                "under both 'score_only' and 'eligibility_then_rank', compare OOS Sharpe, CAGR, and "
                "drawdown for an equal-weight top-N portfolio, then resubmit this gate with the "
                "resulting summary DataFrame."
            ),
        )
    )

    # --- Print table ---
    frame = promotion_gate_decisions_frame(decisions)
    _log.info("\n\n%s\n", frame.to_string(index=False))

    # --- Write report ---
    report_text = format_evidence_gate_report(decisions, generated_at_utc=generated_at_utc)
    Path(output_path).write_text(report_text, encoding="utf-8")
    _log.info("Gate report written → %s", output_path)

    blocked = sum(1 for d in decisions if d.status != "ready_for_review")
    ready   = sum(1 for d in decisions if d.status == "ready_for_review")
    _log.info("Summary: %d ready_for_review  /  %d blocked", ready, blocked)

    if ready > 0:
        _log.warning(
            "ACTION REQUIRED: %d ticket(s) cleared the evidence gate. "
            "A human-reviewed promotion patch is needed before DEFAULT_SCORING_CONFIG "
            "or any live config is changed.",
            ready,
        )

    return 0 if ready == 0 else 1  # exit 1 when tickets need human review


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
