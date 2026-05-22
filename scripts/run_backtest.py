from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import backtest
from src.data import _select_ohlcv_provider, fetch_ohlcv, fetch_ohlcv_result
from src.fred_data import fetch_fred


REPORT_PATH = ROOT / "docs" / "backtest_report.md"
METHODOLOGY_REPORT_PATH = ROOT / "docs" / "backtest_methodology_report.md"
EQUITY_PATH = ROOT / "docs" / "backtest_equity.csv"
STATES_PATH = ROOT / "docs" / "backtest_states.csv"
METADATA_PATH = ROOT / "docs" / "backtest_metadata.json"
FRED_VALIDATION_REPORT_PATH = ROOT / "docs" / "fred_macro_validation_report.md"
FRED_VALIDATION_SUMMARY_PATH = ROOT / "docs" / "fred_macro_validation_summary.csv"
MASSIVE_VALIDATION_REPORT_PATH = ROOT / "docs" / "massive_provider_validation_report.md"
MASSIVE_VALIDATION_SUMMARY_PATH = ROOT / "docs" / "massive_provider_validation_summary.csv"
MASSIVE_AGGS_ENDPOINT = "https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}"
MASSIVE_TRADES_ENDPOINT = "https://api.massive.com/v3/trades/{ticker}"
MASSIVE_BLOCK_TRADE_THRESHOLDS = (1.0, 1.25, 1.5)
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
MACRO_VARIANT_RULES = (
    backtest.MacroVariantRule(
        name="Curve falling defensive",
        series_id="T10Y2Y",
        condition="falling",
        exposure_multiplier=0.0,
        availability_lag_days=1,
    ),
    backtest.MacroVariantRule(
        name="HY spread rising defensive",
        series_id="BAMLH0A0HYM2",
        condition="rising",
        exposure_multiplier=0.0,
        availability_lag_days=1,
    ),
    backtest.MacroVariantRule(
        name="Stress rising defensive",
        series_id="STLFSI4",
        condition="rising",
        exposure_multiplier=0.0,
        availability_lag_days=7,
    ),
)


def _sha256_bytes(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _replace_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(path)


def _stage_artifacts(payloads: dict[Path, bytes]) -> list[tuple[Path, Path]]:
    staged = []
    try:
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(path.name + ".tmp")
            tmp_path.write_bytes(payload)
            staged.append((tmp_path, path))
    except Exception:
        for tmp_path, _ in staged:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        raise
    return staged


def _replace_staged_artifacts(staged: list[tuple[Path, Path]]) -> None:
    for tmp_path, path in staged:
        tmp_path.replace(path)


def _write_artifacts(
    report: str,
    methodology_report: str,
    equity,
    states,
    required_tickers: list[str],
    simulation_summary: dict | None = None,
    macro_variant_summary=None,
    fred_validation_report: str | None = None,
    fred_validation_summary=None,
    massive_validation_report: str | None = None,
    massive_validation_summary=None,
    ohlcv_source: dict | None = None,
) -> None:
    report_bytes = report.encode("utf-8")
    methodology_report_bytes = methodology_report.encode("utf-8")
    equity_csv = equity.to_csv()
    equity_bytes = equity_csv.encode("utf-8")
    states_csv = states.to_csv()
    states_bytes = states_csv.encode("utf-8")
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report_sha256": _sha256_bytes(report_bytes),
        "methodology_report_sha256": _sha256_bytes(methodology_report_bytes),
        "equity_sha256": _sha256_bytes(equity_bytes),
        "states_sha256": _sha256_bytes(states_bytes),
        "required_tickers": required_tickers,
        "equity_rows": int(len(equity)),
        "equity_columns": list(equity.columns),
        "states_rows": int(len(states)),
        "states_columns": list(states.columns),
        "simulation_summary": simulation_summary or {},
        "macro_variant_summary": _frame_records(macro_variant_summary),
        "massive_validation_summary": _frame_records(massive_validation_summary),
        "ohlcv_source": ohlcv_source or {},
    }
    payloads = {
        REPORT_PATH: report_bytes,
        METHODOLOGY_REPORT_PATH: methodology_report_bytes,
        EQUITY_PATH: equity_bytes,
        STATES_PATH: states_bytes,
    }
    if fred_validation_report is not None:
        fred_validation_report_bytes = fred_validation_report.encode("utf-8")
        payloads[FRED_VALIDATION_REPORT_PATH] = fred_validation_report_bytes
        metadata["fred_validation_report_sha256"] = _sha256_bytes(fred_validation_report_bytes)
    if fred_validation_summary is not None:
        fred_validation_summary_bytes = fred_validation_summary.to_csv(index=False).encode("utf-8")
        payloads[FRED_VALIDATION_SUMMARY_PATH] = fred_validation_summary_bytes
        metadata["fred_validation_summary_sha256"] = _sha256_bytes(fred_validation_summary_bytes)
    if massive_validation_report is not None:
        massive_validation_report_bytes = massive_validation_report.encode("utf-8")
        payloads[MASSIVE_VALIDATION_REPORT_PATH] = massive_validation_report_bytes
        metadata["massive_validation_report_sha256"] = _sha256_bytes(massive_validation_report_bytes)
    if massive_validation_summary is not None:
        massive_validation_summary_bytes = massive_validation_summary.to_csv(index=False).encode("utf-8")
        payloads[MASSIVE_VALIDATION_SUMMARY_PATH] = massive_validation_summary_bytes
        metadata["massive_validation_summary_sha256"] = _sha256_bytes(massive_validation_summary_bytes)
    metadata_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    payloads[METADATA_PATH] = metadata_bytes
    staged = _stage_artifacts(payloads)
    _replace_staged_artifacts(staged)


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
    parser.add_argument(
        "--macro-variants",
        action="store_true",
        help="Fetch FRED and include analysis-only macro-conditioned exposure variants in the report.",
    )
    parser.add_argument(
        "--massive-variants",
        action="store_true",
        help="Compare default/yfinance and Massive historical provider data in a research-only report.",
    )
    return parser


