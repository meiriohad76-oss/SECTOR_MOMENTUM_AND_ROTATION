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
from src import provider_snapshots


REPORT_PATH = ROOT / "docs" / "backtest_report.md"
METHODOLOGY_REPORT_PATH = ROOT / "docs" / "backtest_methodology_report.md"
EQUITY_PATH = ROOT / "docs" / "backtest_equity.csv"
STATES_PATH = ROOT / "docs" / "backtest_states.csv"
METADATA_PATH = ROOT / "docs" / "backtest_metadata.json"
FRED_VALIDATION_REPORT_PATH = ROOT / "docs" / "fred_macro_validation_report.md"
FRED_VALIDATION_SUMMARY_PATH = ROOT / "docs" / "fred_macro_validation_summary.csv"
MASSIVE_VALIDATION_REPORT_PATH = ROOT / "docs" / "massive_provider_validation_report.md"
MASSIVE_VALIDATION_SUMMARY_PATH = ROOT / "docs" / "massive_provider_validation_summary.csv"
CALIBRATION_REPORT_PATH = ROOT / "docs" / "calibration_10y_report.md"
CALIBRATION_SUMMARY_PATH = ROOT / "docs" / "calibration_10y_summary.csv"
CALIBRATION_CANDIDATES_PATH = ROOT / "docs" / "calibration_10y_candidates.csv"
CALIBRATION_CANDIDATE_CONFIG_PATH = ROOT / "docs" / "calibration_10y_candidate_config.json"
CALIBRATION_METADATA_PATH = ROOT / "docs" / "calibration_10y_metadata.json"
CALIBRATION_BASELINE_CONFIG_FILENAME = "calibration_10y_baseline_config.json"
CALIBRATION_HORIZONS_WEEKS = (4, 13, 26, 52)
MASSIVE_AGGS_ENDPOINT = "https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}"
MASSIVE_TRADES_ENDPOINT = "https://api.massive.com/v3/trades/{ticker}"
MASSIVE_BLOCK_TRADE_THRESHOLDS = (1.0, 1.25, 1.5)
MASSIVE_PROVIDER_FLOW_MIN_ACTIVE_OOS = 20
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


def _calibration_baseline_config_path() -> Path:
    return METADATA_PATH.with_name(CALIBRATION_BASELINE_CONFIG_FILENAME)


