"""Read-only custom universe parsing and scored-snapshot analysis."""
from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Iterable

import pandas as pd

from .portfolio import (
    TICKER_COLUMNS,
    normalize_ticker,
)


@dataclass(frozen=True)
class CustomUniverseInputError:
    message: str
    token: str | None = None
    row_number: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class CustomUniverseInputResult:
    tickers: list[str]
    errors: list[CustomUniverseInputError]
    duplicate_tickers: list[str]


@dataclass(frozen=True)
class CustomUniverseAnalysisRow:
    ticker: str
    custom_rank: int | None
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
class CustomUniverseAnalysis:
    rows: list[CustomUniverseAnalysisRow]
    available_tickers: list[str]
    missing_tickers: list[str]
    class_counts: dict[str, int]
    state_counts: dict[str, int]
    action_tickers: dict[str, list[str]]


DISPLAY_COLUMNS = [
    "Custom Rank",
    "Ticker",
    "Class",
    "State",
    "S",
    "F",
    "Class Rank",
    "Selected",
    "Veto",
]


def parse_custom_universe_text(value: str) -> CustomUniverseInputResult:
    """Parse comma, semicolon, newline, or whitespace separated ticker text."""
    text = str(value or "").strip()
    if not text:
        return CustomUniverseInputResult(tickers=[], errors=[], duplicate_tickers=[])

    tickers: list[str] = []
    errors: list[CustomUniverseInputError] = []
    for token in [part for part in re.split(r"[\s,;]+", text) if part]:
        ticker = normalize_ticker(token)
        if ticker is None:
            errors.append(CustomUniverseInputError("ticker has invalid characters", token=token))
            continue
        tickers.append(ticker)

    unique, duplicates = _dedupe_tickers(tickers)
    return CustomUniverseInputResult(tickers=unique, errors=errors, duplicate_tickers=duplicates)


def parse_custom_universe_file(payload: str | bytes, filename: str) -> CustomUniverseInputResult:
    """Parse a ticker-list CSV/XLS/XLSX file using B-130 ticker column aliases."""
    lowered = str(filename or "").lower()
    try:
        if lowered.endswith((".xlsx", ".xls")):
            frame = pd.read_excel(io.BytesIO(_ensure_bytes(payload)), dtype=str, keep_default_na=False)
        else:
            text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
            frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except UnicodeDecodeError as exc:
        return CustomUniverseInputResult([], [CustomUniverseInputError(f"could not read CSV file: {exc}")], [])
    except pd.errors.EmptyDataError:
        return CustomUniverseInputResult([], [CustomUniverseInputError("custom universe file is empty")], [])
    except pd.errors.ParserError as exc:
        return CustomUniverseInputResult([], [CustomUniverseInputError(f"could not read CSV file: {exc}")], [])
    except (ImportError, OSError, ValueError) as exc:
        return CustomUniverseInputResult([], [CustomUniverseInputError(f"could not read Excel file: {exc}")], [])
    return _parse_custom_universe_frame(frame)


def _parse_custom_universe_frame(frame: pd.DataFrame) -> CustomUniverseInputResult:
    ticker_column = _ticker_column(frame.columns)
    if ticker_column is None:
        return CustomUniverseInputResult(
            tickers=[],
            errors=[CustomUniverseInputError("custom universe file must include a ticker column")],
            duplicate_tickers=[],
        )

    tickers: list[str] = []
    errors: list[CustomUniverseInputError] = []
    for idx, row in frame.iterrows():
        row_number = int(idx) + 2
        raw_ticker = row.get(ticker_column)
        ticker_text = _cell_text(raw_ticker)
        ticker = normalize_ticker(raw_ticker)
        if ticker is None:
            message = "ticker is required" if ticker_text is None else "ticker has invalid characters"
            errors.append(CustomUniverseInputError(message, row_number=row_number, column=ticker_column))
            continue
        tickers.append(ticker)

    unique, duplicates = _dedupe_tickers(tickers)
    return CustomUniverseInputResult(tickers=unique, errors=errors, duplicate_tickers=duplicates)


