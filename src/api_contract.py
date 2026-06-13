"""Pure API response contracts for the production dashboard migration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping, Any

from .data_health import dashboard_health_summary


API_VERSION = "v1"


def _utc_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _string_list(values: Iterable[Any] | None) -> list[str]:
    return [str(value) for value in (values or ())]


def normalize_health_lane(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe lane record for non-Streamlit clients."""
    providers = []
    for provider in row.get("providers", ()) or ():
        if not isinstance(provider, Mapping):
            continue
        providers.append(
            {
                "id": str(provider.get("id", "")),
                "label": str(provider.get("label", "Provider")),
                "provider": str(provider.get("provider", "")),
                "status": str(provider.get("status", "info")),
                "mode": str(provider.get("mode", provider.get("status", "unknown"))),
                "signal": str(provider.get("signal", "")),
                "detail": str(provider.get("detail", "")),
            }
        )
    return {
        "lane_id": str(row.get("lane_id", "")),
        "source": str(row.get("source", "Source")),
        "role": str(row.get("role", "")),
        "status": str(row.get("status", "warning")),
        "severity_symbol": str(row.get("severity_symbol", "")),
        "latest": str(row.get("latest", "-")),
        "freshness": str(row.get("freshness", "-")),
        "coverage": str(row.get("coverage", "")),
        "detail": str(row.get("detail", "")),
        "sla": str(row.get("sla", "")),
        "refresh_label": str(row.get("refresh_label", "")),
        "refresh_key": str(row.get("refresh_key", "")),
        "providers": providers,
    }


def build_dashboard_status_payload(
    health_rows: Iterable[Mapping[str, Any]],
    *,
    app_version: str,
    git_sha: str | None,
    generated_at: datetime | None = None,
    active_frontend: str = "streamlit",
) -> dict[str, Any]:
    """Build the first stable backend status payload for future clients.

    The contract is intentionally independent from Streamlit so a FastAPI
    service, CLI smoke test, or future React frontend can consume the same
    shape without importing ``app.py``.
    """
    lanes = [normalize_health_lane(row) for row in health_rows]
    summary = dashboard_health_summary(lanes)
    return {
        "api_version": API_VERSION,
        "generated_at": _utc_iso(generated_at),
        "app": {
            "name": "sector-momentum-dashboard",
            "version": str(app_version),
            "git_sha": str(git_sha or "unknown"),
            "active_frontend": str(active_frontend),
            "migration_stage": "streamlit_compat_api_foundation",
        },
        "health": {
            "status": summary["status"],
            "label": summary["label"],
            "detail": summary["detail"],
            "lane_count": len(lanes),
            "critical_statuses": _string_list(row.get("status") for row in lanes),
        },
        "lanes": lanes,
    }
