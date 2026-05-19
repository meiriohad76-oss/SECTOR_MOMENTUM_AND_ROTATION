"""Portfolio and single-ticker input parsing for the B-130 analyzer."""
from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class HoldingInput:
    ticker: str
    shares: float | None = None
    cost_basis: float | None = None
    market_value: float | None = None
    weight: float | None = None
    sector: str | None = None
    account: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class PortfolioInputError:
    message: str
    row_number: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class PortfolioInputResult:
    holdings: list[HoldingInput]
    errors: list[PortfolioInputError]


TICKER_COLUMNS = ("ticker", "symbol", "holding", "asset")
COLUMN_ALIASES = {
    "ticker": TICKER_COLUMNS,
    "shares": ("shares", "share", "quantity", "qty"),
    "cost_basis": ("cost_basis", "cost basis", "cost", "basis"),
    "market_value": ("market_value", "market value", "value", "current value"),
    "weight": ("weight", "allocation", "alloc", "portfolio weight"),
    "sector": ("sector",),
    "account": ("account", "account name"),
    "notes": ("notes", "note", "comment", "comments"),
}


def parse_single_ticker(value: str) -> PortfolioInputResult:
    ticker_text = _parse_text(value)
    ticker = normalize_ticker(value)
    if ticker is None:
        message = "ticker is required" if ticker_text is None else "ticker has invalid characters"
        return PortfolioInputResult(
            holdings=[],
            errors=[PortfolioInputError(message)],
        )
    return PortfolioInputResult(holdings=[HoldingInput(ticker=ticker, weight=1.0)], errors=[])


def parse_holdings_csv(payload: str | bytes) -> PortfolioInputResult:
    try:
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except UnicodeDecodeError as exc:
        return PortfolioInputResult([], [PortfolioInputError(f"could not read CSV file: {exc}")])
    except pd.errors.EmptyDataError:
        return PortfolioInputResult([], [PortfolioInputError("portfolio file is empty")])
    except pd.errors.ParserError as exc:
        return PortfolioInputResult([], [PortfolioInputError(f"could not read CSV file: {exc}")])
    return parse_holdings_frame(frame)


def parse_holdings_excel(payload: bytes) -> PortfolioInputResult:
    try:
        frame = pd.read_excel(io.BytesIO(payload), dtype=str, keep_default_na=False)
    except ValueError as exc:
        return PortfolioInputResult([], [PortfolioInputError(f"could not read Excel file: {exc}")])
    return parse_holdings_frame(frame)


def parse_holdings_frame(frame: pd.DataFrame) -> PortfolioInputResult:
    column_map = _build_column_map(frame.columns)
    ticker_column = column_map.get("ticker")
    if ticker_column is None:
        return PortfolioInputResult(
            holdings=[],
            errors=[PortfolioInputError("portfolio file must include a ticker column")],
        )

    holdings: list[HoldingInput] = []
    errors: list[PortfolioInputError] = []
    for idx, row in frame.iterrows():
        row_number = int(idx) + 2
        raw_ticker = row.get(ticker_column)
        ticker_text = _parse_text(raw_ticker)
        ticker = normalize_ticker(raw_ticker)
        if ticker is None:
            message = "ticker is required" if ticker_text is None else "ticker has invalid characters"
            errors.append(PortfolioInputError(message, row_number=row_number, column=ticker_column))
            continue

        shares = _parse_float_field(row, column_map, "shares", "shares", row_number, errors)
        cost_basis = _parse_float_field(row, column_map, "cost_basis", "cost_basis", row_number, errors)
        market_value = _parse_float_field(row, column_map, "market_value", "market_value", row_number, errors)
        weight = _parse_weight_field(row, column_map, row_number, errors)
        holdings.append(
            HoldingInput(
                ticker=ticker,
                shares=shares,
                cost_basis=cost_basis,
                market_value=market_value,
                weight=weight,
                sector=_parse_text(_row_value(row, column_map, "sector")),
                account=_parse_text(_row_value(row, column_map, "account")),
                notes=_parse_text(_row_value(row, column_map, "notes")),
            )
        )
    return PortfolioInputResult(holdings=holdings, errors=errors)


def normalize_ticker(value) -> str | None:
    text = _parse_text(value)
    if text is None:
        return None
    text = text.upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", text):
        return None
    return text


def _build_column_map(columns: Iterable[str]) -> dict[str, str]:
    normalized = {_normalize_header(column): column for column in columns}
    out: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            found = normalized.get(_normalize_header(alias))
            if found is not None:
                out[canonical] = found
                break
    return out


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _row_value(row: pd.Series, column_map: dict[str, str], key: str):
    column = column_map.get(key)
    if column is None:
        return None
    return row.get(column)


def _parse_float_field(
    row: pd.Series,
    column_map: dict[str, str],
    key: str,
    label: str,
    row_number: int,
    errors: list[PortfolioInputError],
) -> float | None:
    column = column_map.get(key)
    if column is None:
        return None
    raw_value = row.get(column)
    if _parse_text(raw_value) is None:
        return None
    value = _parse_float(raw_value)
    if value is None:
        errors.append(PortfolioInputError(f"{label} must be numeric", row_number=row_number, column=column))
    return value


def _parse_weight_field(
    row: pd.Series,
    column_map: dict[str, str],
    row_number: int,
    errors: list[PortfolioInputError],
) -> float | None:
    column = column_map.get("weight")
    if column is None:
        return None
    raw_value = row.get(column)
    if _parse_text(raw_value) is None:
        return None
    value = _parse_weight(raw_value)
    if value is None:
        errors.append(PortfolioInputError("weight must be numeric", row_number=row_number, column=column))
    return value


def _parse_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _parse_float(value) -> float | None:
    text = _parse_text(value)
    if text is None:
        return None
    text = text.replace(",", "").replace("$", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def _parse_weight(value) -> float | None:
    text = _parse_text(value)
    if text is None:
        return None
    had_percent = text.endswith("%")
    number = _parse_float(text)
    if number is None:
        return None
    if had_percent or number > 1.0:
        return number / 100.0
    return number
