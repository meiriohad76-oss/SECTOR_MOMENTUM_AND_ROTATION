"""Small helpers for dashboard rerun performance auditing."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter, time
from typing import Any, Iterator


VISUAL_STATE_KEYS = (
    "theme",
    "bluf_mode",
    "view_density",
    "sparkline_style",
    "color_palette",
    "preference_profile_choice",
    "preference_profile_name",
    "preference_profile_error",
    "preference_profile_message",
)
COMPUTE_SNAPSHOT_KEYS = ("ohlcv_result", "ohlcv", "fred_data", "regime", "scored", "created_at")
DASHBOARD_COMPUTE_SNAPSHOT_TTL_SECONDS = 3600
SESSION_STATE_KEYS = VISUAL_STATE_KEYS + (
    "klass",
    "drill_ticker",
    "drill_range",
    "comparison_tickers",
    "portfolio_analyzer_mode",
    "portfolio_single_ticker",
    "portfolio_single_source",
    "portfolio_upload",
    "saved_portfolio_select",
    "loaded_portfolio_name",
    "save_portfolio_name",
    "custom_universe_mode",
    "custom_universe_text",
    "custom_universe_upload",
    "saved_watchlist_select",
    "loaded_watchlist_name",
    "save_watchlist_name",
    "table_open",
    "table_sort",
    "sort_choice",
)


@dataclass(frozen=True)
class RerunClassification:
    kind: str
    changed_keys: tuple[str, ...] = ()


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def session_snapshot(
    session_state: Mapping[str, Any],
    keys: tuple[str, ...] = SESSION_STATE_KEYS,
) -> tuple[tuple[str, str], ...]:
    """Return a stable subset of Streamlit session state for rerun classification."""
    return tuple((key, _string_value(session_state.get(key))) for key in keys)


def classify_rerun(
    previous: tuple[tuple[str, str], ...] | None,
    current: tuple[tuple[str, str], ...],
) -> RerunClassification:
    if previous is None:
        return RerunClassification("initial")

    previous_values = dict(previous)
    current_values = dict(current)
    keys = tuple(dict.fromkeys([*previous_values.keys(), *current_values.keys()]))
    changed = tuple(
        key
        for key in keys
        if previous_values.get(key, "") != current_values.get(key, "")
    )
    if not changed:
        return RerunClassification("unchanged")
    if all(key in VISUAL_STATE_KEYS for key in changed):
        return RerunClassification("visual_only", changed)
    return RerunClassification("interactive", changed)


def should_reuse_dashboard_compute(
    classification: RerunClassification,
    snapshot: Mapping[str, Any] | None,
    *,
    now: float | None = None,
    max_age_seconds: int = DASHBOARD_COMPUTE_SNAPSHOT_TTL_SECONDS,
) -> bool:
    """Return whether a prior dashboard compute snapshot is safe to reuse."""
    if classification.kind != "visual_only" or snapshot is None:
        return False
    if not all(key in snapshot for key in COMPUTE_SNAPSHOT_KEYS):
        return False
    try:
        created_at = float(snapshot["created_at"])
    except (TypeError, ValueError):
        return False
    age_seconds = (time() if now is None else now) - created_at
    return 0 <= age_seconds <= max_age_seconds


@dataclass
class DashboardPerformanceAudit:
    timer: Callable[[], float] = perf_counter
    durations_ms: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        start = self.timer()
        try:
            yield
        finally:
            elapsed_ms = round((self.timer() - start) * 1000, 3)
            self.durations_ms[name] = round(self.durations_ms.get(name, 0.0) + elapsed_ms, 3)
