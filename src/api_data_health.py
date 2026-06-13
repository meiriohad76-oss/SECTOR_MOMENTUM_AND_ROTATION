"""Read-only data/provider health payloads for the optional dashboard API."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .api_contract import build_dashboard_status_payload
from .api_status import _status_symbol, persisted_status_lanes
from .provider_flow_cache import DEFAULT_CACHE_DB_PATH, provider_flow_cache_coverage
from .provider_snapshots import DEFAULT_SNAPSHOT_DB_PATH
from .run_journal import DEFAULT_JOURNAL_PATH
from .universe import SCORED_TICKERS


PROVIDER_FLOW_CACHE_LANES = (
    "massive_block_trades",
    "finra_ats_dark_pool",
    "finra_short_interest",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _status_rank(status: str) -> int:
    return {"healthy": 0, "info": 0, "warning": 1, "stale": 2}.get(str(status), 1)


def _worst_status(statuses: Iterable[str], default: str = "warning") -> str:
    return max([str(status) for status in statuses] or [default], key=_status_rank)


def _provider_flow_statuses() -> list[dict[str, str]]:
    from .flow import provider_flow_health_statuses

    return provider_flow_health_statuses()


def _provider_flow_feeds_stubbed(statuses: Iterable[Mapping[str, Any]]) -> bool:
    from .flow import provider_flow_feeds_stubbed

    return provider_flow_feeds_stubbed([dict(row) for row in statuses])


def _provider_flow_lane(provider_statuses: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    providers = [dict(row) for row in (provider_statuses if provider_statuses is not None else _provider_flow_statuses())]
    status = _worst_status(str(row.get("status", "info")) for row in providers)
    stubbed = _provider_flow_feeds_stubbed(providers)
    enabled = [
        row
        for row in providers
        if row.get("id") != "ohlcv_derived" and not str(row.get("mode", "")).startswith("stubbed")
    ]
    return {
        "lane_id": "provider_flow_readiness",
        "source": "Provider-flow readiness",
        "role": "Provider configuration and latest in-process readiness for institutional-flow signals",
        "status": status,
        "severity_symbol": _status_symbol(status),
        "latest": "-",
        "freshness": "all optional feeds neutral" if stubbed else f"{len(enabled)} optional feeds enabled",
        "coverage": f"{len(providers)} provider rows",
        "detail": (
            "Read-only readiness; this endpoint does not call providers. "
            "Live provider runtime details update when the dashboard or headless refresh computes flow."
        ),
        "sla": "provider status is configuration/runtime metadata; data coverage is tracked in provider-flow cache",
        "refresh_label": "Read provider-flow readiness",
        "refresh_key": "api_data_health_provider_flow_readiness",
        "providers": providers,
    }


def _provider_flow_cache_lane(
    *,
    cache_path: str | Path = DEFAULT_CACHE_DB_PATH,
    expected_tickers: tuple[str, ...] = SCORED_TICKERS,
    cache_lanes: tuple[str, ...] = PROVIDER_FLOW_CACHE_LANES,
) -> dict[str, Any]:
    coverage = provider_flow_cache_coverage(
        tickers=expected_tickers,
        lanes=cache_lanes,
        path=cache_path,
    )
    state = str(coverage.get("state") or "missing")
    status = "healthy" if state == "ready" else "warning"
    covered = int(coverage.get("covered_pair_count", 0) or 0)
    expected = int(coverage.get("expected_pair_count", 0) or 0)
    missing = int(coverage.get("missing_pair_count", 0) or 0)
    return {
        "lane_id": "provider_flow_cache",
        "source": "Provider-flow cache",
        "role": "Persistent provider response cache used by headless refresh and provider-flow observability",
        "status": status,
        "severity_symbol": _status_symbol(status),
        "latest": str(coverage.get("latest_created_at_utc") or "-"),
        "freshness": f"{state}; {covered}/{expected} lane-ticker pairs covered",
        "coverage": f"{missing} missing pairs",
        "detail": f"path={coverage.get('path')}; missing sample={coverage.get('missing_pairs', [])[:5]}",
        "sla": "warm before scoring refresh; missing pairs fall back neutral or stale-cache according to runner mode",
        "refresh_label": "Read provider-flow cache",
        "refresh_key": "api_data_health_provider_flow_cache",
    }


def provider_data_health_lanes(
    *,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    snapshot_db_path: str | Path = DEFAULT_SNAPSHOT_DB_PATH,
    cache_path: str | Path = DEFAULT_CACHE_DB_PATH,
    expected_tickers: tuple[str, ...] | None = None,
    provider_flow_statuses: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    tickers = expected_tickers or SCORED_TICKERS
    return [
        *persisted_status_lanes(
            journal_path=journal_path,
            snapshot_db_path=snapshot_db_path,
            expected_tickers=tickers,
        ),
        _provider_flow_lane(provider_flow_statuses),
        _provider_flow_cache_lane(cache_path=cache_path, expected_tickers=tickers),
    ]


def build_provider_data_health_payload(
    *,
    app_version: str = "unknown",
    git_sha: str | None = None,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    snapshot_db_path: str | Path = DEFAULT_SNAPSHOT_DB_PATH,
    cache_path: str | Path = DEFAULT_CACHE_DB_PATH,
    expected_tickers: tuple[str, ...] | None = None,
    provider_flow_statuses: Iterable[Mapping[str, Any]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    lanes = provider_data_health_lanes(
        journal_path=journal_path,
        snapshot_db_path=snapshot_db_path,
        cache_path=cache_path,
        expected_tickers=expected_tickers,
        provider_flow_statuses=provider_flow_statuses,
    )
    payload = build_dashboard_status_payload(
        lanes,
        app_version=app_version,
        git_sha=git_sha,
        generated_at=generated_at or _utc_now(),
        active_frontend="api",
    )
    provider_lane = next((lane for lane in lanes if lane.get("lane_id") == "provider_flow_readiness"), {})
    providers = list(provider_lane.get("providers", []) or [])
    payload["provider_flow"] = {
        "provider_count": len(providers),
        "enabled_provider_count": sum(
            1
            for row in providers
            if row.get("id") != "ohlcv_derived" and not str(row.get("mode", "")).startswith("stubbed")
        ),
        "stubbed": bool(_provider_flow_feeds_stubbed(providers)),
    }
    return payload
