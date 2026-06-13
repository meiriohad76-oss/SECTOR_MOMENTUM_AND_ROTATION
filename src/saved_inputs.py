"""Local saved watchlist and portfolio persistence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

from .portfolio import HoldingInput, normalize_ticker


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAVED_INPUTS_PATH = ROOT / "data" / "saved_inputs.json"
STORE_VERSION = 1
VALID_KINDS = {"watchlist", "portfolio"}


@dataclass(frozen=True)
class SavedInput:
    kind: str
    name: str
    tickers: list[str]
    holdings: list[HoldingInput]
    updated_at: str


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    message: str
    item: SavedInput | None = None


def load_saved_inputs(path: str | Path | None = None) -> list[SavedInput]:
    store_path = _store_path(path)
    if not store_path.exists():
        return []
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []

    out: list[SavedInput] = []
    for item in items:
        parsed = _saved_input_from_payload(item)
        if parsed is not None:
            out.append(parsed)
    return sorted(out, key=lambda item: (item.kind, item.name.casefold()))


def save_watchlist(
    name: str,
    tickers: Iterable[str],
    path: str | Path | None = None,
    now: str | None = None,
) -> SaveResult:
    clean_name = _clean_name(name)
    if clean_name is None:
        return SaveResult(False, "name is required")

    clean_tickers = _normalize_tickers(tickers)
    if not clean_tickers:
        return SaveResult(False, "at least one valid ticker is required")

    item = SavedInput(
        kind="watchlist",
        name=clean_name,
        tickers=clean_tickers,
        holdings=[],
        updated_at=now or _utc_now(),
    )
    _upsert_saved_input(item, path)
    return SaveResult(True, f"saved watchlist {clean_name}", item)


def save_portfolio(
    name: str,
    holdings: Iterable[HoldingInput],
    path: str | Path | None = None,
    now: str | None = None,
) -> SaveResult:
    clean_name = _clean_name(name)
    if clean_name is None:
        return SaveResult(False, "name is required")

    clean_holdings = [holding for holding in holdings if normalize_ticker(holding.ticker)]
    if not clean_holdings:
        return SaveResult(False, "at least one valid holding is required")

    item = SavedInput(
        kind="portfolio",
        name=clean_name,
        tickers=[],
        holdings=clean_holdings,
        updated_at=now or _utc_now(),
    )
    _upsert_saved_input(item, path)
    return SaveResult(True, f"saved portfolio {clean_name}", item)


def delete_saved_input(kind: str, name: str, path: str | Path | None = None) -> bool:
    clean_kind = str(kind).strip().lower()
    clean_name = _clean_name(name)
    if clean_kind not in VALID_KINDS or clean_name is None:
        return False
    items = load_saved_inputs(path)
    keep = [item for item in items if not _same_identity(item, clean_kind, clean_name)]
    if len(keep) == len(items):
        return False
    _write_store(keep, path)
    return True


def _saved_input_from_payload(payload) -> SavedInput | None:
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("kind", "")).strip().lower()
    name = _clean_name(str(payload.get("name", "")))
    if kind not in VALID_KINDS or name is None:
        return None
    tickers = _normalize_tickers(payload.get("tickers", []))
    holdings = _holdings_from_payload(payload.get("holdings", []))
    updated_at = str(payload.get("updated_at") or "")
    return SavedInput(kind=kind, name=name, tickers=tickers, holdings=holdings, updated_at=updated_at)


def _holdings_from_payload(payload) -> list[HoldingInput]:
    if not isinstance(payload, list):
        return []
    holdings: list[HoldingInput] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ticker = normalize_ticker(item.get("ticker"))
        if ticker is None:
            continue
        holdings.append(
            HoldingInput(
                ticker=ticker,
                shares=_optional_float(item.get("shares")),
                cost_basis=_optional_float(item.get("cost_basis")),
                market_value=_optional_float(item.get("market_value")),
                weight=_optional_float(item.get("weight")),
                sector=_optional_text(item.get("sector")),
                account=_optional_text(item.get("account")),
                notes=_optional_text(item.get("notes")),
            )
        )
    return holdings


def _upsert_saved_input(item: SavedInput, path: str | Path | None) -> None:
    items = [
        existing
        for existing in load_saved_inputs(path)
        if not _same_identity(existing, item.kind, item.name)
    ]
    items.append(item)
    _write_store(items, path)


def _write_store(items: list[SavedInput], path: str | Path | None) -> None:
    store_path = _store_path(path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "items": [_payload_from_saved_input(item) for item in sorted(items, key=lambda row: (row.kind, row.name.casefold()))],
    }
    tmp_path = store_path.with_suffix(store_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(store_path)


def _payload_from_saved_input(item: SavedInput) -> dict:
    return {
        "kind": item.kind,
        "name": item.name,
        "tickers": list(item.tickers),
        "holdings": [asdict(holding) for holding in item.holdings],
        "updated_at": item.updated_at,
    }


def _same_identity(item: SavedInput, kind: str, name: str) -> bool:
    return item.kind == kind and item.name.casefold() == name.casefold()


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = normalize_ticker(raw)
        if ticker is None or ticker in seen:
            continue
        out.append(ticker)
        seen.add(ticker)
    return out


def _clean_name(name: str) -> str | None:
    cleaned = str(name or "").strip()
    return cleaned[:80] if cleaned else None


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _store_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_SAVED_INPUTS_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
