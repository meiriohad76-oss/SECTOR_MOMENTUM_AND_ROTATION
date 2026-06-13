"""Read-only persisted status provider for the optional dashboard API."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api_contract import build_dashboard_status_payload
from .provider_snapshots import DEFAULT_SNAPSHOT_DB_PATH, provider_snapshot_coverage
from .run_journal import DEFAULT_JOURNAL_PATH, list_runs
from .scoring import state_storage_health
from .universe import SCORED_TICKERS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _status_symbol(status: str) -> str:
    return {
        "healthy": "OK",
        "info": "INFO",
        "warning": "WARN",
        "stale": "STALE",
    }.get(status, "WARN")


def _state_lane() -> dict[str, Any]:
    health = state_storage_health()
    freshness = str(health.get("freshness_state") or "missing")
    healthy = (
        health.get("state_file_exists")
        and health.get("transition_journal_exists")
        and freshness != "stale"
    )
    status = "healthy" if healthy else "warning"
    age_seconds = health.get("state_updated_age_seconds")
    age_text = f"{int(age_seconds) // 3600}h old" if isinstance(age_seconds, int) else "age unknown"
    return {
        "lane_id": "state_persistence",
        "source": "Persisted state and transitions",
        "role": "Critical: durable state-machine memory for transitions, alerts, feeds, and debrief evidence",
        "status": status,
        "severity_symbol": _status_symbol(status),
        "latest": str(health.get("state_updated") or "-"),
        "freshness": (
            f"{health.get('by_ticker_count', 0)} states; "
            f"{health.get('journal_transition_count', 0)} journaled transitions; "
            f"{freshness} ({age_text})"
        ),
        "coverage": f"latest transition {health.get('latest_transition_date') or 'none'}",
        "detail": (
            f"state={health.get('state_file')}; "
            f"journal={health.get('transition_journal')}; "
            f"backups={health.get('backup_dir')}"
        ),
        "sla": "must persist across restarts",
        "refresh_label": "Read state persistence",
        "refresh_key": "api_status_state_persistence",
    }


def _run_journal_lane(journal_path: str | Path = DEFAULT_JOURNAL_PATH) -> dict[str, Any]:
    path = Path(journal_path)
    if not path.exists():
        status = "warning"
        latest = "-"
        freshness = "missing"
        detail = f"run journal missing at {path}"
        coverage = "0 runs"
    else:
        try:
            runs = list_runs(path, limit=1)
            if runs:
                latest_run = runs[0]
                status = "healthy"
                latest = str(latest_run.get("started_at_utc") or "-")
                freshness = f"latest run {latest}"
                coverage = f"universe {latest_run.get('universe_count', 0)}"
                detail = (
                    f"path={path}; provider={latest_run.get('provider') or 'unknown'}; "
                    f"git_sha={latest_run.get('git_sha') or 'unknown'}"
                )
            else:
                status = "warning"
                latest = "-"
                freshness = "empty"
                coverage = "0 runs"
                detail = f"run journal exists but has no runs: {path}"
        except Exception as exc:
            status = "warning"
            latest = "-"
            freshness = "unreadable"
            coverage = "read failed"
            detail = f"{type(exc).__name__}: {exc}"
    return {
        "lane_id": "run_journal",
        "source": "Run journal",
        "role": "Critical: append-only decision and recommendation evidence for debrief and backtesting",
        "status": status,
        "severity_symbol": _status_symbol(status),
        "latest": latest,
        "freshness": freshness,
        "coverage": coverage,
        "detail": detail,
        "sla": "append after dashboard scoring runs",
        "refresh_label": "Read run journal",
        "refresh_key": "api_status_run_journal",
    }


def _provider_snapshot_lane(
    snapshot_db_path: str | Path = DEFAULT_SNAPSHOT_DB_PATH,
    expected_tickers: tuple[str, ...] = SCORED_TICKERS,
) -> dict[str, Any]:
    coverage = provider_snapshot_coverage(
        snapshot_db_path,
        provider="massive",
        dataset="stock_trades",
        expected_tickers=expected_tickers,
    )
    state = str(coverage.get("state") or "missing")
    status = "healthy" if state == "ready" else "warning"
    covered = int(coverage.get("covered_ticker_count", 0) or 0)
    expected = int(coverage.get("expected_ticker_count", 0) or 0)
    missing = int(coverage.get("missing_ticker_count", 0) or 0)
    return {
        "lane_id": "provider_snapshots",
        "source": "Massive provider snapshots",
        "role": "Research: historical as-of provider-flow evidence for calibration and replay",
        "status": status,
        "severity_symbol": _status_symbol(status),
        "latest": str(coverage.get("latest_as_of") or "-"),
        "freshness": f"{state}; {covered}/{expected} tickers covered",
        "coverage": f"{missing} missing",
        "detail": f"path={coverage.get('path')}; latest captured {coverage.get('latest_captured_at_utc') or '-'}",
        "sla": "capture after market close for provider-flow replay",
        "refresh_label": "Read provider snapshots",
        "refresh_key": "api_status_provider_snapshots",
    }


def persisted_status_lanes(
    *,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    snapshot_db_path: str | Path = DEFAULT_SNAPSHOT_DB_PATH,
    expected_tickers: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Return read-only persisted artifact lanes for API consumers."""
    return [
        _state_lane(),
        _run_journal_lane(journal_path),
        _provider_snapshot_lane(snapshot_db_path, expected_tickers or SCORED_TICKERS),
    ]


def build_persisted_status_payload(
    *,
    app_version: str = "unknown",
    git_sha: str | None = None,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    snapshot_db_path: str | Path = DEFAULT_SNAPSHOT_DB_PATH,
    expected_tickers: tuple[str, ...] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return build_dashboard_status_payload(
        persisted_status_lanes(
            journal_path=journal_path,
            snapshot_db_path=snapshot_db_path,
            expected_tickers=expected_tickers,
        ),
        app_version=app_version,
        git_sha=git_sha,
        generated_at=generated_at or _utc_now(),
        active_frontend="api",
    )
