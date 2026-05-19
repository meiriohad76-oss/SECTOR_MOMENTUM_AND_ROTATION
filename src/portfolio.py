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


@dataclass(frozen=True)
class HoldingAnalysisRow:
    ticker: str
    analysis_weight: float
    input_weight: float | None
    market_value: float | None
    state: str | None
    asset_class: str | None
    s_score: float | None
    f_score: float | None
    rank_in_class: float | None
    selected: bool | None
    veto: bool | None
    missing: bool = False
    missing_reason: str | None = None


@dataclass(frozen=True)
class PortfolioAnalysis:
    rows: list[HoldingAnalysisRow]
    missing_tickers: list[str]
    state_exposure: dict[str, float]
    class_exposure: dict[str, float]
    action_tickers: dict[str, list[str]]


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


def analyze_holdings(holdings: list[HoldingInput], scored_df: pd.DataFrame) -> PortfolioAnalysis:
    if not scored_df.index.is_unique:
        raise ValueError("scored_df index must contain unique tickers")

    weights = _analysis_weights(holdings)
    rows: list[HoldingAnalysisRow] = []
    missing_tickers: list[str] = []
    state_exposure: dict[str, float] = {}
    class_exposure: dict[str, float] = {}
    action_tickers = {"exit": [], "warning": [], "bullish": []}

    for holding, weight in zip(holdings, weights):
        if holding.ticker not in scored_df.index:
            rows.append(
                HoldingAnalysisRow(
                    ticker=holding.ticker,
                    analysis_weight=weight,
                    input_weight=holding.weight,
                    market_value=holding.market_value,
                    state=None,
                    asset_class=None,
                    s_score=None,
                    f_score=None,
                    rank_in_class=None,
                    selected=None,
                    veto=None,
                    missing=True,
                    missing_reason="ticker not found in scored universe",
                )
            )
            missing_tickers.append(holding.ticker)
            _add_exposure(state_exposure, "MISSING", weight)
            _add_exposure(class_exposure, "MISSING", weight)
            continue

        scored = scored_df.loc[holding.ticker]
        state = _optional_text(scored.get("state"))
        asset_class = _optional_text(scored.get("class"))
        row = HoldingAnalysisRow(
            ticker=holding.ticker,
            analysis_weight=weight,
            input_weight=holding.weight,
            market_value=holding.market_value,
            state=state,
            asset_class=asset_class,
            s_score=_optional_float(scored.get("S_score")),
            f_score=_optional_float(scored.get("F_score")),
            rank_in_class=_optional_float(scored.get("rank_in_class")),
            selected=_optional_bool(scored.get("selected")),
            veto=_optional_bool(scored.get("veto")),
        )
        rows.append(row)
        _add_exposure(state_exposure, state or "UNKNOWN", weight)
        _add_exposure(class_exposure, asset_class or "UNKNOWN", weight)
        _add_action_ticker(action_tickers, holding.ticker, state)

    return PortfolioAnalysis(
        rows=rows,
        missing_tickers=missing_tickers,
        state_exposure=state_exposure,
        class_exposure=class_exposure,
        action_tickers=action_tickers,
    )


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


def _analysis_weights(holdings: list[HoldingInput]) -> list[float]:
    if not holdings:
        return []

    explicit = [holding.weight for holding in holdings]
    if all(weight is not None and weight >= 0 for weight in explicit):
        total = float(sum(weight for weight in explicit if weight is not None))
        if total > 0:
            return [float(weight or 0.0) / total for weight in explicit]

    values = [holding.market_value for holding in holdings]
    if all(value is not None and value > 0 for value in values):
        total = float(sum(value for value in values if value is not None))
        if total > 0:
            return [float(value or 0.0) / total for value in values]

    equal_weight = 1.0 / len(holdings)
    return [equal_weight for _ in holdings]


def _optional_text(value) -> str | None:
    return _parse_text(value)


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = _parse_text(value)
    if text is None:
        return None
    normalized = text.strip().lower()
    if normalized in {"true", "t", "yes", "y", "1"}:
        return True
    if normalized in {"false", "f", "no", "n", "0"}:
        return False
    return None


def _add_exposure(exposures: dict[str, float], key: str, weight: float) -> None:
    exposures[key] = exposures.get(key, 0.0) + float(weight)


def _add_action_ticker(action_tickers: dict[str, list[str]], ticker: str, state: str | None) -> None:
    if state in {"EXIT", "BEARISH_STAGE_4"}:
        action_tickers["exit"].append(ticker)
    elif state == "WARNING":
        action_tickers["warning"].append(ticker)
    elif state == "STAGE_2_BULLISH":
        action_tickers["bullish"].append(ticker)


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
