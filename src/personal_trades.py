"""Personal trade-history methodology alignment for B-132."""
from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Iterable

import pandas as pd

from .portfolio import normalize_ticker


@dataclass(frozen=True)
class TradeInput:
    trade_date: pd.Timestamp
    ticker: str
    side: str
    shares: float
    price: float
    fees: float = 0.0


@dataclass(frozen=True)
class TradeInputError:
    message: str
    row_number: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class TradeInputResult:
    trades: list[TradeInput]
    errors: list[TradeInputError]


@dataclass(frozen=True)
class TradeAlignmentRow:
    trade: TradeInput
    state_date: pd.Timestamp | None
    methodology_state: str | None
    alignment: str


@dataclass(frozen=True)
class TradeBacktestResult:
    rows: list[TradeAlignmentRow]
    aligned_count: int
    not_aligned_count: int
    unavailable_count: int


DATE_ALIASES = ("date", "trade date", "transaction date", "executed at")
TICKER_ALIASES = ("ticker", "symbol", "holding", "asset")
SIDE_ALIASES = ("side", "action", "transaction type", "type")
SHARES_ALIASES = ("shares", "quantity", "qty", "units")
PRICE_ALIASES = ("price", "fill price", "execution price")
FEE_ALIASES = ("fee", "fees", "commission", "commissions")
BUY_SIDES = {"BUY", "BOT", "B", "BOUGHT"}
SELL_SIDES = {"SELL", "SLD", "S", "SOLD"}
BUY_ALIGNED_STATES = {"STAGE_2_BULLISH", "HOLD"}
SELL_ALIGNED_STATES = {"WARNING", "EXIT", "BEARISH_STAGE_4"}


def parse_trade_history_csv(payload: str | bytes) -> TradeInputResult:
    try:
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except UnicodeDecodeError as exc:
        return TradeInputResult([], [TradeInputError(f"could not read CSV file: {exc}")])
    except pd.errors.EmptyDataError:
        return TradeInputResult([], [TradeInputError("trade file is empty")])
    except pd.errors.ParserError as exc:
        return TradeInputResult([], [TradeInputError(f"could not read CSV file: {exc}")])
    return parse_trade_history_frame(frame)


def parse_trade_history_excel(payload: bytes) -> TradeInputResult:
    try:
        frame = pd.read_excel(io.BytesIO(payload), dtype=str, keep_default_na=False)
    except (ImportError, OSError, ValueError, pd.errors.ParserError) as exc:
        return TradeInputResult([], [TradeInputError(f"could not read Excel file: {exc}")])
    return parse_trade_history_frame(frame)


def parse_trade_history_frame(frame: pd.DataFrame) -> TradeInputResult:
    column_map = _build_column_map(frame.columns)
    missing = [
        (key, label)
        for key, label in [
            ("date", "date"),
            ("ticker", "ticker"),
            ("side", "side/action"),
            ("shares", "shares"),
            ("price", "price"),
        ]
        if key not in column_map
    ]
    errors = [TradeInputError(f"trade file must include a {label} column") for _, label in missing]

    trades: list[TradeInput] = []
    for idx, row in frame.iterrows():
        row_number = int(idx) + 2
        parsed = _parse_trade_row(row, column_map, row_number, errors)
        if parsed is not None:
            trades.append(parsed)
    return TradeInputResult(trades=trades, errors=errors)


def evaluate_trade_history(trades: list[TradeInput], states: pd.DataFrame) -> TradeBacktestResult:
    clean_states = states.copy()
    clean_states.index = pd.to_datetime(clean_states.index)
    clean_states = clean_states.sort_index()
    rows = [_alignment_row(trade, clean_states) for trade in trades]
    aligned = sum(1 for row in rows if row.alignment == "ALIGNED")
    not_aligned = sum(1 for row in rows if row.alignment == "AGAINST_METHOD")
    unavailable = sum(1 for row in rows if row.alignment.startswith("NO_"))
    return TradeBacktestResult(
        rows=rows,
        aligned_count=aligned,
        not_aligned_count=not_aligned,
        unavailable_count=unavailable,
    )


