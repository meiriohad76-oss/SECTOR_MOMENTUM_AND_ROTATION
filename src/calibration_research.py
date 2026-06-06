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