def _provider() -> str:
    return os.environ.get("OHLCV_PROVIDER", DEFAULT_OHLCV_PROVIDER)


def _frame_records(frame) -> list[dict]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return json.loads(frame.to_json(orient="records"))


def _resolve_validation_split(
    target_index,
    preferred_oos_start: str = "2015-01-01",
    min_side_rebalances: int = 20,
    fallback_fraction: float = 0.70,
) -> tuple[pd.Timestamp, str]:
    dates = pd.DatetimeIndex(pd.to_datetime(target_index)).dropna().sort_values().unique()
    preferred = pd.Timestamp(preferred_oos_start)
    if len(dates) == 0:
        return preferred, "configured split unavailable because there are no rebalances"
    in_sample_count = int((dates < preferred).sum())
    oos_count = int((dates >= preferred).sum())
    if in_sample_count >= min_side_rebalances and oos_count >= min_side_rebalances:
        return preferred, f"configured OOS start with {in_sample_count} in-sample and {oos_count} OOS rebalances"
    if len(dates) >= min_side_rebalances * 2:
        raw_position = int(len(dates) * fallback_fraction)
        position = min(max(raw_position, min_side_rebalances), len(dates) - min_side_rebalances)
        split = pd.Timestamp(dates[position])
        return (
            split,
            (
                "walk-forward fallback because configured OOS start would leave "
                f"{in_sample_count} in-sample and {oos_count} OOS rebalances"
            ),
        )
    return (
        preferred,
        (
            "configured split retained but validation sample is thin "
            f"({in_sample_count} in-sample, {oos_count} OOS rebalances)"
        ),
    )


def _fetch_macro_data(enabled: bool) -> dict[str, pd.Series]:
    if not enabled:
        return {}
    return fetch_fred(start_date="2003-01-01")


def _build_macro_variant_summary(*, enabled: bool, prices, target_weights, macro_data=None, oos_start="2015-01-01"):
    if not enabled:
        return pd.DataFrame()
    fred_data = macro_data if macro_data is not None else _fetch_macro_data(enabled=True)
    if not fred_data:
        return pd.DataFrame()
    return backtest.evaluate_macro_condition_variants(
        prices,
        target_weights,
        fred_data,
        rules=MACRO_VARIANT_RULES,
        transaction_cost_bps=5.0,
        oos_start=oos_start,
    )


def _provider_endpoint(provider: str) -> str:
    return MASSIVE_AGGS_ENDPOINT if provider == "massive" else "yfinance.download"


def _coverage_by_ticker(ohlcv: dict[str, pd.DataFrame]) -> str:
    parts = []
    for ticker in REQUIRED_TICKERS:
        frame = ohlcv.get(ticker)
        if frame is None:
            frame = ohlcv.get(str(ticker).upper())
        if frame is None or frame.empty:
            parts.append(f"{ticker}:-")
            continue
        start, end, count = _index_window(frame.index)
        parts.append(f"{ticker}:{start}->{end}({count})")
    return "; ".join(parts)