def analyze_custom_universe(tickers: list[str], scored_df: pd.DataFrame) -> CustomUniverseAnalysis:
    """Join a custom ticker list to the current scored snapshot without mutation."""
    if not scored_df.index.is_unique:
        raise ValueError("scored_df index must contain unique tickers")

    unique_tickers, _ = _dedupe_tickers([ticker for ticker in tickers if ticker])
    matched: list[tuple[str, pd.Series]] = []
    missing_tickers: list[str] = []

    for ticker in unique_tickers:
        if ticker in scored_df.index:
            matched.append((ticker, scored_df.loc[ticker]))
        else:
            missing_tickers.append(ticker)

    matched.sort(key=lambda item: _sort_score(item[1].get("S_score")))

    rows: list[CustomUniverseAnalysisRow] = []
    available_tickers: list[str] = []
    class_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    action_tickers = {"exit": [], "warning": [], "bullish": []}

    for custom_rank, (ticker, scored) in enumerate(matched, start=1):
        state = _optional_text(scored.get("state"))
        asset_class = _optional_text(scored.get("class"))
        selected = _optional_bool(scored.get("selected"))
        row = CustomUniverseAnalysisRow(
            ticker=ticker,
            custom_rank=custom_rank,
            state=state,
            asset_class=asset_class,
            s_score=_optional_float(scored.get("S_score")),
            f_score=_optional_float(scored.get("F_score")),
            rank_in_class=_optional_float(scored.get("rank_in_class")),
            selected=selected,
            veto=_optional_bool(scored.get("veto")),
        )
        rows.append(row)
        available_tickers.append(ticker)
        _add_count(class_counts, asset_class or "UNKNOWN")
        _add_count(state_counts, state or "UNKNOWN")
        _add_action_ticker(action_tickers, ticker, state, selected)

    for ticker in missing_tickers:
        rows.append(
            CustomUniverseAnalysisRow(
                ticker=ticker,
                custom_rank=None,
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
        _add_count(class_counts, "MISSING")
        _add_count(state_counts, "MISSING")

    return CustomUniverseAnalysis(
        rows=rows,
        available_tickers=available_tickers,
        missing_tickers=missing_tickers,
        class_counts=class_counts,
        state_counts=state_counts,
        action_tickers=action_tickers,
    )


def custom_universe_rows_frame(analysis: CustomUniverseAnalysis) -> pd.DataFrame:
    rows = []
    for row in analysis.rows:
        rows.append(
            {
                "Custom Rank": _format_rank(row.custom_rank),
                "Ticker": row.ticker,
                "Class": "MISSING" if row.missing else _display_label(row.asset_class),
                "State": "MISSING" if row.missing else _display_label(row.state),
                "S": _format_number(row.s_score),
                "F": _format_number(row.f_score),
                "Class Rank": _format_rank(row.rank_in_class),
                "Selected": _format_bool(row.selected),
                "Veto": _format_bool(row.veto),
            }
        )
    return pd.DataFrame(rows, columns=DISPLAY_COLUMNS)


def summary_counts_frame(counts: dict[str, int], label: str) -> pd.DataFrame:
    rows = [
        {label: _display_label(key), "Count": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]
    return pd.DataFrame(rows, columns=[label, "Count"])


def _dedupe_tickers(tickers: Iterable[str]) -> tuple[list[str], list[str]]:
    seen: set[str] = set()
    duplicates: list[str] = []
    unique: list[str] = []
    duplicate_seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).upper()
        if ticker in seen:
            if ticker not in duplicate_seen:
                duplicates.append(ticker)
                duplicate_seen.add(ticker)
            continue
        seen.add(ticker)
        unique.append(ticker)
    return unique, duplicates


def _ensure_bytes(payload: str | bytes) -> bytes:
    return payload.encode("utf-8") if isinstance(payload, str) else payload


def _ticker_column(columns: Iterable[str]) -> str | None:
    normalized = {_normalize_header(column): column for column in columns}
    for alias in TICKER_COLUMNS:
        found = normalized.get(_normalize_header(alias))
        if found is not None:
            return found
    return None


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _cell_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _sort_score(value) -> tuple[int, float]:
    score = _optional_float(value)
    if score is None:
        return (1, 0.0)
    return (0, -score)


def _optional_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _optional_bool(value) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0"}:
        return False
    return None


def _add_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _add_action_ticker(
    action_tickers: dict[str, list[str]],
    ticker: str,
    state: str | None,
    selected: bool | None,
) -> None:
    if state in {"EXIT", "BEARISH_STAGE_4"}:
        action_tickers["exit"].append(ticker)
    elif state == "WARNING":
        action_tickers["warning"].append(ticker)
    elif state == "STAGE_2_BULLISH" or selected is True:
        action_tickers["bullish"].append(ticker)


def _display_label(value: str | None) -> str:
    if value is None:
        return "-"
    return str(value).replace("_", " ")


def _format_number(value: float | None) -> str:
    parsed = _optional_float(value)
    return "-" if parsed is None else f"{parsed:.2f}"


def _format_rank(value: float | int | None) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "-"
    return str(int(parsed)) if float(parsed).is_integer() else f"{parsed:.1f}"


def _format_bool(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "-"
