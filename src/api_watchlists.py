"""Saved watchlist API payloads (mirrors the saved portfolio endpoints)."""
from __future__ import annotations

from typing import Any, Mapping

from .saved_inputs import delete_saved_input, load_saved_inputs, save_watchlist


def build_saved_watchlists_payload(path=None) -> dict[str, Any]:
    """Return locally saved watchlists without running analysis or provider fetches."""
    items = [item for item in load_saved_inputs(path) if item.kind == "watchlist"]
    return {
        "api_version": "v1",
        "status": "ready",
        "watchlist_count": len(items),
        "watchlists": [
            {"name": item.name, "tickers": list(item.tickers), "updated_at": item.updated_at}
            for item in items
        ],
    }


def save_saved_watchlist_payload(request: Mapping[str, Any] | None, *, path=None) -> dict[str, Any]:
    """Persist one named watchlist. Tickers may be a list or a comma/space/newline string."""
    body = dict(request or {})
    name = str(body.get("name") or "").strip()
    raw = body.get("tickers") or []
    if isinstance(raw, str):
        tickers = raw.replace(",", " ").replace("\n", " ").split()
    else:
        tickers = [str(t) for t in raw]
    result = save_watchlist(name, tickers, path=path)
    if not result.ok:
        return {"api_version": "v1", "status": "error", "message": result.message}
    return {"api_version": "v1", "status": "ready", "message": result.message}


def delete_saved_watchlist_payload(name: str, *, path=None) -> dict[str, Any]:
    deleted = delete_saved_input("watchlist", name, path=path)
    return {
        "api_version": "v1",
        "status": "ready" if deleted else "not_found",
        "deleted": bool(deleted),
        "name": name,
    }