def _empty_provider_validation_row(provider: str, status: str, notes: str) -> dict:
    return {
        "row_type": "provider_comparison",
        "variant": "Massive aggregate OHLCV" if provider == "massive" else "Default/yfinance OHLCV baseline",
        "provider": provider,
        "endpoint": _provider_endpoint(provider),
        "status": status,
        "coverage_start": "-",
        "coverage_end": "-",
        "coverage_rows": 0,
        "ticker_count": 0,
        "missing_count": len(REQUIRED_TICKERS),
        "missing_tickers": ", ".join(REQUIRED_TICKERS),
        "coverage_by_ticker": "",
        "cagr": None,
        "sharpe": None,
        "max_drawdown": None,
        "annualized_turnover": None,
        "oos_cagr": None,
        "oos_sharpe": None,
        "oos_max_drawdown": None,
        "oos_annualized_turnover": None,
        "cagr_delta_vs_yfinance": None,
        "sharpe_delta_vs_yfinance": None,
        "max_drawdown_delta_vs_yfinance": None,
        "oos_cagr_delta_vs_yfinance": None,
        "oos_sharpe_delta_vs_yfinance": None,
        "oos_max_drawdown_delta_vs_yfinance": None,
        "threshold": None,
        "promotion_label": "needs more testing",
        "notes": notes,
    }


def _provider_validation_row_from_backtest(
    *,
    provider: str,
    ohlcv: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    result: backtest.BacktestResult,
    oos_start: str | pd.Timestamp,
    notes: str,
) -> dict:
    windows = backtest.split_backtest_metrics(result, oos_start=oos_start)
    oos_metrics = windows["Out-of-sample"]
    coverage_start, coverage_end, coverage_rows = _index_window(prices.index)
    missing = _validate_required_prices(prices)
    return {
        "row_type": "provider_comparison",
        "variant": "Massive aggregate OHLCV" if provider == "massive" else "Default/yfinance OHLCV baseline",
        "provider": provider,
        "endpoint": _provider_endpoint(provider),
        "status": "available" if not missing else "missing_required_prices",
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "coverage_rows": int(coverage_rows),
        "ticker_count": int(len(prices.columns)),
        "missing_count": int(len(missing)),
        "missing_tickers": ", ".join(missing),
        "coverage_by_ticker": _coverage_by_ticker(ohlcv),
        "cagr": result.metrics["cagr"],
        "sharpe": result.metrics["sharpe"],
        "max_drawdown": result.metrics["max_drawdown"],
        "annualized_turnover": result.metrics["annualized_turnover"],
        "oos_cagr": oos_metrics["cagr"],
        "oos_sharpe": oos_metrics["sharpe"],
        "oos_max_drawdown": oos_metrics["max_drawdown"],
        "oos_annualized_turnover": oos_metrics["annualized_turnover"],
        "cagr_delta_vs_yfinance": None,
        "sharpe_delta_vs_yfinance": None,
        "max_drawdown_delta_vs_yfinance": None,
        "oos_cagr_delta_vs_yfinance": None,
        "oos_sharpe_delta_vs_yfinance": None,
        "oos_max_drawdown_delta_vs_yfinance": None,
        "threshold": None,
        "promotion_label": "needs more testing",
        "notes": notes,
    }


def _provider_validation_row(provider: str, oos_start: str | pd.Timestamp) -> dict:
    try:
        fetch_result = fetch_ohlcv_result(
            REQUIRED_TICKERS,
            period="max",
            provider=provider,
            use_cache=False,
        )
        ohlcv = fetch_result.data
        prices = backtest.close_matrix_from_ohlcv(ohlcv).loc["2003-01-01":]
        missing = _validate_required_prices(prices)
        if missing:
            row = _empty_provider_validation_row(
                provider,
                status="missing_required_prices",
                notes="Provider returned data, but not enough aligned required tickers for a valid methodology run.",
            )
            row.update(
                {
                    "ticker_count": int(len(prices.columns)),
                    "missing_count": int(len(missing)),
                    "missing_tickers": ", ".join(missing),
                    "coverage_by_ticker": _coverage_by_ticker(ohlcv),
                }
            )
            return row
        rebalance_dates = backtest.weekly_rebalance_dates(prices)
        methodology_targets = backtest.build_historical_methodology_targets(
            ohlcv,
            rebalance_dates=rebalance_dates,
            phase="MID",
        )
        strategy_columns = list(methodology_targets.target_weights.columns)
        if not strategy_columns:
            raise ValueError("methodology target builder produced no target columns")
        result = backtest.run_weight_backtest(
            prices[strategy_columns],
            methodology_targets.target_weights,
            transaction_cost_bps=5.0,
        )
        return _provider_validation_row_from_backtest(
            provider=provider,
            ohlcv=ohlcv,
            prices=prices,
            result=result,
            oos_start=oos_start,
            notes="Provider source comparison only; use B-160 before promoting any live rule.",
        )
    except Exception as exc:
        return _empty_provider_validation_row(
            provider,
            status="error",
            notes=f"Provider validation failed: {exc}",
        )


