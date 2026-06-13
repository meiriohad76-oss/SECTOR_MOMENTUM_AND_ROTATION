"""Saved portfolio API payloads for the B-170 React migration."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .api_portfolio import parse_portfolio_request
from .saved_inputs import delete_saved_input, load_saved_inputs, save_portfolio


def build_saved_portfolios_payload(path: str | Path | None = None) -> dict[str, Any]:
    """Return locally saved portfolios without running analysis or provider fetches."""

    portfolios = [
        item
        for item in load_saved_inputs(path)
        if item.kind == "portfolio" and item.holdings
    ]
    return {
        "api_version": "v1",
        "status": "ready",
        "portfolio_count": len(portfolios),
        "portfolios": [_portfolio_payload(item) for item in portfolios],
    }


def save_saved_portfolio_payload(
    request: Mapping[str, Any] | None,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Persist one named portfolio from the same request shape used by analysis."""

    body = dict(request or {})
    name = str(body.get("name") or "").strip()
    parsed = parse_portfolio_request(body)
    if parsed.errors:
        return {
            "api_version": "v1",
            "status": "invalid",
            "message": "Portfolio input could not be parsed.",
            "errors": [
                {"message": error.message, "row_number": error.row_number, "column": error.column}
                for error in parsed.errors
            ],
            "portfolio": None,
        }

    result = save_portfolio(name, parsed.holdings, path=path)
    if not result.ok:
        return {
            "api_version": "v1",
            "status": "invalid",
            "message": result.message,
            "errors": [{"message": result.message, "row_number": None, "column": None}],
            "portfolio": None,
        }
    return {
        "api_version": "v1",
        "status": "ready",
        "message": result.message,
        "errors": [],
        "portfolio": _portfolio_payload(result.item) if result.item is not None else None,
    }


def delete_saved_portfolio_payload(
    name: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    deleted = delete_saved_input("portfolio", name, path=path)
    return {
        "api_version": "v1",
        "status": "deleted" if deleted else "missing",
        "message": "saved portfolio deleted" if deleted else "saved portfolio not found",
        "deleted": deleted,
    }


def _portfolio_payload(item) -> dict[str, Any]:
    return {
        "name": item.name,
        "updated_at": item.updated_at,
        "holding_count": len(item.holdings),
        "holdings": [asdict(holding) for holding in item.holdings],
    }