def _artifact_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


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
    baseline_config: dict | None = None,
    calibration_split_summary: dict | None = None,
    calibration_report: str | None = None,
    calibration_summary=None,
    calibration_candidates=None,
    calibration_candidate_config: dict | None = None,
    calibration_metadata: dict | None = None,
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
        "calibration_split_summary": calibration_split_summary or {},
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
    calibration_metadata_payload = dict(calibration_metadata or {})
    if calibration_report is not None:
        calibration_report_bytes = calibration_report.encode("utf-8")
        payloads[CALIBRATION_REPORT_PATH] = calibration_report_bytes
        metadata["calibration_10y_report_sha256"] = _sha256_bytes(calibration_report_bytes)
        calibration_metadata_payload["report_sha256"] = metadata["calibration_10y_report_sha256"]
    if calibration_summary is not None:
        calibration_summary_bytes = calibration_summary.to_csv(index=False).encode("utf-8")
        payloads[CALIBRATION_SUMMARY_PATH] = calibration_summary_bytes
        metadata["calibration_10y_summary_sha256"] = _sha256_bytes(calibration_summary_bytes)
        calibration_metadata_payload["summary_sha256"] = metadata["calibration_10y_summary_sha256"]
    if calibration_candidates is not None:
        calibration_candidates_bytes = calibration_candidates.to_csv(index=False).encode("utf-8")
        payloads[CALIBRATION_CANDIDATES_PATH] = calibration_candidates_bytes
        metadata["calibration_10y_candidates_sha256"] = _sha256_bytes(
            calibration_candidates_bytes
        )
        calibration_metadata_payload["candidates_sha256"] = metadata[
            "calibration_10y_candidates_sha256"
        ]
    if calibration_candidate_config is not None:
        calibration_candidate_config_bytes = _json_artifact_bytes(calibration_candidate_config)
        payloads[CALIBRATION_CANDIDATE_CONFIG_PATH] = calibration_candidate_config_bytes
        metadata["calibration_10y_candidate_config_sha256"] = _sha256_bytes(
            calibration_candidate_config_bytes
        )
        calibration_metadata_payload["candidate_config_sha256"] = metadata[
            "calibration_10y_candidate_config_sha256"
        ]
    if baseline_config is not None:
        baseline_config_bytes = (
            json.dumps(baseline_config, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        baseline_config_path = _calibration_baseline_config_path()
        payloads[baseline_config_path] = baseline_config_bytes
        metadata["baseline_config"] = baseline_config
        metadata["baseline_config_sha256"] = backtest.baseline_config_hash(baseline_config)
        metadata["baseline_config_artifact"] = _artifact_label(baseline_config_path)
        metadata["baseline_config_artifact_sha256"] = _sha256_bytes(baseline_config_bytes)
    if (
        calibration_metadata is not None
        or calibration_report is not None
        or calibration_summary is not None
        or calibration_candidates is not None
        or calibration_candidate_config is not None
    ):
        calibration_metadata_payload.setdefault("generated_at_utc", metadata["generated_at_utc"])
        calibration_metadata_bytes = (
            json.dumps(calibration_metadata_payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        payloads[CALIBRATION_METADATA_PATH] = calibration_metadata_bytes
        metadata["calibration_10y_metadata_sha256"] = _sha256_bytes(calibration_metadata_bytes)
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
    parser.add_argument(
        "--provider-snapshot-db",
        default=str(provider_snapshots.DEFAULT_SNAPSHOT_DB_PATH),
        help=(
            "SQLite provider snapshot DB for --massive-variants provider-flow replay "
            f"(default: {provider_snapshots.DEFAULT_SNAPSHOT_DB_PATH})."
        ),
    )
    return parser


def _provider() -> str:
    return os.environ.get("OHLCV_PROVIDER", DEFAULT_OHLCV_PROVIDER)


def _frame_records(frame) -> list[dict]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return json.loads(frame.to_json(orient="records"))


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _json_ready(value.item())
        except (TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _json_artifact_bytes(payload: dict) -> bytes:
    return (
        json.dumps(_json_ready(payload), allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


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


def _date_or_none(index: pd.DatetimeIndex, position: int) -> str | None:
    if len(index) == 0:
        return None
    return pd.Timestamp(index[position]).date().isoformat()


def _build_calibration_split_summary(
    rebalance_dates,
    *,
    years: int = 10,
    calibration_years: int = 5,
    validation_years: int = 1,
    final_holdout_years: int = 1,
) -> dict:
    dates = pd.DatetimeIndex(pd.to_datetime(rebalance_dates)).dropna().sort_values().unique()
    try:
        splits = backtest.walk_forward_calibration_splits(
            dates,
            years=years,
            calibration_years=calibration_years,
            validation_years=validation_years,
            final_holdout_years=final_holdout_years,
        )
    except ValueError as exc:
        return {
            "status": "insufficient_history",
            "requested_years": years,
            "calibration_years": calibration_years,
            "validation_years": validation_years,
            "final_holdout_years": final_holdout_years,
            "available_start": _date_or_none(dates, 0),
            "available_end": _date_or_none(dates, -1),
            "fold_count": 0,
            "folds": [],
            "reason": str(exc),
        }
    return backtest.walk_forward_split_summary(splits, requested_years=years)


def _normalize_calibration_summary(metrics: pd.DataFrame, *, scope: str) -> pd.DataFrame:
    if metrics is None or metrics.empty:
        return pd.DataFrame()
    frame = metrics.copy()
    frame.insert(0, "scope", scope)
    if "class" not in frame.columns:
        frame.insert(1, "class", "all")
    else:
        frame["class"] = frame["class"].fillna("unknown").astype(str)
    preferred = [
        "scope",
        "class",
        "direction",
        "horizon_weeks",
        "total_count",
        "available_count",
        "signal_count",
        "signal_available_count",
        "success_count",
        "failure_count",
        "hit_rate",
        "precision",
        "recall",
        "f1",
        "average_forward_return",
        "average_forward_excess_return",
        "average_post_entry_drawdown",
        "average_drawdown_avoided",
    ]
    columns = [column for column in preferred if column in frame.columns]
    columns.extend(column for column in frame.columns if column not in columns)
    return frame[columns]


def _format_percent(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if pd.isna(number):
        return "n/a"
    return f"{number * 100:.2f}%"


def _format_count(value) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "0"


def _format_calibration_baseline_report(
    summary: pd.DataFrame,
    *,
    candidates: pd.DataFrame,
    metadata: dict,
) -> str:
    lines = [
        "# 10-Year Calibration Baseline Report",
        "",
        "Ticket: B-163.7",
        "",
        (
            "This is research-only baseline and calibration-candidate evidence. It does "
            "not change live scoring, alter recommendations, or allow live promotion."
        ),
        "",
        "## Provenance",
        "",
        f"- Baseline config hash: `{metadata.get('baseline_config_sha256', 'unknown')}`",
        f"- Label rows: {_format_count(metadata.get('label_rows'))}",
        f"- Summary rows: {_format_count(metadata.get('summary_rows'))}",
        f"- Split status: `{metadata.get('calibration_split_summary', {}).get('status', 'unknown')}`",
        f"- Calibrated rerun gate: `{metadata.get('candidate_config_status', 'unknown')}`",
        "",
        "## Overall Baseline Hit Rates",
        "",
    ]
    overall = summary[summary["scope"] == "overall"] if not summary.empty else pd.DataFrame()
    if overall.empty:
        lines.append("- No baseline label metrics were available for this run.")
    else:
        ordered = overall.copy()
        ordered["_direction_order"] = (
            ordered["direction"].map({"positive": 0, "negative": 1}).fillna(9)
        )
        for _, row in ordered.sort_values(["horizon_weeks", "_direction_order"]).iterrows():
            direction = str(row.get("direction", "")).lower()
            label = "Positive momentum" if direction == "positive" else "Negative momentum"
            lines.append(
                "- "
                f"{label} hit rate ({int(row.get('horizon_weeks', 0))}w): "
                f"{_format_percent(row.get('hit_rate'))} "
                f"({_format_count(row.get('success_count'))} successes / "
                f"{_format_count(row.get('signal_available_count'))} available signals)."
            )
    lines.extend(
        [
            "",
            "## Calibration Candidate Search",
            "",
        ]
    )
    if candidates.empty:
        lines.append("- No calibration candidate rows were produced.")
    else:
        selected = (
            candidates[candidates["selected_by_calibration"].map(bool)]
            if "selected_by_calibration" in candidates.columns
            else pd.DataFrame()
        )
        if selected.empty:
            first = candidates.iloc[0]
            lines.append(
                "- No calibration candidate was selected. "
                f"Status: `{first.get('gate_status', 'unknown')}`."
            )
        else:
            for _, row in selected.iterrows():
                lines.append(
                    "- Selected by calibration window only: "
                    f"`{row.get('candidate_id', 'unknown')}` "
                    f"({row.get('gate_status', 'unknown')}; "
                    f"{row.get('promotion_label', 'do not promote')})."
                )
        lines.append(
            "- Final holdout remains untouched in this slice; no candidate is promoted."
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Candidate search is research-only and does not update live methodology parameters.",
            "- Final holdout evaluation and live promotion remain pending future reviewed B-163 slices.",
            "- Dashboard surfacing remains artifact-only and read-only.",
            "",
        ]
    )
    return "\n".join(lines)


def _calibration_splits_from_summary(summary: dict) -> list[backtest.WalkForwardSplit]:
    if not summary or summary.get("status") != "ready":
        return []
    splits = []
    for row in summary.get("folds", []):
        try:
            splits.append(
                backtest.WalkForwardSplit(
                    name=str(row["name"]),
                    calibration_start=pd.Timestamp(row["calibration_start"]),
                    calibration_end=pd.Timestamp(row["calibration_end"]),
                    validation_start=pd.Timestamp(row["validation_start"]),
                    validation_end=pd.Timestamp(row["validation_end"]),
                    final_holdout_start=pd.Timestamp(row["final_holdout_start"]),
                    final_holdout_end=pd.Timestamp(row["final_holdout_end"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("calibration split summary contains an invalid fold") from exc
    return splits


def _calibration_candidate_rules() -> tuple[backtest.CalibrationCandidateRule, ...]:
    return (
        backtest.CalibrationCandidateRule(candidate_id="baseline"),
        backtest.CalibrationCandidateRule(
            candidate_id="positive_score_ge_0_8",
            positive_min_s_score_after_veto=0.8,
        ),
        backtest.CalibrationCandidateRule(
            candidate_id="positive_score_ge_1_0",
            positive_min_s_score_after_veto=1.0,
        ),
        backtest.CalibrationCandidateRule(
            candidate_id="negative_score_le_0_0",
            negative_max_s_score_after_veto=0.0,
        ),
        backtest.CalibrationCandidateRule(
            candidate_id="negative_score_le_minus_0_5",
            negative_max_s_score_after_veto=-0.5,
        ),
    )


def _scalar_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _selected_candidate_rows(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates is None or candidates.empty or "selected_by_calibration" not in candidates.columns:
        return pd.DataFrame()
    return candidates[candidates["selected_by_calibration"].map(_scalar_bool)].copy()


def _build_calibration_candidate_config(
    *,
    candidates: pd.DataFrame,
    baseline_config: dict,
    calibration_split_summary: dict,
) -> dict:
    split_status = str((calibration_split_summary or {}).get("status", "unknown"))
    base = {
        "ticket": "B-163",
        "slice": "B-163.7",
        "purpose": "research_only_calibrated_rerun_gate",
        "research_only": True,
        "baseline_config_sha256": backtest.baseline_config_hash(baseline_config),
        "calibration_split_status": split_status,
        "calibration_split_summary": calibration_split_summary or {},
        "candidate_rows": int(len(candidates)) if candidates is not None else 0,
        "candidate_config_available": False,
        "selected_candidate_id": None,
        "selected_candidate": {},
        "candidate_rule": {},
        "final_holdout_evaluated": False,
        "final_holdout_rows_used": 0,
        "live_promotion_allowed": False,
        "safety": {
            "parameter_tuning": "research_only_calibrated_rerun_gate",
            "candidate_promotion": "not_allowed",
            "live_scoring_change": "none",
            "final_holdout": "not_evaluated",
        },
    }
    if split_status != "ready":
        return {
            **base,
            "config_status": "skipped_insufficient_history",
            "gate_reasons": [
                str((calibration_split_summary or {}).get("reason") or "walk_forward_splits_not_ready")
            ],
        }

    selected = _selected_candidate_rows(candidates)
    if selected.empty:
        return {
            **base,
            "config_status": "blocked_no_selected_candidate",
            "gate_reasons": ["no_candidate_selected_by_calibration"],
        }

    row = selected.iloc[0].to_dict()
    candidate_id = str(row.get("candidate_id", "unknown"))
    gate_status = str(row.get("gate_status") or "blocked_final_holdout_not_evaluated")
    final_holdout_rows_used = _json_ready(row.get("final_holdout_rows_used")) or 0
    selected_candidate = _json_ready(row)
    candidate_rule = {
        "candidate_id": candidate_id,
        "horizon_weeks": _json_ready(row.get("horizon_weeks")),
        "selection_source": _json_ready(row.get("selection_source")),
        "positive_min_s_score_after_veto": _json_ready(
            row.get("positive_min_s_score_after_veto")
        ),
        "negative_max_s_score_after_veto": _json_ready(
            row.get("negative_max_s_score_after_veto")
        ),
    }
    config_available = gate_status == "blocked_final_holdout_not_evaluated"
    return {
        **base,
        "config_status": gate_status,
        "candidate_config_available": bool(config_available),
        "selected_candidate_id": candidate_id,
        "selected_candidate": selected_candidate,
        "candidate_rule": candidate_rule,
        "final_holdout_evaluated": _scalar_bool(row.get("final_holdout_evaluated")),
        "final_holdout_rows_used": int(final_holdout_rows_used),
        "live_promotion_allowed": False,
        "gate_reasons": [
            reason
            for reason in str(row.get("rejection_reasons") or gate_status).split(";")
            if reason
        ],
    }


def _build_calibration_baseline_artifacts(
    *,
    targets,
    prices: pd.DataFrame,
    baseline_config: dict,
    calibration_split_summary: dict,
    ohlcv_source: dict,
) -> tuple[pd.DataFrame, str, dict, pd.DataFrame, dict]:
    labels = backtest.build_calibration_feature_labels(
        targets,
        prices,
        horizons_weeks=CALIBRATION_HORIZONS_WEEKS,
    )
    overall = _normalize_calibration_summary(
        backtest.calibration_label_metrics(
            labels,
            horizons_weeks=CALIBRATION_HORIZONS_WEEKS,
        ),
        scope="overall",
    )
    by_class = pd.DataFrame()
    if not labels.empty and "class" in labels.columns:
        by_class = _normalize_calibration_summary(
            backtest.calibration_label_metrics(
                labels,
                horizons_weeks=CALIBRATION_HORIZONS_WEEKS,
                group_by="class",
            ),
            scope="class",
        )
    summary = pd.concat([overall, by_class], ignore_index=True)
    if not summary.empty:
        summary["scope"] = pd.Categorical(
            summary["scope"],
            categories=["overall", "class"],
            ordered=True,
        )
        summary["direction"] = pd.Categorical(
            summary["direction"],
            categories=["positive", "negative"],
            ordered=True,
        )
        summary = summary.sort_values(
            ["scope", "class", "horizon_weeks", "direction"]
        ).reset_index(drop=True)
        summary["scope"] = summary["scope"].astype(str)
        summary["direction"] = summary["direction"].astype(str)

    calibration_splits = _calibration_splits_from_summary(calibration_split_summary)
    candidates = backtest.calibration_candidate_search(
        labels,
        calibration_splits,
        horizons_weeks=CALIBRATION_HORIZONS_WEEKS,
        candidate_rules=_calibration_candidate_rules(),
        min_direction_signal_count=20,
    )
    candidate_config = _build_calibration_candidate_config(
        candidates=candidates,
        baseline_config=baseline_config,
        calibration_split_summary=calibration_split_summary,
    )

    date_values = (
        pd.to_datetime(labels["rebalance_date"]).dropna().sort_values()
        if "rebalance_date" in labels.columns
        else pd.DatetimeIndex([])
    )
    metadata = {
        "ticket": "B-163",
        "slice": "B-163.7",
        "purpose": "research_only_walk_forward_calibration_candidate_search_and_rerun_gate",
        "research_only": True,
        "live_promotion_allowed": False,
        "horizons_weeks": list(CALIBRATION_HORIZONS_WEEKS),
        "label_rows": int(len(labels)),
        "summary_rows": int(len(summary)),
        "candidate_rows": int(len(candidates)),
        "selected_candidate_count": (
            int(candidates["selected_by_calibration"].map(bool).sum())
            if "selected_by_calibration" in candidates.columns
            else 0
        ),
        "candidate_search_status": (
            "completed" if calibration_splits else "skipped_insufficient_history"
        ),
        "candidate_config_status": candidate_config["config_status"],
        "candidate_config_available": candidate_config["candidate_config_available"],
        "label_start": _date_or_none(pd.DatetimeIndex(date_values), 0),
        "label_end": _date_or_none(pd.DatetimeIndex(date_values), -1),
        "ticker_count": int(labels["ticker"].nunique()) if "ticker" in labels.columns else 0,
        "class_count": int(labels["class"].nunique()) if "class" in labels.columns else 0,
        "baseline_config_sha256": backtest.baseline_config_hash(baseline_config),
        "calibration_split_summary": calibration_split_summary,
        "ohlcv_source": ohlcv_source,
        "safety": {
            "parameter_tuning": "research_only_candidate_search",
            "candidate_promotion": "not_allowed",
            "live_scoring_change": "none",
            "calibrated_rerun": candidate_config["config_status"],
            "final_holdout": "not_evaluated",
        },
    }
    report = _format_calibration_baseline_report(
        summary,
        candidates=candidates,
        metadata=metadata,
    )
    return summary, report, metadata, candidates, candidate_config


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
        "snapshot_rebalance_count": 0,
        "snapshot_required_decisions": 0,
        "snapshot_available_count": 0,
        "snapshot_missing_count": 0,
        "snapshot_neutral_missing_count": 0,
        "snapshot_unusable_count": 0,
        "snapshot_passing_count": 0,
        "snapshot_below_threshold_count": 0,
        "snapshot_coverage_pct": None,
        "snapshot_audit_metadata_count": 0,
        "active_rebalances": 0,
        "active_oos_rebalances": 0,
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
        "snapshot_rebalance_count": 0,
        "snapshot_required_decisions": 0,
        "snapshot_available_count": 0,
        "snapshot_missing_count": 0,
        "snapshot_neutral_missing_count": 0,
        "snapshot_unusable_count": 0,
        "snapshot_passing_count": 0,
        "snapshot_below_threshold_count": 0,
        "snapshot_coverage_pct": None,
        "snapshot_audit_metadata_count": 0,
        "active_rebalances": 0,
        "active_oos_rebalances": 0,
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


def _empty_provider_flow_sweep_row(
    threshold: float,
    *,
    notes: str,
    ticker_count: int = 0,
    missing_tickers: str = "",
    coverage_by_ticker: str = "",
    snapshot_rebalance_count: int = 0,
    snapshot_required_decisions: int = 0,
    snapshot_missing_count: int = 0,
) -> dict:
    return {
        "row_type": "provider_feature_sweep",
        "variant": f"Block-trade upside ratio >= {threshold:g}",
        "provider": "massive",
        "endpoint": MASSIVE_TRADES_ENDPOINT,
        "status": "unavailable_no_historical_asof_snapshots",
        "coverage_start": "-",
        "coverage_end": "-",
        "coverage_rows": 0,
        "ticker_count": int(ticker_count),
        "missing_count": int(snapshot_missing_count),
        "missing_tickers": missing_tickers,
        "coverage_by_ticker": coverage_by_ticker,
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
        "snapshot_rebalance_count": int(snapshot_rebalance_count),
        "snapshot_required_decisions": int(snapshot_required_decisions),
        "snapshot_available_count": 0,
        "snapshot_missing_count": int(snapshot_missing_count),
        "snapshot_neutral_missing_count": int(snapshot_missing_count),
        "snapshot_unusable_count": 0,
        "snapshot_passing_count": 0,
        "snapshot_below_threshold_count": 0,
        "snapshot_coverage_pct": 0.0,
        "snapshot_audit_metadata_count": 0,
        "active_rebalances": 0,
        "active_oos_rebalances": 0,
        "promotion_label": "do not promote",
        "notes": notes,
    }


def _massive_provider_feature_sweep_rows() -> list[dict]:
    notes = (
        "The current trade-tape endpoint can inform live provider flow, but this runner has no "
        "persisted timestamped as-of snapshots for historical rebalances."
    )
    return [_empty_provider_flow_sweep_row(threshold, notes=notes) for threshold in MASSIVE_BLOCK_TRADE_THRESHOLDS]


def _massive_provider_missing_snapshot_sweep_rows(
    *,
    decisions: list[dict],
    target_weights: pd.DataFrame,
    tickers: list[str],
) -> list[dict]:
    missing_tickers = ", ".join(sorted({item["ticker"] for item in decisions}))
    coverage_by_ticker = _coverage_by_snapshot_ticker(decisions, tickers)
    notes = (
        "No stored Massive stock_trades snapshots were available as of the requested rebalances; "
        "missing snapshots were neutral and did not change baseline weights. Research only; use B-160 before promotion."
    )
    return [
        _empty_provider_flow_sweep_row(
            threshold,
            notes=notes,
            ticker_count=len(tickers),
            missing_tickers=missing_tickers,
            coverage_by_ticker=coverage_by_ticker,
            snapshot_rebalance_count=int(target_weights.shape[0]),
            snapshot_required_decisions=len(decisions),
            snapshot_missing_count=len(decisions),
        )
        for threshold in MASSIVE_BLOCK_TRADE_THRESHOLDS
    ]


def _snapshot_payload_has_audit_metadata(payload: dict) -> bool:
    request = payload.get("request")
    response = payload.get("response")
    return isinstance(request, dict) and isinstance(response, dict)


def _snapshot_ratio(record: provider_snapshots.ProviderSnapshotRecord) -> float | None:
    return provider_snapshots.block_trade_upside_ratio_from_snapshot(record)


def _provider_flow_promotion_label(row: dict) -> str:
    if row.get("status") != "replayed_snapshots":
        return "do not promote"
    if int(row.get("active_oos_rebalances", 0)) < MASSIVE_PROVIDER_FLOW_MIN_ACTIVE_OOS:
        return "needs more testing"
    oos_sharpe_delta = float(row.get("oos_sharpe_delta_vs_yfinance") or 0.0)
    oos_cagr_delta = float(row.get("oos_cagr_delta_vs_yfinance") or 0.0)
    oos_drawdown_delta = float(row.get("oos_max_drawdown_delta_vs_yfinance") or 0.0)
    full_sharpe_delta = float(row.get("sharpe_delta_vs_yfinance") or 0.0)
    if (
        oos_sharpe_delta >= 0.10
        and oos_cagr_delta >= 0.0
        and oos_drawdown_delta >= 0.0
        and full_sharpe_delta >= 0.0
    ):
        return "candidate"
    if oos_sharpe_delta <= 0.0 and oos_cagr_delta <= 0.0 and oos_drawdown_delta <= 0.0:
        return "do not promote"
    return "needs more testing"


def _coverage_by_snapshot_ticker(decisions: list[dict], tickers: list[str]) -> str:
    parts = []
    for ticker in tickers:
        as_of_values = sorted(
            {str(item["snapshot_as_of"]) for item in decisions if item["ticker"] == ticker and item.get("snapshot_as_of")}
        )
        if not as_of_values:
            parts.append(f"{ticker}:-")
            continue
        parts.append(f"{ticker}:{as_of_values[0]}->{as_of_values[-1]}({len(as_of_values)})")
    return "; ".join(parts)


def _provider_flow_decisions(
    *,
    snapshot_db_path: str | Path,
    target_weights: pd.DataFrame,
) -> list[dict]:
    decisions = []
    clean_targets = target_weights.copy()
    clean_targets.index = pd.to_datetime(clean_targets.index)
    for rebalance_date, weights in clean_targets.iterrows():
        as_of = pd.Timestamp(rebalance_date).date().isoformat()
        for ticker, weight in weights.items():
            try:
                numeric_weight = float(weight)
            except (TypeError, ValueError):
                continue
            if numeric_weight <= 0.0:
                continue
            record = provider_snapshots.load_provider_snapshot_as_of(
                snapshot_db_path,
                provider="massive",
                dataset="stock_trades",
                ticker=str(ticker),
                as_of=as_of,
            )
            if record is None:
                decisions.append(
                    {
                        "rebalance_date": pd.Timestamp(rebalance_date),
                        "ticker": str(ticker).upper(),
                        "weight": numeric_weight,
                        "ratio": None,
                        "snapshot_as_of": None,
                        "has_audit_metadata": False,
                    }
                )
                continue
            decisions.append(
                {
                    "rebalance_date": pd.Timestamp(rebalance_date),
                    "ticker": record.ticker,
                    "weight": numeric_weight,
                    "ratio": _snapshot_ratio(record),
                    "snapshot_as_of": record.as_of,
                    "has_audit_metadata": _snapshot_payload_has_audit_metadata(record.payload),
                }
            )
    return decisions


def _provider_flow_metric_fields(
    baseline: backtest.BacktestResult,
    variant: backtest.BacktestResult,
    oos_start: str | pd.Timestamp,
) -> dict:
    baseline_windows = backtest.split_backtest_metrics(baseline, oos_start=oos_start)
    variant_windows = backtest.split_backtest_metrics(variant, oos_start=oos_start)
    baseline_oos = baseline_windows["Out-of-sample"]
    variant_oos = variant_windows["Out-of-sample"]
    return {
        "cagr": variant.metrics["cagr"],
        "sharpe": variant.metrics["sharpe"],
        "max_drawdown": variant.metrics["max_drawdown"],
        "annualized_turnover": variant.metrics["annualized_turnover"],
        "oos_cagr": variant_oos["cagr"],
        "oos_sharpe": variant_oos["sharpe"],
        "oos_max_drawdown": variant_oos["max_drawdown"],
        "oos_annualized_turnover": variant_oos["annualized_turnover"],
        "cagr_delta_vs_yfinance": variant.metrics["cagr"] - baseline.metrics["cagr"],
        "sharpe_delta_vs_yfinance": variant.metrics["sharpe"] - baseline.metrics["sharpe"],
        "max_drawdown_delta_vs_yfinance": variant.metrics["max_drawdown"] - baseline.metrics["max_drawdown"],
        "oos_cagr_delta_vs_yfinance": variant_oos["cagr"] - baseline_oos["cagr"],
        "oos_sharpe_delta_vs_yfinance": variant_oos["sharpe"] - baseline_oos["sharpe"],
        "oos_max_drawdown_delta_vs_yfinance": variant_oos["max_drawdown"] - baseline_oos["max_drawdown"],
    }


def _build_massive_provider_flow_sweep_rows(
    *,
    snapshot_db_path: str | Path,
    prices: pd.DataFrame | None,
    target_weights: pd.DataFrame | None,
    oos_start: str | pd.Timestamp,
) -> list[dict]:
    if prices is None or target_weights is None or getattr(prices, "empty", True) or getattr(target_weights, "empty", True):
        return _massive_provider_feature_sweep_rows()
    strategy_columns = [column for column in target_weights.columns if column in prices.columns]
    if not strategy_columns:
        return _massive_provider_feature_sweep_rows()
    clean_prices = prices[strategy_columns].copy()
    clean_targets = target_weights[strategy_columns].copy()
    decisions = _provider_flow_decisions(snapshot_db_path=snapshot_db_path, target_weights=clean_targets)
    required_count = len(decisions)
    available = [item for item in decisions if item.get("snapshot_as_of")]
    if not available:
        return _massive_provider_missing_snapshot_sweep_rows(
            decisions=decisions,
            target_weights=clean_targets,
            tickers=[str(item) for item in strategy_columns],
        )

    snapshot_asofs = sorted({str(item["snapshot_as_of"]) for item in available})
    missing_tickers = sorted({item["ticker"] for item in decisions if not item.get("snapshot_as_of")})
    active_rebalance_dates = {pd.Timestamp(item["rebalance_date"]).normalize() for item in available}
    baseline = backtest.run_weight_backtest(clean_prices, clean_targets, transaction_cost_bps=5.0)
    oos_date = pd.Timestamp(oos_start)
    rows = []
    for threshold in MASSIVE_BLOCK_TRADE_THRESHOLDS:
        adjusted_targets = clean_targets.copy()
        passing_count = 0
        below_count = 0
        unusable_count = 0
        active_oos_dates = set()
        for item in decisions:
            ratio = item.get("ratio")
            if not item.get("snapshot_as_of"):
                continue
            if pd.Timestamp(item["rebalance_date"]) >= oos_date:
                active_oos_dates.add(pd.Timestamp(item["rebalance_date"]).normalize())
            if ratio is None:
                unusable_count += 1
                continue
            if float(ratio) >= float(threshold):
                passing_count += 1
                continue
            below_count += 1
            adjusted_targets.loc[item["rebalance_date"], item["ticker"]] = 0.0
        variant = backtest.run_weight_backtest(clean_prices, adjusted_targets, transaction_cost_bps=5.0)
        coverage_pct = len(available) / required_count if required_count else 0.0
        row = {
            "row_type": "provider_feature_sweep",
            "variant": f"Block-trade upside ratio >= {threshold:g}",
            "provider": "massive",
            "endpoint": MASSIVE_TRADES_ENDPOINT,
            "status": "replayed_snapshots",
            "coverage_start": snapshot_asofs[0],
            "coverage_end": snapshot_asofs[-1],
            "coverage_rows": int(len(available)),
            "ticker_count": int(len(strategy_columns)),
            "missing_count": int(required_count - len(available)),
            "missing_tickers": ", ".join(missing_tickers),
            "coverage_by_ticker": _coverage_by_snapshot_ticker(decisions, [str(item) for item in strategy_columns]),
            "threshold": float(threshold),
            "snapshot_rebalance_count": int(clean_targets.shape[0]),
            "snapshot_required_decisions": int(required_count),
            "snapshot_available_count": int(len(available)),
            "snapshot_missing_count": int(required_count - len(available)),
            "snapshot_neutral_missing_count": int(required_count - len(available)),
            "snapshot_unusable_count": int(unusable_count),
            "snapshot_passing_count": int(passing_count),
            "snapshot_below_threshold_count": int(below_count),
            "snapshot_coverage_pct": float(coverage_pct),
            "snapshot_audit_metadata_count": int(sum(1 for item in available if item.get("has_audit_metadata"))),
            "active_rebalances": int(len(active_rebalance_dates)),
            "active_oos_rebalances": int(len(active_oos_dates)),
            "notes": (
                "Replayed stored Massive stock_trades snapshots as of each rebalance; "
                "missing snapshots were neutral and did not change baseline weights. "
                "Research only; use B-160 before promotion."
            ),
        }
        row.update(_provider_flow_metric_fields(baseline, variant, oos_start=oos_start))
        row["promotion_label"] = _provider_flow_promotion_label(row)
        rows.append(row)
    return rows


def _build_massive_provider_validation_summary(
    *,
    enabled: bool,
    oos_start="2015-01-01",
    precomputed_provider_rows: list[dict] | None = None,
    prices: pd.DataFrame | None = None,
    target_weights: pd.DataFrame | None = None,
    snapshot_db_path: str | Path = provider_snapshots.DEFAULT_SNAPSHOT_DB_PATH,
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
    rows.extend(
        _build_massive_provider_flow_sweep_rows(
            snapshot_db_path=snapshot_db_path,
            prices=prices,
            target_weights=target_weights,
            oos_start=oos_start,
        )
    )
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
        "| Variant | Endpoint | Status | Threshold | Snapshot Coverage | Active OOS | OOS CAGR Delta | OOS Sharpe Delta | OOS Drawdown Delta | Label | Notes |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in rows.iterrows():
        lines.append(
            f"| {row.get('variant', '-')} | "
            f"{row.get('endpoint', '-')} | "
            f"{row.get('status', '-')} | "
            f"{_num(row.get('threshold'))} | "
            f"{_pct(row.get('snapshot_coverage_pct'))} | "
            f"{_int_text(row.get('active_oos_rebalances'))} | "
            f"{_pct(row.get('oos_cagr_delta_vs_yfinance'))} | "
            f"{_num(row.get('oos_sharpe_delta_vs_yfinance'))} | "
            f"{_pct(row.get('oos_max_drawdown_delta_vs_yfinance'))} | "
            f"{row.get('promotion_label', 'do not promote')} | "
            f"{row.get('notes', '')} |"
        )
    return lines


def _massive_provider_flow_snapshot_table(summary: pd.DataFrame) -> list[str]:
    rows = summary[summary.get("row_type") == "provider_feature_sweep"] if not summary.empty else pd.DataFrame()
    if rows.empty:
        return ["No provider-flow snapshot replay rows were produced."]
    lines = [
        "| Variant | Status | Snapshot Window | Rebalances | Decisions | Snapshot Coverage | Missing Neutral | Passing | Below Threshold | Active OOS | Audit Metadata | Label |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in rows.iterrows():
        window = f"{row.get('coverage_start', '-')} to {row.get('coverage_end', '-')}"
        lines.append(
            f"| {row.get('variant', '-')} | "
            f"{row.get('status', '-')} | "
            f"{window} | "
            f"{_int_text(row.get('snapshot_rebalance_count'))} | "
            f"{_int_text(row.get('snapshot_required_decisions'))} | "
            f"{_pct(row.get('snapshot_coverage_pct'))} | "
            f"{_int_text(row.get('snapshot_neutral_missing_count'))} | "
            f"{_int_text(row.get('snapshot_passing_count'))} | "
            f"{_int_text(row.get('snapshot_below_threshold_count'))} | "
            f"{_int_text(row.get('active_oos_rebalances'))} | "
            f"{_int_text(row.get('snapshot_audit_metadata_count'))} | "
            f"{row.get('promotion_label', 'do not promote')} |"
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
        "Ticket: B-159/B-162",
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
            "## Provider-Flow Snapshot Replay Coverage",
            "",
        ]
    )
    lines.extend(_massive_provider_flow_snapshot_table(massive_validation_summary))
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
            "- Massive trade-tape/block-trade sweeps replay only snapshots whose as-of date is on or before each rebalance.",
            "- Missing provider-flow snapshots are counted and kept neutral rather than filled from current provider data.",
            "- Use B-160 before any Massive-derived criterion changes scoring, alerts, vetoes, recommendations, provider-flow behavior, Pillar 7 weights, or broker behavior.",
            "",
            "## Decision",
            "",
            "Treat B-159/B-162 as research evidence only. Promote only through B-160 after review and deterministic tests.",
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
        baseline_config = backtest.frozen_baseline_config(
            universe=REQUIRED_TICKERS,
            benchmark_tickers=["AGG", "SPY", *SECTOR_BENCHMARK_TICKERS],
            ohlcv_provider=requested_provider,
            transaction_cost_bps=5.0,
            phase="MID",
        )
        calibration_split_summary = _build_calibration_split_summary(rebalance_dates)
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
                prices=prices[strategy_columns],
                target_weights=methodology_targets.target_weights,
                snapshot_db_path=args.provider_snapshot_db,
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
        (
            calibration_summary,
            calibration_report,
            calibration_metadata,
            calibration_candidates,
            calibration_candidate_config,
        ) = _build_calibration_baseline_artifacts(
            targets=methodology_targets,
            prices=prices,
            baseline_config=baseline_config,
            calibration_split_summary=calibration_split_summary,
            ohlcv_source=ohlcv_source,
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
            baseline_config=baseline_config,
            calibration_split_summary=calibration_split_summary,
            calibration_report=calibration_report,
            calibration_summary=calibration_summary,
            calibration_candidates=calibration_candidates,
            calibration_candidate_config=calibration_candidate_config,
            calibration_metadata=calibration_metadata,
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