def _with_yfinance_deltas(rows: list[dict]) -> list[dict]:
    baseline = next(
        (row for row in rows if row.get("provider") == "yfinance" and row.get("status") == "available"),
        None,
    )
    metrics = ["cagr", "sharpe", "max_drawdown", "oos_cagr", "oos_sharpe", "oos_max_drawdown"]
    if baseline is None:
        for row in rows:
            if row.get("row_type") == "provider_comparison":
                row["notes"] = str(row.get("notes", "")).rstrip() + " Default/yfinance comparison unavailable."
        return rows
    for row in rows:
        if row.get("row_type") != "provider_comparison":
            continue
        for metric in metrics:
            value = row.get(metric)
            base = baseline.get(metric)
            row[f"{metric}_delta_vs_yfinance"] = (
                float(value) - float(base) if value is not None and base is not None else None
            )
    return rows


def _massive_provider_feature_sweep_rows() -> list[dict]:
    rows = []
    for threshold in MASSIVE_BLOCK_TRADE_THRESHOLDS:
        rows.append(
            {
                "row_type": "provider_feature_sweep",
                "variant": f"Block-trade upside ratio >= {threshold:g}",
                "provider": "massive",
                "endpoint": MASSIVE_TRADES_ENDPOINT,
                "status": "unavailable_no_historical_asof_snapshots",
                "coverage_start": "-",
                "coverage_end": "-",
                "coverage_rows": 0,
                "ticker_count": 0,
                "missing_count": 0,
                "missing_tickers": "",
                "coverage_by_ticker": "",
                "cagr": None,
                "sharpe": None,
                "max_drawdown": None,
                "annualized_turnover": None,
                "oos_cagr": None,
                "oos_sharpe": None,
                "oos_max_drawdown": None,
                "oos_annualized_turnover": None,
                "cagr_delta_vs_yfinance": None,
                "sharpe_delta_vs_yfinance": None,
                "max_drawdown_delta_vs_yfinance": None,
                "oos_cagr_delta_vs_yfinance": None,
                "oos_sharpe_delta_vs_yfinance": None,
                "oos_max_drawdown_delta_vs_yfinance": None,
                "threshold": float(threshold),
                "promotion_label": "do not promote",
                "notes": (
                    "The current trade-tape endpoint can inform live provider flow, but this runner has no "
                    "persisted timestamped as-of snapshots for historical rebalances."
                ),
            }
        )
    return rows


def _build_massive_provider_validation_summary(
    *,
    enabled: bool,
    oos_start="2015-01-01",
    precomputed_provider_rows: list[dict] | None = None,
) -> pd.DataFrame:
    if not enabled:
        return pd.DataFrame()
    precomputed = {
        str(row.get("provider", "")).lower(): dict(row)
        for row in (precomputed_provider_rows or [])
        if row.get("row_type") == "provider_comparison"
    }
    rows = []
    for provider in ("yfinance", "massive"):
        rows.append(precomputed.get(provider) or _provider_validation_row(provider, oos_start=oos_start))
    rows = _with_yfinance_deltas(rows)
    rows.extend(_massive_provider_feature_sweep_rows())
    return pd.DataFrame(rows)


def _resolved_provider(provider: str) -> str:
    try:
        return _select_ohlcv_provider(provider)
    except Exception:
        return str(provider)


def _fred_config_status(macro_data: dict[str, pd.Series]) -> str:
    if macro_data:
        return "configured"
    return "not configured or no FRED series returned"


def _index_window(index) -> tuple[str, str, int]:
    values = pd.DatetimeIndex(pd.to_datetime(index))
    if len(values) == 0:
        return "-", "-", 0
    return values.min().date().isoformat(), values.max().date().isoformat(), int(len(values))


def _macro_windows(macro_data: dict[str, pd.Series]) -> list[str]:
    if not macro_data:
        return ["- No FRED macro series were returned."]
    lines = []
    for series_id in sorted(macro_data):
        start, end, count = _index_window(macro_data[series_id].dropna().index)
        lines.append(f"- {series_id}: {start} to {end} ({count} observations)")
    return lines


