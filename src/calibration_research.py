"""Research-only statistical calibration helpers for B-164."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import universe


def _candidate_token(value: float) -> str:
    return str(value).replace("-", "minus_").replace(".", "_")


def _scope_token(scope: str) -> str:
    return scope.lower().replace(" ", "_").replace("-", "_")


def calibration_candidate_guardrail(
    config: dict,
    *,
    min_final_holdout_rows: int = 20,
) -> dict:
    """Validate that a calibrated candidate config is display-only and fail-closed."""

    reasons: list[str] = []
    selected = config.get("selected_candidate") if isinstance(config.get("selected_candidate"), dict) else {}
    safety = config.get("safety") if isinstance(config.get("safety"), dict) else {}
    promotion_label = str(selected.get("promotion_label") or "").strip().lower()
    final_holdout_evaluated = _scalar_bool(config.get("final_holdout_evaluated"))
    try:
        final_holdout_rows = int(config.get("final_holdout_rows_used") or 0)
    except (TypeError, ValueError):
        final_holdout_rows = 0

    if _scalar_bool(config.get("live_promotion_allowed")):
        reasons.append("config_live_promotion_true")
    if _scalar_bool(selected.get("live_promotion_allowed")):
        reasons.append("selected_candidate_live_promotion_true")
    if not _scalar_bool(config.get("research_only")):
        reasons.append("config_not_research_only")
    if safety.get("candidate_promotion") != "separate_ticket_required":
        reasons.append("missing_separate_ticket_requirement")
    if promotion_label in {"candidate", "research_candidate"} and not final_holdout_evaluated:
        reasons.append("candidate_without_final_holdout")
    if promotion_label in {"candidate", "research_candidate"} and final_holdout_rows < int(min_final_holdout_rows):
        reasons.append("insufficient_final_holdout_rows_for_candidate")
    if str(config.get("config_status") or "").startswith("passed_final_holdout") and not final_holdout_evaluated:
        reasons.append("passed_status_without_final_holdout")

    return {
        "status": "fail_closed" if reasons else "pass_display_only",
        "live_promotion_allowed": False,
        "requires_separate_ticket": True,
        "min_final_holdout_rows": int(min_final_holdout_rows),
        "reasons": reasons,
    }


def sector_override_guardrail(
    sector_overrides: pd.DataFrame,
    *,
    max_weight_multiplier: float = 1.25,
) -> dict:
    """Validate sector/class calibration overrides before any dashboard surfacing."""

    if sector_overrides is None or sector_overrides.empty:
        return {
            "status": "pass_no_overrides",
            "live_promotion_allowed": False,
            "requires_separate_ticket": True,
            "override_count": 0,
            "reasons": [],
        }
    frame = pd.DataFrame(sector_overrides).copy()
    reasons: list[str] = []
    required = {
        "sector",
        "promotion_label",
        "live_promotion_allowed",
        "promotion_requires",
        "sector_weight_multiplier",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        reasons.append("missing_columns:" + ",".join(missing))
        return {
            "status": "fail_closed",
            "live_promotion_allowed": False,
            "requires_separate_ticket": True,
            "override_count": int(len(frame)),
            "reasons": reasons,
        }

    sectors = frame["sector"].astype(str).str.upper()
    multipliers = pd.to_numeric(frame["sector_weight_multiplier"], errors="coerce")
    if not sectors.isin(set(universe.US_SECTORS)).all():
        reasons.append("non_us_sector_override")
    if not (frame["promotion_label"].astype(str) == "sector_candidate").all():
        reasons.append("unexpected_promotion_label")
    if _bool_series(frame["live_promotion_allowed"]).any():
        reasons.append("override_live_promotion_true")
    if not (
        frame["promotion_requires"].astype(str)
        == "separate_reviewed_live_promotion_ticket"
    ).all():
        reasons.append("missing_separate_review_requirement")
    if multipliers.isna().any() or (multipliers < 1.0).any() or (multipliers > float(max_weight_multiplier)).any():
        reasons.append("weight_multiplier_out_of_bounds")

    return {
        "status": "fail_closed" if reasons else "pass_display_only",
        "live_promotion_allowed": False,
        "requires_separate_ticket": True,
        "override_count": int(len(frame)),
        "max_weight_multiplier": float(max_weight_multiplier),
        "reasons": reasons,
    }


def expanded_candidate_grid() -> list[dict]:
    score_thresholds = [0.8, 1.0, 1.2]
    negative_thresholds = [0.0, -0.5, -1.0]
    scopes = ["global", "US Sectors", "US Industries", "Factors", "Mega-Cap Stocks"]
    rules: list[dict] = []

    def add_rules(prefix: str, *, scope: str, sector: str | None = None) -> None:
        base = {"scope": scope, "research_only": True}
        if sector is not None:
            base["sector"] = sector
        for threshold in score_thresholds:
            rules.append(
                {
                    **base,
                    "candidate_id": f"{prefix}_positive_score_ge_{_candidate_token(threshold)}",
                    "direction": "positive",
                    "positive_min_s_score_after_veto": threshold,
                    "relative_strength_min": None,
                }
            )
            rules.append(
                {
                    **base,
                    "candidate_id": (
                        f"{prefix}_positive_score_ge_{_candidate_token(threshold)}"
                        "_rel_strength_ge_0_0"
                    ),
                    "direction": "positive",
                    "positive_min_s_score_after_veto": threshold,
                    "relative_strength_min": 0.0,
                }
            )
        for threshold in negative_thresholds:
            rules.append(
                {
                    **base,
                    "candidate_id": f"{prefix}_negative_score_le_{_candidate_token(threshold)}",
                    "direction": "negative",
                    "negative_max_s_score_after_veto": threshold,
                }
            )

    for scope in scopes:
        add_rules(_scope_token(scope), scope=scope)
    for sector_ticker in universe.US_SECTORS:
        add_rules(sector_ticker.lower(), scope="US Sectors", sector=sector_ticker)
    return rules


def sector_override_candidates(
    rows,
    *,
    min_train_signals: int = 40,
    min_holdout_signals: int = 20,
    min_holdout_hit_rate_delta: float = 0.05,
) -> pd.DataFrame:
    frame = pd.DataFrame(rows).copy()
    required = {
        "train_signal_count",
        "holdout_signal_count",
        "holdout_hit_rate_delta_vs_baseline",
        "holdout_negative_hit_rate_delta_vs_baseline",
        "holdout_max_drawdown_delta_vs_baseline",
        "fold_stability_passed",
        "bootstrap_ci_low",
        "promotion_label",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"sector override rows missing required columns: {', '.join(missing)}")
    sector_values = frame.get("sector", pd.Series("", index=frame.index)).astype(str).str.upper()
    scope_values = frame.get("scope", pd.Series("", index=frame.index)).astype(str).str.strip()
    true_us_sector = (
        scope_values.eq("US Sectors")
        & sector_values.isin(set(universe.US_SECTORS))
    )
    mask = (
        true_us_sector
        & (pd.to_numeric(frame["train_signal_count"], errors="coerce") >= int(min_train_signals))
        & (pd.to_numeric(frame["holdout_signal_count"], errors="coerce") >= int(min_holdout_signals))
        & (
            pd.to_numeric(
                frame["holdout_hit_rate_delta_vs_baseline"],
                errors="coerce",
            )
            >= float(min_holdout_hit_rate_delta)
        )
        & (
            pd.to_numeric(
                frame["holdout_negative_hit_rate_delta_vs_baseline"],
                errors="coerce",
            )
            >= 0
        )
        & (
            pd.to_numeric(
                frame["holdout_max_drawdown_delta_vs_baseline"],
                errors="coerce",
            )
            >= 0
        )
        & _bool_series(frame["fold_stability_passed"])
        & (pd.to_numeric(frame["bootstrap_ci_low"], errors="coerce") >= 0)
        & (frame["promotion_label"].astype(str) == "research_candidate")
    )
    out = frame.loc[mask].copy()
    if out.empty:
        return out.reset_index(drop=True)
    improvement = pd.to_numeric(
        out["holdout_hit_rate_delta_vs_baseline"],
        errors="coerce",
    ).fillna(0.0)
    out["sector_weight_multiplier"] = (1.0 + improvement.clip(0, 0.25)).round(4)
    out["promotion_label"] = "sector_candidate"
    out["live_promotion_allowed"] = False
    out["promotion_requires"] = "separate_reviewed_live_promotion_ticket"
    out["live_promotion_allowed"] = out["live_promotion_allowed"].astype(object)
    return out.reset_index(drop=True)


def _zero_bootstrap_result(
    *,
    method: str,
    candidate_count: int = 0,
    baseline_count: int = 0,
    block_count: int = 0,
) -> dict:
    return {
        "method": method,
        "mean_delta": 0.0,
        "ci_low": 0.0,
        "ci_high": 0.0,
        "sample_count": int(baseline_count),
        "candidate_sample_count": int(candidate_count),
        "baseline_sample_count": int(baseline_count),
        "block_count": int(block_count),
        "valid_resample_count": 0,
        "invalid_resample_count": 0,
    }


def block_bootstrap_hit_rate_delta(
    baseline_success,
    candidate_flags,
    block_keys,
    *,
    samples: int = 1000,
    random_seed: int = 42,
) -> dict:
    """Bootstrap candidate-vs-baseline deltas over paired rebalance-date blocks."""
    sample_count = int(samples)
    if sample_count <= 0:
        raise ValueError("samples must be a positive integer")

    success = pd.to_numeric(pd.Series(baseline_success), errors="coerce")
    candidate = pd.Series(candidate_flags).map(_scalar_bool)
    blocks = pd.Series(block_keys)
    if not (len(success) == len(candidate) == len(blocks)):
        raise ValueError("baseline_success, candidate_flags, and block_keys must have equal length")

    frame = pd.DataFrame(
        {
            "success": success,
            "candidate": candidate.astype(bool),
            "block": blocks,
        }
    )
    frame = frame[frame["success"].notna()].copy()
    if frame.empty:
        return _zero_bootstrap_result(method="paired_block_by_rebalance_date")

    frame["block"] = frame["block"].where(frame["block"].notna(), frame.index)
    frame["block"] = frame["block"].astype(str)
    frame["candidate_success"] = frame["success"] * frame["candidate"].astype(int)

    baseline_count = int(len(frame))
    candidate_count = int(frame["candidate"].sum())
    block_count = int(frame["block"].nunique())
    if candidate_count == 0 or baseline_count == 0 or block_count == 0:
        return _zero_bootstrap_result(
            method="paired_block_by_rebalance_date",
            candidate_count=candidate_count,
            baseline_count=baseline_count,
            block_count=block_count,
        )

    observed = float(frame.loc[frame["candidate"], "success"].mean() - frame["success"].mean())
    stats = frame.groupby("block", sort=True).agg(
        baseline_success_sum=("success", "sum"),
        baseline_count=("success", "size"),
        candidate_success_sum=("candidate_success", "sum"),
        candidate_count=("candidate", "sum"),
    )
    baseline_success_sum = stats["baseline_success_sum"].to_numpy(dtype=float)
    baseline_counts = stats["baseline_count"].to_numpy(dtype=float)
    candidate_success_sum = stats["candidate_success_sum"].to_numpy(dtype=float)
    candidate_counts = stats["candidate_count"].to_numpy(dtype=float)

    rng = np.random.default_rng(int(random_seed))
    deltas: list[float] = []
    invalid_resample_count = 0
    for _ in range(sample_count):
        idx = rng.integers(0, len(stats), len(stats))
        sampled_baseline_count = baseline_counts[idx].sum()
        sampled_candidate_count = candidate_counts[idx].sum()
        if sampled_baseline_count == 0 or sampled_candidate_count == 0:
            invalid_resample_count += 1
            continue
        sampled_baseline_rate = baseline_success_sum[idx].sum() / sampled_baseline_count
        sampled_candidate_rate = candidate_success_sum[idx].sum() / sampled_candidate_count
        deltas.append(float(sampled_candidate_rate - sampled_baseline_rate))
    if not deltas:
        return {
            **_zero_bootstrap_result(
                method="paired_block_by_rebalance_date",
                candidate_count=candidate_count,
                baseline_count=baseline_count,
                block_count=block_count,
            ),
            "invalid_resample_count": sample_count,
        }

    return {
        "method": "paired_block_by_rebalance_date",
        "mean_delta": round(observed, 6),
        "ci_low": round(float(np.percentile(deltas, 2.5)), 6),
        "ci_high": round(float(np.percentile(deltas, 97.5)), 6),
        "sample_count": baseline_count,
        "candidate_sample_count": candidate_count,
        "baseline_sample_count": baseline_count,
        "block_count": block_count,
        "valid_resample_count": int(len(deltas)),
        "invalid_resample_count": int(invalid_resample_count),
    }


def bootstrap_hit_rate_delta(
    candidate_success,
    baseline_success,
    *,
    samples: int = 1000,
    random_seed: int = 42,
) -> dict:
    candidate = np.asarray(candidate_success, dtype=float)
    baseline = np.asarray(baseline_success, dtype=float)
    candidate = candidate[np.isfinite(candidate)]
    baseline = baseline[np.isfinite(baseline)]
    if len(candidate) == 0 or len(baseline) == 0:
        return {
            "mean_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "sample_count": 0,
            "candidate_sample_count": int(len(candidate)),
            "baseline_sample_count": int(len(baseline)),
        }
    sample_count = int(samples)
    if sample_count <= 0:
        raise ValueError("samples must be a positive integer")
    rng = np.random.default_rng(int(random_seed))
    deltas = []
    for _ in range(sample_count):
        candidate_idx = rng.integers(0, len(candidate), len(candidate))
        baseline_idx = rng.integers(0, len(baseline), len(baseline))
        deltas.append(float(candidate[candidate_idx].mean() - baseline[baseline_idx].mean()))
    return {
        "mean_delta": round(float(candidate.mean() - baseline.mean()), 6),
        "ci_low": round(float(np.percentile(deltas, 2.5)), 6),
        "ci_high": round(float(np.percentile(deltas, 97.5)), 6),
        "sample_count": int(len(candidate) + len(baseline)),
        "candidate_sample_count": int(len(candidate)),
        "baseline_sample_count": int(len(baseline)),
    }


def _positive_int(name: str, value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if number <= 0 or float(number) != float(value):
        raise ValueError(f"{name} must be a positive integer")
    return number


def _bool_series(series: pd.Series) -> pd.Series:
    return series.map(_scalar_bool).astype(bool)


def _scalar_bool(value) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _label_maturity_dates(labels: pd.DataFrame, horizon_weeks: int) -> pd.Series:
    column = f"label_end_date_{horizon_weeks}w"
    if column in labels.columns:
        return pd.to_datetime(labels[column], errors="coerce")
    return pd.to_datetime(labels["rebalance_date"], errors="coerce") + pd.DateOffset(
        weeks=horizon_weeks
    )


def _windowed_mature_labels(
    labels: pd.DataFrame,
    *,
    start: str,
    end: str,
    horizon_weeks: int,
) -> pd.DataFrame:
    frame = labels.copy()
    dates = pd.to_datetime(frame["rebalance_date"], errors="coerce")
    maturity_dates = _label_maturity_dates(frame, horizon_weeks)
    window_start = pd.Timestamp(start)
    window_end = pd.Timestamp(end)
    mask = (
        dates.notna()
        & (dates >= window_start)
        & (dates <= window_end)
        & maturity_dates.notna()
        & (maturity_dates <= window_end)
    )
    return frame.loc[mask].copy()


def _scope_frame(frame: pd.DataFrame, rule: dict) -> pd.DataFrame:
    scoped = frame.copy()
    scope = str(rule.get("scope") or "global")
    if scope.lower() != "global":
        if "class" in scoped.columns and (scoped["class"].astype(str) == scope).any():
            scoped = scoped[scoped["class"].astype(str) == scope]
        elif "sector" in scoped.columns and (scoped["sector"].astype(str) == scope).any():
            scoped = scoped[scoped["sector"].astype(str) == scope]
        else:
            return scoped.iloc[0:0].copy()
    sector = rule.get("sector")
    if sector is not None:
        if "sector" in scoped.columns and (scoped["sector"].astype(str) == str(sector)).any():
            scoped = scoped[scoped["sector"].astype(str) == str(sector)]
        elif "ticker" in scoped.columns:
            scoped = scoped[scoped["ticker"].astype(str).str.upper() == str(sector).upper()]
        else:
            return scoped.iloc[0:0].copy()
    return scoped


def _signal_mask(frame: pd.DataFrame, rule: dict, direction: str, *, candidate: bool) -> pd.Series:
    if direction == "positive":
        mask = _bool_series(frame["positive_signal"])
        if candidate and rule.get("positive_min_s_score_after_veto") is not None:
            score = pd.to_numeric(frame.get("S_score_after_veto"), errors="coerce")
            mask &= score.ge(float(rule["positive_min_s_score_after_veto"]))
        if candidate and rule.get("relative_strength_min") is not None:
            if "rs_ratio_z" not in frame.columns:
                mask &= False
            else:
                rs_ratio = pd.to_numeric(frame["rs_ratio_z"], errors="coerce")
                mask &= rs_ratio.ge(float(rule["relative_strength_min"]))
        return mask.astype(bool)
    if direction == "negative":
        mask = _bool_series(frame["negative_signal"])
        if candidate and rule.get("negative_max_s_score_after_veto") is not None:
            score = pd.to_numeric(frame.get("S_score_after_veto"), errors="coerce")
            mask &= score.le(float(rule["negative_max_s_score_after_veto"]))
        return mask.astype(bool)
    raise ValueError("direction must be positive or negative")


def _success_column(direction: str, horizon_weeks: int) -> str:
    if direction == "positive":
        return f"positive_success_{horizon_weeks}w"
    if direction == "negative":
        return f"negative_success_{horizon_weeks}w"
    raise ValueError("direction must be positive or negative")


def _metrics_for_signals(
    frame: pd.DataFrame,
    *,
    rule: dict,
    direction: str,
    horizon_weeks: int,
    candidate: bool,
) -> dict:
    if frame.empty:
        return {
            "signal_count": 0,
            "success_count": 0,
            "hit_rate": 0.0,
            "average_forward_return": 0.0,
            "average_forward_excess_return": 0.0,
            "average_post_entry_drawdown": 0.0,
            "success_values": [],
        }
    available_col = f"label_available_{horizon_weeks}w"
    success_col = _success_column(direction, horizon_weeks)
    required = {"positive_signal", "negative_signal", available_col, success_col}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"labels missing required columns: {', '.join(missing)}")
    signal = _signal_mask(frame, rule, direction, candidate=candidate)
    available = _bool_series(frame[available_col])
    selected = frame.loc[signal & available].copy()
    if selected.empty:
        return {
            "signal_count": 0,
            "success_count": 0,
            "hit_rate": 0.0,
            "average_forward_return": 0.0,
            "average_forward_excess_return": 0.0,
            "average_post_entry_drawdown": 0.0,
            "success_values": [],
        }
    success = _bool_series(selected[success_col])
    forward_return = pd.to_numeric(
        selected.get(f"forward_return_{horizon_weeks}w"),
        errors="coerce",
    )
    excess_return = pd.to_numeric(
        selected.get(f"forward_excess_return_{horizon_weeks}w"),
        errors="coerce",
    )
    drawdown = pd.to_numeric(
        selected.get(f"post_entry_drawdown_{horizon_weeks}w"),
        errors="coerce",
    )
    return {
        "signal_count": int(len(selected)),
        "success_count": int(success.sum()),
        "hit_rate": float(success.mean()) if len(success) else 0.0,
        "average_forward_return": float(forward_return.mean()) if forward_return.notna().any() else 0.0,
        "average_forward_excess_return": float(excess_return.mean()) if excess_return.notna().any() else 0.0,
        "average_post_entry_drawdown": float(drawdown.mean()) if drawdown.notna().any() else 0.0,
        "success_values": [int(value) for value in success.tolist()],
    }


def _bootstrap_for_rule(
    frame: pd.DataFrame,
    *,
    rule: dict,
    direction: str,
    horizon_weeks: int,
) -> dict:
    if frame.empty:
        return _zero_bootstrap_result(method="paired_block_by_rebalance_date")
    available_col = f"label_available_{horizon_weeks}w"
    success_col = _success_column(direction, horizon_weeks)
    required = {"positive_signal", "negative_signal", available_col, success_col}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"labels missing required columns: {', '.join(missing)}")
    available = _bool_series(frame[available_col])
    baseline_mask = _signal_mask(frame, rule, direction, candidate=False) & available
    baseline = frame.loc[baseline_mask].copy()
    if baseline.empty:
        return _zero_bootstrap_result(method="paired_block_by_rebalance_date")

    candidate_mask = _signal_mask(baseline, rule, direction, candidate=True)
    block_keys = (
        baseline["rebalance_date"]
        if "rebalance_date" in baseline.columns
        else pd.Series(baseline.index, index=baseline.index)
    )
    return block_bootstrap_hit_rate_delta(
        _bool_series(baseline[success_col]).astype(int),
        candidate_mask,
        block_keys,
        samples=500,
        random_seed=164,
    )


def _promotion_label(
    *,
    train_signal_count: int,
    holdout_signal_count: int,
    holdout_evaluated: bool,
    holdout_delta: float,
    fold_stability_passed: bool,
    bootstrap: dict,
    min_train_signals: int,
    min_holdout_signals: int,
) -> tuple[str, str]:
    if train_signal_count < min_train_signals or holdout_signal_count < min_holdout_signals:
        return "do not promote", "thin_sample"
    if not holdout_evaluated:
        return "do not promote", "no_mature_holdout_labels"
    if holdout_delta <= 0:
        return "needs more testing", "holdout_no_improvement"
    if not fold_stability_passed:
        return "needs more testing", "fold_unstable"
    if int(bootstrap.get("valid_resample_count", 1) or 0) <= 0:
        return "needs more testing", "bootstrap_insufficient_candidate_blocks"
    if float(bootstrap.get("ci_low", 0.0)) < 0:
        return "needs more testing", "bootstrap_interval_crosses_zero"
    return "research_candidate", "separate_live_promotion_ticket_required"


def evaluate_expanded_candidates(
    labels: pd.DataFrame,
    split: dict,
    *,
    candidate_rules: list[dict] | tuple[dict, ...],
    horizons_weeks=(13, 26, 52),
    min_train_signals: int = 40,
    min_holdout_signals: int = 20,
) -> pd.DataFrame:
    horizons = sorted({_positive_int("horizons_weeks", value) for value in horizons_weeks})
    min_train = _positive_int("min_train_signals", min_train_signals)
    min_holdout = _positive_int("min_holdout_signals", min_holdout_signals)
    if not candidate_rules:
        raise ValueError("candidate_rules must contain at least one rule")
    if split.get("status") != "ready":
        return pd.DataFrame(
            [
                {
                    "candidate_id": "split_not_ready",
                    "gate_status": "skipped_insufficient_history",
                    "promotion_label": "do not promote",
                    "live_promotion_allowed": False,
                    "research_only": True,
                }
            ]
        )
    frame = pd.DataFrame(labels).copy()
    if frame.empty:
        return pd.DataFrame()
    if "rebalance_date" not in frame.columns:
        raise ValueError("labels missing required column: rebalance_date")

    rows: list[dict] = []
    for horizon in horizons:
        train = _windowed_mature_labels(
            frame,
            start=split["train"]["start"],
            end=split["train"]["end"],
            horizon_weeks=horizon,
        )
        holdout = _windowed_mature_labels(
            frame,
            start=split["holdout"]["start"],
            end=split["holdout"]["end"],
            horizon_weeks=horizon,
        )
        for rule in candidate_rules:
            direction = str(rule.get("direction") or "positive").lower()
            scoped_train = _scope_frame(train, rule)
            scoped_holdout = _scope_frame(holdout, rule)
            baseline_train = _metrics_for_signals(
                scoped_train,
                rule=rule,
                direction=direction,
                horizon_weeks=horizon,
                candidate=False,
            )
            baseline_holdout = _metrics_for_signals(
                scoped_holdout,
                rule=rule,
                direction=direction,
                horizon_weeks=horizon,
                candidate=False,
            )
            candidate_train = _metrics_for_signals(
                scoped_train,
                rule=rule,
                direction=direction,
                horizon_weeks=horizon,
                candidate=True,
            )
            candidate_holdout = _metrics_for_signals(
                scoped_holdout,
                rule=rule,
                direction=direction,
                horizon_weeks=horizon,
                candidate=True,
            )
            train_delta = candidate_train["hit_rate"] - baseline_train["hit_rate"]
            holdout_delta = candidate_holdout["hit_rate"] - baseline_holdout["hit_rate"]
            drawdown_delta = (
                candidate_holdout["average_post_entry_drawdown"]
                - baseline_holdout["average_post_entry_drawdown"]
            )
            bootstrap = _bootstrap_for_rule(
                scoped_holdout,
                rule=rule,
                direction=direction,
                horizon_weeks=horizon,
            )
            holdout_evaluated = bool(candidate_holdout["signal_count"] > 0)
            fold_stability_passed = bool(train_delta >= 0 and holdout_delta >= 0)
            promotion_label, rejection_reasons = _promotion_label(
                train_signal_count=candidate_train["signal_count"],
                holdout_signal_count=candidate_holdout["signal_count"],
                holdout_evaluated=holdout_evaluated,
                holdout_delta=holdout_delta,
                fold_stability_passed=fold_stability_passed,
                bootstrap=bootstrap,
                min_train_signals=min_train,
                min_holdout_signals=min_holdout,
            )
            positive_delta = holdout_delta if direction == "positive" else 0.0
            negative_delta = holdout_delta if direction == "negative" else 0.0
            rows.append(
                {
                    "candidate_id": str(rule.get("candidate_id", "unknown")),
                    "scope": str(rule.get("scope") or "global"),
                    "sector": str(rule.get("sector") or rule.get("scope") or "global"),
                    "direction": direction,
                    "horizon_weeks": horizon,
                    "train_signal_count": candidate_train["signal_count"],
                    "holdout_signal_count": candidate_holdout["signal_count"],
                    "train_hit_rate": candidate_train["hit_rate"],
                    "holdout_hit_rate": candidate_holdout["hit_rate"],
                    "baseline_train_hit_rate": baseline_train["hit_rate"],
                    "baseline_holdout_hit_rate": baseline_holdout["hit_rate"],
                    "train_hit_rate_delta_vs_baseline": train_delta,
                    "holdout_hit_rate_delta_vs_baseline": holdout_delta,
                    "holdout_positive_hit_rate_delta_vs_baseline": positive_delta,
                    "holdout_negative_hit_rate_delta_vs_baseline": negative_delta,
                    "holdout_average_forward_return": candidate_holdout[
                        "average_forward_return"
                    ],
                    "holdout_average_forward_excess_return": candidate_holdout[
                        "average_forward_excess_return"
                    ],
                    "holdout_average_post_entry_drawdown": candidate_holdout[
                        "average_post_entry_drawdown"
                    ],
                    "baseline_holdout_average_post_entry_drawdown": baseline_holdout[
                        "average_post_entry_drawdown"
                    ],
                    "holdout_max_drawdown_delta_vs_baseline": drawdown_delta,
                    "bootstrap_mean_delta": bootstrap["mean_delta"],
                    "bootstrap_ci_low": bootstrap["ci_low"],
                    "bootstrap_ci_high": bootstrap["ci_high"],
                    "bootstrap_method": bootstrap["method"],
                    "bootstrap_sample_count": bootstrap["sample_count"],
                    "bootstrap_candidate_sample_count": bootstrap[
                        "candidate_sample_count"
                    ],
                    "bootstrap_baseline_sample_count": bootstrap[
                        "baseline_sample_count"
                    ],
                    "bootstrap_valid_resample_count": bootstrap.get(
                        "valid_resample_count",
                        0,
                    ),
                    "bootstrap_invalid_resample_count": bootstrap.get(
                        "invalid_resample_count",
                        0,
                    ),
                    "fold_stability_passed": fold_stability_passed,
                    "holdout_evaluated": holdout_evaluated,
                    "promotion_label": promotion_label,
                    "rejection_reasons": rejection_reasons,
                    "research_only": True,
                    "live_promotion_allowed": False,
                }
            )
    out = pd.DataFrame(rows)
    for column in (
        "fold_stability_passed",
        "holdout_evaluated",
        "research_only",
        "live_promotion_allowed",
    ):
        if column in out.columns:
            out[column] = _bool_series(out[column]).astype(object)
    return out.sort_values(["horizon_weeks", "candidate_id"], kind="mergesort").reset_index(
        drop=True
    )


# ── Task 9: Rank-IC per pillar + walk-forward weight grid ────────────────────

def _spearman_corr(a: pd.Series, b: pd.Series) -> float:
    """Spearman rank correlation without scipy (rank-then-Pearson)."""
    ra = a.rank().values.astype(float)
    rb = b.rank().values.astype(float)
    # np.corrcoef uses ddof=1 Pearson — equivalent to Spearman on ranked data
    mat = np.corrcoef(ra, rb)
    return float(mat[0, 1])

#: Ordered pillar z-score column names (default set for rank-IC evaluation).
PILLAR_Z_COLUMNS: tuple[str, ...] = (
    "mom_12_1_z",
    "mansfield_rs_z",
    "rs_ratio_z",
    "rs_momentum_z",
    "binary_filters_z",
    "breadth_50d_z",
    "provider_flow_z",
)


def rank_ic_per_pillar(
    scored_df: pd.DataFrame,
    *,
    forward_return_col: str = "forward_return",
    pillar_columns: tuple[str, ...] | list[str] | None = None,
    min_cross_section: int = 5,
) -> pd.DataFrame:
    """Per-pillar rank information coefficient (IC) computed cross-sectionally.

    For each pillar z-score column, computes the Spearman rank correlation
    between the pillar's cross-sectional rank and the forward class-relative
    return.  Reports mean IC, IC standard deviation, IC IR (mean/std), and
    IC t-statistic across rebalances.

    Parameters
    ----------
    scored_df : pd.DataFrame
        Must contain pillar z-score columns and a ``forward_return`` column.
        If the frame has a ``rebalance_date`` column it is used as the grouping
        key; otherwise the whole frame is treated as one rebalance.
    forward_return_col : str
        Column name for forward class-relative return.
    pillar_columns : sequence of str, optional
        Pillar z-score columns to evaluate.  Defaults to ``PILLAR_Z_COLUMNS``.
    min_cross_section : int
        Minimum instruments per rebalance to compute IC (avoids rank-IC on <5
        observations where Spearman correlation is unreliable).

    Returns
    -------
    pd.DataFrame
        One row per pillar with columns:
        ``pillar``, ``mean_ic``, ``ic_std``, ``ic_ir``, ``ic_t_stat``,
        ``n_rebalances``, ``valid_rebalances``.
    """
    cols = list(pillar_columns) if pillar_columns is not None else list(PILLAR_Z_COLUMNS)
    present = [c for c in cols if c in scored_df.columns]
    if forward_return_col not in scored_df.columns:
        raise ValueError(
            f"rank_ic_per_pillar requires column '{forward_return_col}'; "
            f"columns present: {list(scored_df.columns)}"
        )

    rebalance_col = "rebalance_date" if "rebalance_date" in scored_df.columns else None
    groups = (
        [grp for _, grp in scored_df.groupby(rebalance_col)]
        if rebalance_col
        else [scored_df]
    )

    ic_records: dict[str, list[float]] = {col: [] for col in present}
    for grp in groups:
        fwd = grp[forward_return_col].astype(float)
        if fwd.notna().sum() < min_cross_section:
            continue
        for col in present:
            pillar = grp[col].astype(float)
            both = pillar.notna() & fwd.notna()
            if both.sum() < min_cross_section:
                continue
            ic = _spearman_corr(pillar[both], fwd[both])
            if not np.isnan(ic):
                ic_records[col].append(ic)

    rows = []
    for col in present:
        ics = ic_records[col]
        n = len(ics)
        if n == 0:
            rows.append(
                {
                    "pillar": col,
                    "mean_ic": float("nan"),
                    "ic_std": float("nan"),
                    "ic_ir": float("nan"),
                    "ic_t_stat": float("nan"),
                    "n_rebalances": len(groups),
                    "valid_rebalances": 0,
                }
            )
            continue
        arr = np.array(ics, dtype=float)
        mean_ic = float(arr.mean())
        ic_std = float(arr.std(ddof=1)) if n > 1 else float("nan")
        ic_ir = mean_ic / ic_std if (not np.isnan(ic_std) and ic_std > 0) else float("nan")
        ic_t = (
            mean_ic / (ic_std / np.sqrt(n))
            if (not np.isnan(ic_std) and ic_std > 0 and n > 1)
            else float("nan")
        )
        rows.append(
            {
                "pillar": col,
                "mean_ic": mean_ic,
                "ic_std": ic_std,
                "ic_ir": ic_ir,
                "ic_t_stat": ic_t,
                "n_rebalances": len(groups),
                "valid_rebalances": n,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "pillar",
            "mean_ic",
            "ic_std",
            "ic_ir",
            "ic_t_stat",
            "n_rebalances",
            "valid_rebalances",
        ],
    )


def walk_forward_weight_grid(
    weight_candidates: list[dict],
    scored_df: pd.DataFrame,
    *,
    forward_return_col: str = "forward_return",
    min_cross_section: int = 5,
    equal_weight_label: str = "equal_weight",
) -> pd.DataFrame:
    """Evaluate a grid of pillar-weight candidates via rank-IC.

    For each candidate weight dict, computes a weighted composite z-score
    from the pillar z-scores in ``scored_df``, then measures rank-IC against
    the forward return.  The equal-weight candidate is automatically prepended
    as the honest benchmark.

    Parameters
    ----------
    weight_candidates : list of dict
        Each dict: ``{"label": str, "weights": {pillar_col: float, ...}}``.
        Weights need not sum to 1.0; they are renormalized internally so only
        the *relative* values matter.
    scored_df : pd.DataFrame
        Must contain pillar z-score columns and ``forward_return_col``.
    forward_return_col : str
        Column for forward class-relative return.
    min_cross_section : int
        Minimum instruments per group to compute IC.
    equal_weight_label : str
        Label for the auto-prepended equal-weight baseline.

    Returns
    -------
    pd.DataFrame
        One row per candidate with columns:
        ``label``, ``mean_ic``, ``ic_ir``, ``ic_t_stat``, ``valid_rebalances``,
        ``promotion_label``, ``weights``.

        ``promotion_label`` is ``"candidate"`` when mean_ic > 0 and ic_t > 1.0,
        ``"research_candidate"`` when mean_ic > 0 but t-stat is insufficient,
        ``"not_promoted"`` otherwise.

    Notes
    -----
    This is a research-only helper; ``promotion_label == "candidate"`` here
    only qualifies for the evidence gate (``evaluate_promotion_gate``), which
    itself requires ≥20 OOS rebalances and Sharpe/CAGR criteria beyond IC alone.
    No live ``DEFAULT_SCORING_CONFIG`` change is made automatically.
    """
    if forward_return_col not in scored_df.columns:
        raise ValueError(
            f"walk_forward_weight_grid requires '{forward_return_col}' column."
        )
    present_pillars = [c for c in PILLAR_Z_COLUMNS if c in scored_df.columns]

    # Always prepend equal-weight baseline if not already present
    candidates = list(weight_candidates)
    if not any(str(c.get("label")) == equal_weight_label for c in candidates):
        if present_pillars:
            ew = 1.0 / len(present_pillars)
            candidates = [
                {"label": equal_weight_label, "weights": {col: ew for col in present_pillars}}
            ] + candidates

    rebalance_col = "rebalance_date" if "rebalance_date" in scored_df.columns else None
    groups = (
        [grp for _, grp in scored_df.groupby(rebalance_col)]
        if rebalance_col
        else [scored_df]
    )

    rows = []
    for cand in candidates:
        label = str(cand.get("label", "unknown"))
        raw_weights: dict[str, float] = cand.get("weights", {})
        # Restrict to present pillars; renormalize so weights sum to 1.0
        active = {
            k: float(v)
            for k, v in raw_weights.items()
            if k in present_pillars and float(v) > 0
        }
        total = sum(active.values())
        norm_w = {k: v / total for k, v in active.items()} if total > 0 else {}

        ics: list[float] = []
        for grp in groups:
            fwd = grp[forward_return_col].astype(float)
            if fwd.notna().sum() < min_cross_section:
                continue
            composite = pd.Series(0.0, index=grp.index)
            for col, w in norm_w.items():
                if col in grp.columns:
                    composite = composite + w * grp[col].astype(float).fillna(0)
            both = composite.notna() & fwd.notna()
            if both.sum() < min_cross_section:
                continue
            ic = _spearman_corr(composite[both], fwd[both])
            if not np.isnan(ic):
                ics.append(ic)

        n = len(ics)
        if n == 0:
            rows.append(
                {
                    "label": label,
                    "mean_ic": float("nan"),
                    "ic_ir": float("nan"),
                    "ic_t_stat": float("nan"),
                    "valid_rebalances": 0,
                    "promotion_label": "not_promoted",
                    "weights": str(norm_w),
                }
            )
            continue

        arr = np.array(ics, dtype=float)
        mean_ic = float(arr.mean())
        ic_std = float(arr.std(ddof=1)) if n > 1 else float("nan")
        ic_ir = mean_ic / ic_std if (not np.isnan(ic_std) and ic_std > 0) else float("nan")
        ic_t = (
            mean_ic / (ic_std / np.sqrt(n))
            if (not np.isnan(ic_std) and ic_std > 0 and n > 1)
            else float("nan")
        )

        if mean_ic > 0 and not np.isnan(ic_t) and ic_t > 1.0:
            promo = "candidate"
        elif mean_ic > 0:
            promo = "research_candidate"
        else:
            promo = "not_promoted"

        rows.append(
            {
                "label": label,
                "mean_ic": mean_ic,
                "ic_ir": ic_ir,
                "ic_t_stat": ic_t,
                "valid_rebalances": n,
                "promotion_label": promo,
                "weights": str(norm_w),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "label",
            "mean_ic",
            "ic_ir",
            "ic_t_stat",
            "valid_rebalances",
            "promotion_label",
            "weights",
        ],
    )


# ── Task 10: Weight-perturbation robustness + state forward-return separation ─

def weight_perturbation_robustness(
    scored_df: pd.DataFrame,
    baseline_weights: dict[str, float],
    *,
    score_col: str = "S_score",
    perturbation_pp: float = 0.10,
    step_pp: float = 0.05,
    top_n: int = 10,
    pillar_columns: tuple[str, ...] | list[str] | None = None,
) -> dict:
    """Compute rank stability of a weight vector under uniform perturbations.

    For each pillar, shifts its weight by ±``perturbation_pp`` in ``step_pp``
    increments (redistributing the delta equally across the other pillars so
    weights remain positive and sum to 1).  For each perturbed vector, computes
    the Spearman rank correlation and top-N overlap against the baseline ranking.

    If ``score_col`` is absent from ``scored_df``, a weighted composite is built
    from ``pillar_columns`` using ``baseline_weights`` instead.

    Parameters
    ----------
    scored_df : pd.DataFrame
        Instrument-level data with the pillar z-score columns and optionally
        ``score_col`` for the baseline ranking.
    baseline_weights : dict[str, float]
        Current pillar weights (will be renormalized to sum=1).
    score_col : str
        Column holding the baseline composite score.
    perturbation_pp : float
        Maximum perturbation in weight-fraction units (0.10 = ±10 pp).
    step_pp : float
        Grid step size (0.05 = 5 pp grid).
    top_n : int
        Size of the "top-N" set for overlap measurement.
    pillar_columns : sequence of str, optional
        Which pillar z-score columns to perturb.  Defaults to ``PILLAR_Z_COLUMNS``.

    Returns
    -------
    dict with keys:
        ``rank_correlations`` — list of Spearman ρ per perturbation
        ``top_n_overlaps``    — list of top-N overlap fractions per perturbation
        ``mean_rank_correlation``
        ``min_rank_correlation``
        ``mean_top_n_overlap``
        ``min_top_n_overlap``
        ``n_perturbations``
        ``top_n``
    """
    cols = list(pillar_columns) if pillar_columns is not None else list(PILLAR_Z_COLUMNS)
    present = [c for c in cols if c in scored_df.columns and c in baseline_weights]

    # Normalise baseline weights over present pillars
    raw = {k: float(baseline_weights[k]) for k in present if float(baseline_weights.get(k, 0)) > 0}
    total = sum(raw.values())
    if total <= 0:
        return {
            "rank_correlations": [],
            "top_n_overlaps": [],
            "mean_rank_correlation": float("nan"),
            "min_rank_correlation": float("nan"),
            "mean_top_n_overlap": float("nan"),
            "min_top_n_overlap": float("nan"),
            "n_perturbations": 0,
            "top_n": top_n,
        }
    base_w = {k: v / total for k, v in raw.items()}

    # Build baseline composite / score series
    if score_col in scored_df.columns:
        base_scores = scored_df[score_col].astype(float)
    else:
        base_scores = pd.Series(0.0, index=scored_df.index)
        for col, w in base_w.items():
            base_scores = base_scores + w * scored_df[col].astype(float).fillna(0)

    base_ranks = base_scores.rank(ascending=False, method="min")
    base_top = set(base_scores.nlargest(top_n).index)

    rank_corrs: list[float] = []
    top_overlaps: list[float] = []

    steps = np.arange(step_pp, perturbation_pp + 1e-9, step_pp)
    directions = [1.0, -1.0]

    for pillar in present:
        other_pillars = [p for p in present if p != pillar]
        if not other_pillars:
            continue
        for direction in directions:
            for delta in steps:
                shift = direction * float(delta)
                new_pillar_w = base_w[pillar] + shift
                if new_pillar_w <= 0:
                    continue
                # Redistribute delta across other pillars proportionally
                redistrib = -shift / len(other_pillars)
                new_w = dict(base_w)
                new_w[pillar] = new_pillar_w
                for p in other_pillars:
                    new_w[p] = max(0.0, base_w[p] + redistrib)
                # Renormalise (redistribution may not be perfectly balanced)
                wsum = sum(new_w.values())
                if wsum <= 0:
                    continue
                new_w = {k: v / wsum for k, v in new_w.items()}

                perturbed = pd.Series(0.0, index=scored_df.index)
                for col, w in new_w.items():
                    if col in scored_df.columns:
                        perturbed = perturbed + w * scored_df[col].astype(float).fillna(0)

                both = base_scores.notna() & perturbed.notna()
                if both.sum() < 2:
                    continue
                rho = _spearman_corr(base_scores[both], perturbed[both])
                if not np.isnan(rho):
                    rank_corrs.append(rho)
                    perturbed_top = set(perturbed.nlargest(top_n).index)
                    overlap = len(base_top & perturbed_top) / max(top_n, 1)
                    top_overlaps.append(overlap)

    if not rank_corrs:
        return {
            "rank_correlations": [],
            "top_n_overlaps": [],
            "mean_rank_correlation": float("nan"),
            "min_rank_correlation": float("nan"),
            "mean_top_n_overlap": float("nan"),
            "min_top_n_overlap": float("nan"),
            "n_perturbations": 0,
            "top_n": top_n,
        }

    return {
        "rank_correlations": rank_corrs,
        "top_n_overlaps": top_overlaps,
        "mean_rank_correlation": float(np.mean(rank_corrs)),
        "min_rank_correlation": float(np.min(rank_corrs)),
        "mean_top_n_overlap": float(np.mean(top_overlaps)),
        "min_top_n_overlap": float(np.min(top_overlaps)),
        "n_perturbations": len(rank_corrs),
        "top_n": top_n,
    }


def state_forward_return_separation(
    scored_df: pd.DataFrame,
    *,
    forward_return_col: str = "forward_return",
    state_col: str = "state",
    state_order: list[str] | None = None,
) -> pd.DataFrame:
    """Compute per-state distribution of forward returns.

    Parameters
    ----------
    scored_df : pd.DataFrame
        Must contain ``state_col`` and ``forward_return_col``.
    state_order : list of str, optional
        Expected ordering of states from highest to lowest mean return.
        Default: [STAGE_2_BULLISH, HOLD, WARNING, EXIT, BEARISH_STAGE_4].

    Returns
    -------
    pd.DataFrame
        One row per state with columns:
        ``state``, ``mean_return``, ``median_return``, ``std_return``,
        ``count``, ``rank_by_mean``, ``expected_rank``, ``separation_met``.

        ``separation_met`` is True for all rows when the empirical ordering of
        states by mean return matches the expected ordering (higher states lead
        lower states in forward return).
    """
    _default_state_order = [
        "STAGE_2_BULLISH",
        "HOLD",
        "WARNING",
        "EXIT",
        "BEARISH_STAGE_4",
    ]
    order = list(state_order) if state_order is not None else _default_state_order

    if state_col not in scored_df.columns:
        raise ValueError(
            f"state_forward_return_separation requires column '{state_col}'."
        )
    if forward_return_col not in scored_df.columns:
        raise ValueError(
            f"state_forward_return_separation requires column '{forward_return_col}'."
        )

    df = scored_df[[state_col, forward_return_col]].copy()
    df[forward_return_col] = pd.to_numeric(df[forward_return_col], errors="coerce")

    rows = []
    for state in order:
        sub = df.loc[df[state_col] == state, forward_return_col].dropna()
        rows.append(
            {
                "state": state,
                "mean_return": float(sub.mean()) if len(sub) > 0 else float("nan"),
                "median_return": float(sub.median()) if len(sub) > 0 else float("nan"),
                "std_return": float(sub.std(ddof=1)) if len(sub) > 1 else float("nan"),
                "count": int(len(sub)),
            }
        )

    # Also add any states present in the data but not in the expected order
    extra_states = sorted(set(df[state_col].dropna().unique()) - set(order))
    for state in extra_states:
        sub = df.loc[df[state_col] == state, forward_return_col].dropna()
        rows.append(
            {
                "state": state,
                "mean_return": float(sub.mean()) if len(sub) > 0 else float("nan"),
                "median_return": float(sub.median()) if len(sub) > 0 else float("nan"),
                "std_return": float(sub.std(ddof=1)) if len(sub) > 1 else float("nan"),
                "count": int(len(sub)),
            }
        )

    result = pd.DataFrame(
        rows,
        columns=["state", "mean_return", "median_return", "std_return", "count"],
    )
    # Rank states by mean return (1 = highest)
    result["rank_by_mean"] = (
        result["mean_return"].rank(ascending=False, method="min", na_option="bottom").astype(int)
    )
    # Expected rank per the prescribed order (states not in order get NaN)
    expected_rank_map = {state: i + 1 for i, state in enumerate(order)}
    result["expected_rank"] = result["state"].map(expected_rank_map)

    # separation_met: for states IN the expected order, check empirical rank ≤ expected rank
    # (higher states should have higher or equal mean return, i.e. lower rank number)
    in_order = result["expected_rank"].notna()
    ordered_subset = result.loc[in_order].sort_values("expected_rank")
    mean_returns = ordered_subset["mean_return"].tolist()
    # Monotonic-non-increasing check (allow ties / NaN skipping)
    separation_ok = True
    prev = None
    for v in mean_returns:
        if np.isnan(v):
            continue
        if prev is not None and v > prev:
            separation_ok = False
            break
        prev = v

    result["separation_met"] = separation_ok
    return result.reset_index(drop=True)