def trade_alignment_frame(result: TradeBacktestResult) -> pd.DataFrame:
    rows = []
    for row in result.rows:
        rows.append(
            {
                "Date": row.trade.trade_date.date().isoformat(),
                "Ticker": row.trade.ticker,
                "Side": row.trade.side,
                "Shares": f"{row.trade.shares:,.2f}",
                "Price": f"${row.trade.price:,.2f}",
                "State Date": "-" if row.state_date is None else row.state_date.date().isoformat(),
                "Method State": row.methodology_state or "-",
                "Alignment": row.alignment,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["Date", "Ticker", "Side", "Shares", "Price", "State Date", "Method State", "Alignment"],
    )


def trade_alignment_summary_frame(result: TradeBacktestResult) -> pd.DataFrame:
    total = len(result.rows)
    aligned_rate = result.aligned_count / total if total else None
    return pd.DataFrame(
        [
            {"Metric": "Trades", "Value": str(total)},
            {"Metric": "Aligned", "Value": str(result.aligned_count)},
            {"Metric": "Against Method", "Value": str(result.not_aligned_count)},
            {"Metric": "Unavailable", "Value": str(result.unavailable_count)},
            {"Metric": "Aligned Rate", "Value": "-" if aligned_rate is None else f"{aligned_rate * 100:.1f}%"},
        ]
    )


def _alignment_row(trade: TradeInput, states: pd.DataFrame) -> TradeAlignmentRow:
    if trade.ticker not in states.columns:
        return TradeAlignmentRow(trade, None, None, "NO_METHOD_STATE")
    state_history = states.loc[states.index <= trade.trade_date, trade.ticker].dropna()
    if state_history.empty:
        return TradeAlignmentRow(trade, None, None, "NO_METHOD_STATE")
    state_date = pd.Timestamp(state_history.index[-1])
    state = str(state_history.iloc[-1]).upper()
    if trade.side == "BUY":
        alignment = "ALIGNED" if state in BUY_ALIGNED_STATES else "AGAINST_METHOD"
    else:
        alignment = "ALIGNED" if state in SELL_ALIGNED_STATES else "AGAINST_METHOD"
    return TradeAlignmentRow(trade, state_date, state, alignment)


def _parse_trade_row(
    row: pd.Series,
    column_map: dict[str, str],
    row_number: int,
    errors: list[TradeInputError],
) -> TradeInput | None:
    trade_date = _parse_date(_row_value(row, column_map, "date"))
    ticker = normalize_ticker(_row_value(row, column_map, "ticker"))
    side = _parse_side(_row_value(row, column_map, "side"))
    shares = _parse_float(_row_value(row, column_map, "shares"))
    price = _parse_float(_row_value(row, column_map, "price"))
    fees = _parse_float(_row_value(row, column_map, "fees")) or 0.0

    row_errors = []
    if trade_date is None:
        row_errors.append(("date", "date must be valid"))
    if ticker is None:
        row_errors.append(("ticker", "ticker is required or invalid"))
    if side is None:
        row_errors.append(("side", "side must be BUY or SELL"))
    if shares is None:
        row_errors.append(("shares", "shares must be numeric"))
    if price is None:
        row_errors.append(("price", "price must be numeric"))
    for key, message in row_errors:
        errors.append(TradeInputError(message, row_number=row_number, column=column_map.get(key)))
    if row_errors:
        return None
    return TradeInput(
        trade_date=pd.Timestamp(trade_date),
        ticker=str(ticker),
        side=str(side),
        shares=float(shares),
        price=float(price),
        fees=float(fees),
    )


def _build_column_map(columns: Iterable[str]) -> dict[str, str]:
    aliases = {
        "date": DATE_ALIASES,
        "ticker": TICKER_ALIASES,
        "side": SIDE_ALIASES,
        "shares": SHARES_ALIASES,
        "price": PRICE_ALIASES,
        "fees": FEE_ALIASES,
    }
    normalized = {_normalize_header(column): column for column in columns}
    out: dict[str, str] = {}
    for canonical, values in aliases.items():
        for value in values:
            found = normalized.get(_normalize_header(value))
            if found is not None:
                out[canonical] = found
                break
    return out


def _row_value(row: pd.Series, column_map: dict[str, str], key: str):
    column = column_map.get(key)
    return None if column is None else row.get(column)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _parse_date(value) -> pd.Timestamp | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).normalize()


def _parse_side(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip().upper()
    if normalized in BUY_SIDES:
        return "BUY"
    if normalized in SELL_SIDES:
        return "SELL"
    return None


def _parse_float(value) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    text = str(value).strip().replace(",", "").replace("$", "")
    try:
        parsed = float(text)
    except ValueError:
        return None
    if pd.isna(parsed):
        return None
    return parsed