def _pct(value) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def _num(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _int_text(value) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "-"


def _ohlcv_source_metadata(fetch_result, cache_policy: str) -> dict:
    if fetch_result is None:
        return {
            "cache_policy": "normal",
            "provider": "",
            "fetched_count": 0,
            "fresh_cache_hit_count": 0,
            "stale_cache_hit_count": 0,
            "missing_count": 0,
            "warnings": [],
        }
    return {
        "cache_policy": cache_policy,
        "provider": str(getattr(fetch_result, "provider", "")),
        "fetched_count": int(len(getattr(fetch_result, "fetched", ()))),
        "fresh_cache_hit_count": int(len(getattr(fetch_result, "fresh_cache_hits", ()))),
        "stale_cache_hit_count": int(len(getattr(fetch_result, "stale_cache_hits", ()))),
        "missing_count": int(len(getattr(fetch_result, "missing", ()))),
        "fetched": list(getattr(fetch_result, "fetched", ())),
        "fresh_cache_hits": list(getattr(fetch_result, "fresh_cache_hits", ())),
        "stale_cache_hits": list(getattr(fetch_result, "stale_cache_hits", ())),
        "missing": list(getattr(fetch_result, "missing", ())),
        "warnings": list(getattr(fetch_result, "warnings", ())),
    }


def _ohlcv_source_lines(source: dict | None, validation_ticket: str = "B-157") -> list[str]:
    if not source:
        return ["- Cache policy: normal dashboard/manual fetch path"]
    policy = source.get("cache_policy", "normal")
    label = f"bypassed for {validation_ticket} validation" if policy == "bypassed" else str(policy)
    lines = [
        f"- Cache policy: {label}",
        f"- Source provider: {source.get('provider', '-')}",
        f"- Fetched tickers: {source.get('fetched_count', 0)}",
        f"- Fresh cache hits: {source.get('fresh_cache_hit_count', 0)}",
        f"- Stale cache hits: {source.get('stale_cache_hit_count', 0)}",
        f"- Missing tickers: {source.get('missing_count', 0)}",
    ]
    warnings = source.get("warnings") or []
    if warnings:
        lines.append("- Warnings: " + " | ".join(str(item) for item in warnings))
    return lines


def _fred_validation_variant_table(macro_variant_summary: pd.DataFrame) -> list[str]:
    if macro_variant_summary is None or macro_variant_summary.empty:
        return [
            "No macro variant rows were produced. Do not promote any FRED macro rule from this run.",
        ]
    lines = [
        "| Variant | Series | Lag Days | Label | Active OOS | CAGR Delta | Sharpe Delta | Drawdown Delta | OOS CAGR Delta | OOS Sharpe Delta | OOS Drawdown Delta | Turnover Delta | Hit-Rate Delta | Trade Count Delta |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in macro_variant_summary.iterrows():
        lines.append(
            f"| {row.get('variant', '-')} | "
            f"{row.get('series_id', '-')} | "
            f"{_int_text(row.get('availability_lag_days'))} | "
            f"{row.get('promotion_label', 'needs more testing')} | "
            f"{_int_text(row.get('active_oos_rebalances'))} | "
            f"{_pct(row.get('cagr_delta'))} | "
            f"{_num(row.get('sharpe_delta'))} | "
            f"{_pct(row.get('max_drawdown_delta'))} | "
            f"{_pct(row.get('oos_cagr_delta'))} | "
            f"{_num(row.get('oos_sharpe_delta'))} | "
            f"{_pct(row.get('oos_max_drawdown_delta'))} | "
            f"{_pct(row.get('annualized_turnover_delta'))} | "
            f"{_pct(row.get('hit_rate_delta'))} | "
            f"{_int_text(row.get('trade_count_delta'))} |"
        )
    return lines


def _format_fred_validation_report(
    *,
    macro_variant_summary: pd.DataFrame,
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    macro_data: dict[str, pd.Series],
    requested_provider: str,
    resolved_provider: str,
    fred_status: str,
    generated_at_utc: str,
    oos_start: str = "2015-01-01",
    validation_split_method: str = "configured",
    ohlcv_source: dict | None = None,
) -> str:
    price_start, price_end, price_rows = _index_window(prices.index)
    rebalance_start, rebalance_end, rebalance_count = _index_window(target_weights.index)
    lines = [
        "# FRED Macro Historical Validation Report",
        "",
        f"Generated UTC: {generated_at_utc}",
        "Ticket: B-157",
        "",
        (
            "No FRED macro rule is promoted into live scoring, veto logic, alerts, "
            "recommendations, or broker behavior by this report."
        ),
        "",
        "## Provider Configuration",
        "",
        f"- Requested OHLCV provider: {requested_provider}",
        f"- Resolved OHLCV provider: {resolved_provider}",
        f"- FRED status: {fred_status}",
        f"- OOS start: {pd.Timestamp(oos_start).date().isoformat()}",
        f"- Validation split: {validation_split_method}",
        "",
        "## Data Windows",
        "",
        f"- Market prices: {price_start} to {price_end} ({price_rows} rows, {len(prices.columns)} tickers)",
        f"- Methodology rebalances: {rebalance_start} to {rebalance_end} ({rebalance_count} rows)",
        "",
        "## OHLCV Source Evidence",
        "",
    ]
    lines.extend(_ohlcv_source_lines(ohlcv_source, validation_ticket="B-157"))
    lines.extend(
        [
            "",
        ]
    )
    lines.extend(
        [
        "## FRED Series Windows",
        "",
        ]
    )
    lines.extend(_macro_windows(macro_data))
    lines.extend(
        [
            "",
            "## Promotion Label Rules",
            "",
            "- `candidate`: at least 20 active out-of-sample rebalances, OOS Sharpe delta >= 0.10, OOS CAGR delta >= 0, OOS drawdown delta >= 0, and full-period Sharpe delta >= 0.",
            "- `do not promote`: enough OOS observations and no OOS improvement in Sharpe, CAGR, or drawdown.",
            "- `needs more testing`: mixed evidence or insufficient OOS observations.",
            "",
            "## Variant Results",
            "",
        ]
    )
    lines.extend(_fred_validation_variant_table(macro_variant_summary))
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Use B-158 only for variants labeled `candidate` after review. Leave all other rules out of live behavior.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _massive_provider_comparison_table(summary: pd.DataFrame) -> list[str]:
    rows = summary[summary.get("row_type") == "provider_comparison"] if not summary.empty else pd.DataFrame()
    if rows.empty:
        return ["No provider comparison rows were produced. Do not promote any Massive-derived rule from this run."]
    lines = [
        "| Variant | Provider | Status | Coverage | Tickers | CAGR Delta | Sharpe Delta | Drawdown Delta | OOS CAGR Delta | OOS Sharpe Delta | OOS Drawdown Delta | Label |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in rows.iterrows():
        coverage = f"{row.get('coverage_start', '-')} to {row.get('coverage_end', '-')}"
        lines.append(
            f"| {row.get('variant', '-')} | "
            f"{row.get('provider', '-')} | "
            f"{row.get('status', '-')} | "
            f"{coverage} | "
            f"{_int_text(row.get('ticker_count'))} | "
            f"{_pct(row.get('cagr_delta_vs_yfinance'))} | "
            f"{_num(row.get('sharpe_delta_vs_yfinance'))} | "
            f"{_pct(row.get('max_drawdown_delta_vs_yfinance'))} | "
            f"{_pct(row.get('oos_cagr_delta_vs_yfinance'))} | "
            f"{_num(row.get('oos_sharpe_delta_vs_yfinance'))} | "
            f"{_pct(row.get('oos_max_drawdown_delta_vs_yfinance'))} | "
            f"{row.get('promotion_label', 'needs more testing')} |"
        )
    return lines


def _massive_feature_sweep_table(summary: pd.DataFrame) -> list[str]:
    rows = summary[summary.get("row_type") == "provider_feature_sweep"] if not summary.empty else pd.DataFrame()
    if rows.empty:
        return ["No provider-derived criteria sweeps were produced. Do not promote any Massive-derived rule."]
    lines = [
        "| Variant | Endpoint | Status | Threshold | Label | Notes |",
        "|---|---|---|---:|---|---|",
    ]
    for _, row in rows.iterrows():
        lines.append(
            f"| {row.get('variant', '-')} | "
            f"{row.get('endpoint', '-')} | "
            f"{row.get('status', '-')} | "
            f"{_num(row.get('threshold'))} | "
            f"{row.get('promotion_label', 'do not promote')} | "
            f"{row.get('notes', '')} |"
        )
    return lines


def _massive_coverage_lines(summary: pd.DataFrame) -> list[str]:
    rows = summary[summary.get("row_type") == "provider_comparison"] if not summary.empty else pd.DataFrame()
    if rows.empty:
        return ["- No historical OHLCV coverage rows were produced."]
    lines = []
    for _, row in rows.iterrows():
        detail = str(row.get("coverage_by_ticker") or "").strip()
        if not detail:
            detail = f"{row.get('coverage_start', '-')} to {row.get('coverage_end', '-')}"
        lines.append(f"- {row.get('provider', '-')}: {detail}")
    return lines


def _massive_endpoint_lines(summary: pd.DataFrame) -> list[str]:
    endpoints = []
    if summary is not None and not summary.empty:
        for endpoint in summary["endpoint"].dropna().astype(str):
            if endpoint and endpoint not in endpoints:
                endpoints.append(endpoint)
    if not endpoints:
        endpoints = ["yfinance.download", MASSIVE_AGGS_ENDPOINT, MASSIVE_TRADES_ENDPOINT]
    return [f"- {endpoint}" for endpoint in endpoints]


def _format_massive_provider_validation_report(
    *,
    massive_validation_summary: pd.DataFrame,
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    requested_provider: str,
    resolved_provider: str,
    generated_at_utc: str,
    oos_start: str = "2015-01-01",
    validation_split_method: str = "configured",
    ohlcv_source: dict | None = None,
) -> str:
    price_start, price_end, price_rows = _index_window(prices.index)
    rebalance_start, rebalance_end, rebalance_count = _index_window(target_weights.index)
    lines = [
        "# Massive Historical Provider-Data Validation Report",
        "",
        f"Generated UTC: {generated_at_utc}",
        "Ticket: B-159",
        "",
        (
            "No Massive-derived rule is promoted into live scoring, veto logic, alerts, "
            "recommendations, provider-flow behavior, Pillar 7 weights, or broker behavior by this report."
        ),
        "",
        "## Provider Configuration",
        "",
        f"- Requested OHLCV provider: {requested_provider}",
        f"- Resolved OHLCV provider: {resolved_provider}",
        f"- OOS start: {pd.Timestamp(oos_start).date().isoformat()}",
        f"- Validation split: {validation_split_method}",
        "",
        "## Data Sets And Endpoints Checked",
        "",
    ]
    lines.extend(_massive_endpoint_lines(massive_validation_summary))
    lines.extend(
        [
            "",
            "## Main Run Data Windows",
            "",
            f"- Market prices: {price_start} to {price_end} ({price_rows} rows, {len(prices.columns)} tickers)",
            f"- Methodology rebalances: {rebalance_start} to {rebalance_end} ({rebalance_count} rows)",
            "",
            "## OHLCV Source Evidence",
            "",
        ]
    )
    lines.extend(_ohlcv_source_lines(ohlcv_source, validation_ticket="B-159"))
    lines.extend(
        [
            "",
            "## Historical Coverage By Ticker",
            "",
        ]
    )
    lines.extend(_massive_coverage_lines(massive_validation_summary))
    lines.extend(
        [
            "",
            "## Baseline Vs Massive OHLCV",
            "",
        ]
    )
    lines.extend(_massive_provider_comparison_table(massive_validation_summary))
    lines.extend(
        [
            "",
            "## Provider-Derived Criteria Sweeps",
            "",
        ]
    )
    lines.extend(_massive_feature_sweep_table(massive_validation_summary))
    lines.extend(
        [
            "",
            "## Leakage And Survivorship Controls",
            "",
            "- Validation OHLCV fetches bypass the local cache so provider evidence is fresh for the report run.",
            "- yfinance and Massive provider rows are fetched separately and compared as data-source evidence, not as live rules.",
            "- Historical methodology targets are built from OHLCV sliced through each rebalance date.",
            "- Massive trade-tape/block-trade sweeps are labeled `do not promote` until timestamped as-of snapshots exist.",
            "- Use B-160 before any Massive-derived criterion changes scoring, alerts, vetoes, recommendations, provider-flow behavior, Pillar 7 weights, or broker behavior.",
            "",
            "## Decision",
            "",
            "Treat B-159 as research evidence only. Promote only through B-160 after review and deterministic tests.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _download_prices(period: str, provider: str, use_cache: bool = True):
    fetch_result = None
    if use_cache:
        ohlcv = fetch_ohlcv(REQUIRED_TICKERS, period=period, provider=provider)
    else:
        fetch_result = fetch_ohlcv_result(
            REQUIRED_TICKERS,
            period=period,
            provider=provider,
            use_cache=False,
        )
        ohlcv = fetch_result.data
    prices = backtest.close_matrix_from_ohlcv(ohlcv).loc["2003-01-01":]
    return ohlcv, prices, fetch_result


def _validate_required_prices(prices) -> list[str]:
    return sorted(set(REQUIRED_TICKERS).difference(prices.columns))


def _run_live_smoke(period: str) -> int:
    provider = _provider()
    try:
        _, prices, _ = _download_prices(period=period, provider=provider)
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
    requested_provider = _provider()
    try:
        validation_mode = bool(args.macro_variants or args.massive_variants)
        ohlcv, prices, ohlcv_fetch_result = _download_prices(
            period="max",
            provider=requested_provider,
            use_cache=not validation_mode,
        )
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
        validation_oos_start, validation_split_method = _resolve_validation_split(
            methodology_targets.target_weights.index
        )
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
        methodology_windows = backtest.split_backtest_metrics(
            methodology_result,
            oos_start=validation_oos_start,
        )
        sixty_forty_windows = backtest.split_backtest_metrics(
            sixty_forty_result,
            oos_start=validation_oos_start,
        )
        sector_windows = backtest.split_backtest_metrics(
            sector_result,
            oos_start=validation_oos_start,
        )
        cost_scenarios = backtest.run_cost_scenarios(
            prices[strategy_columns],
            methodology_targets.target_weights,
            cost_bps_values=[3, 5, 10],
        )
        macro_data = _fetch_macro_data(enabled=bool(args.macro_variants))
        macro_variant_summary = _build_macro_variant_summary(
            enabled=bool(args.macro_variants),
            prices=prices[strategy_columns],
            target_weights=methodology_targets.target_weights,
            macro_data=macro_data,
            oos_start=validation_oos_start,
        )
        fred_validation_report = None
        fred_validation_summary = None
        massive_validation_report = None
        massive_validation_summary = None
        if args.macro_variants:
            fred_validation_summary = macro_variant_summary
            fred_validation_report = _format_fred_validation_report(
                macro_variant_summary=macro_variant_summary,
                prices=prices[strategy_columns],
                target_weights=methodology_targets.target_weights,
                macro_data=macro_data,
                requested_provider=requested_provider,
                resolved_provider=_resolved_provider(requested_provider),
                fred_status=_fred_config_status(macro_data),
                generated_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                oos_start=validation_oos_start,
                validation_split_method=validation_split_method,
                ohlcv_source=_ohlcv_source_metadata(ohlcv_fetch_result, cache_policy="bypassed"),
            )
        if args.massive_variants:
            precomputed_provider_rows = []
            if ohlcv_fetch_result is not None:
                main_provider = str(getattr(ohlcv_fetch_result, "provider", "")).lower()
                if main_provider in {"massive", "yfinance"}:
                    precomputed_provider_rows.append(
                        _provider_validation_row_from_backtest(
                            provider=main_provider,
                            ohlcv=ohlcv,
                            prices=prices,
                            result=methodology_result,
                            oos_start=validation_oos_start,
                            notes="Reused the main validation-mode backtest run to avoid duplicate provider scoring.",
                        )
                    )
            massive_validation_summary = _build_massive_provider_validation_summary(
                enabled=True,
                oos_start=validation_oos_start,
                precomputed_provider_rows=precomputed_provider_rows,
            )
            massive_validation_report = _format_massive_provider_validation_report(
                massive_validation_summary=massive_validation_summary,
                prices=prices[strategy_columns],
                target_weights=methodology_targets.target_weights,
                requested_provider=requested_provider,
                resolved_provider=_resolved_provider(requested_provider),
                generated_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                oos_start=validation_oos_start,
                validation_split_method=validation_split_method,
                ohlcv_source=_ohlcv_source_metadata(ohlcv_fetch_result, cache_policy="bypassed"),
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
            macro_variant_summary=macro_variant_summary,
            title="Manual Backtest Smoke Report",
            oos_start=validation_oos_start,
        )
        methodology_report = backtest.format_methodology_report(
            strategy_metrics=methodology_result.metrics,
            benchmark_metrics={
                "Methodology": methodology_result.metrics,
                "60/40 SPY/AGG": sixty_forty_result.metrics,
                "Equal-weight sectors": sector_result.metrics,
            },
            gates=gates,
            window_metrics={
                "Methodology full period": methodology_windows["Full period"],
                "Methodology in-sample": methodology_windows["In-sample"],
                "Methodology out-of-sample": methodology_oos_metrics,
                "60/40 out-of-sample": sixty_forty_windows["Out-of-sample"],
                "Equal-weight sectors out-of-sample": sector_oos_metrics,
            },
            simulation_summary=simulation_summary,
            macro_variant_summary=macro_variant_summary,
        )
        ohlcv_source = _ohlcv_source_metadata(
            ohlcv_fetch_result,
            cache_policy="bypassed" if validation_mode else "normal",
        )
        equity = backtest.equity_frame(
            {
                "Methodology": methodology_result,
                "60/40 SPY/AGG": sixty_forty_result,
                "Equal-weight sectors": sector_result,
            }
        )
        _write_artifacts(
            report,
            methodology_report,
            equity,
            methodology_targets.states,
            REQUIRED_TICKERS,
            simulation_summary=simulation_summary,
            macro_variant_summary=macro_variant_summary,
            fred_validation_report=fred_validation_report,
            fred_validation_summary=fred_validation_summary,
            massive_validation_report=massive_validation_report,
            massive_validation_summary=massive_validation_summary,
            ohlcv_source=ohlcv_source,
        )
    except Exception as exc:
        print(f"Manual backtest data validation failed: {exc}")
        return 2
    print(f"Wrote {REPORT_PATH}")
    if args.macro_variants:
        print(f"Wrote {FRED_VALIDATION_REPORT_PATH}")
    if args.massive_variants:
        print(f"Wrote {MASSIVE_VALIDATION_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
