# B-130 Portfolio / Single-Stock Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first B-130 slice: a pure parser/validation core for one ticker, CSV portfolios, and Excel portfolios.

**Architecture:** Add `src/portfolio.py` with typed input objects and parser functions that return holdings plus row-level validation errors. This slice must not import Streamlit, fetch data, write `state.json`, or join against the methodology scores yet.

**Tech Stack:** Python 3, pandas, pytest, Streamlit for the later UI, existing `src.scoring` output, optional `openpyxl` via pandas for Excel uploads.

---

## Files

- Create: `src/portfolio.py`
- Create: `tests/test_portfolio.py`
- Modify later: `requirements.txt`
- Modify: `docs/BACKLOG.md`

---

### Task 1: Input Parsing And Validation Core

**Files:**
- Create: `src/portfolio.py`
- Create: `tests/test_portfolio.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_portfolio.py`:

```python
from __future__ import annotations

import io

import pandas as pd
import pytest

from src import portfolio


def test_parse_single_ticker_normalizes_symbol_to_one_full_weight_holding():
    result = portfolio.parse_single_ticker(" xlk ")

    assert result.errors == []
    assert len(result.holdings) == 1
    assert result.holdings[0].ticker == "XLK"
    assert result.holdings[0].weight == pytest.approx(1.0)


def test_parse_holdings_csv_accepts_aliases_and_normalizes_weights():
    csv_text = """Symbol,Quantity,Market Value,Weight,Account,Notes
xlk,10,"2,500",25%,IRA,core technology
xlf,5,1250,25,Taxable,financial sleeve
"""

    result = portfolio.parse_holdings_csv(csv_text)

    assert result.errors == []
    assert [holding.ticker for holding in result.holdings] == ["XLK", "XLF"]
    assert result.holdings[0].shares == pytest.approx(10.0)
    assert result.holdings[0].market_value == pytest.approx(2500.0)
    assert result.holdings[0].weight == pytest.approx(0.25)
    assert result.holdings[0].account == "IRA"
    assert result.holdings[1].weight == pytest.approx(0.25)


def test_parse_holdings_csv_reports_blank_ticker_rows_without_dropping_valid_rows():
    csv_text = """ticker,shares,weight
XLK,10,0.5
,4,0.5
XLF,5,50%
"""

    result = portfolio.parse_holdings_csv(csv_text)

    assert [holding.ticker for holding in result.holdings] == ["XLK", "XLF"]
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 3
    assert "ticker is required" in result.errors[0].message


def test_parse_holdings_csv_reports_missing_ticker_column():
    result = portfolio.parse_holdings_csv("name,shares\nTechnology,10\n")

    assert result.holdings == []
    assert len(result.errors) == 1
    assert result.errors[0].row_number is None
    assert "ticker column" in result.errors[0].message


def test_parse_holdings_excel_accepts_xlsx_bytes():
    frame = pd.DataFrame({"Ticker": ["xlk", "xlf"], "Weight": ["60%", "40%"]})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)

    result = portfolio.parse_holdings_excel(buffer.getvalue())

    assert result.errors == []
    assert [holding.ticker for holding in result.holdings] == ["XLK", "XLF"]
    assert [holding.weight for holding in result.holdings] == pytest.approx([0.6, 0.4])
```

- [ ] **Step 2: Run parser tests and verify they fail**

Run:

```bash
python -m pytest tests/test_portfolio.py -q
```

Expected: fail because `src.portfolio` does not exist yet.

- [ ] **Step 3: Add Excel dependency**

Modify `requirements.txt`:

```text
openpyxl>=3.1
```

- [ ] **Step 4: Implement minimal parser core**

Create `src/portfolio.py`:

```python
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
    ticker = normalize_ticker(value)
    if ticker is None:
        return PortfolioInputResult(
            holdings=[],
            errors=[PortfolioInputError("ticker is required")],
        )
    return PortfolioInputResult(holdings=[HoldingInput(ticker=ticker, weight=1.0)], errors=[])


def parse_holdings_csv(payload: str | bytes) -> PortfolioInputResult:
    text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return PortfolioInputResult([], [PortfolioInputError("portfolio file is empty")])
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
            [],
            [PortfolioInputError("portfolio file must include a ticker column")],
        )

    holdings: list[HoldingInput] = []
    errors: list[PortfolioInputError] = []
    for idx, row in frame.iterrows():
        row_number = int(idx) + 2
        ticker = normalize_ticker(row.get(ticker_column))
        if ticker is None:
            errors.append(PortfolioInputError("ticker is required", row_number=row_number, column=ticker_column))
            continue

        holdings.append(
            HoldingInput(
                ticker=ticker,
                shares=_parse_float(_row_value(row, column_map, "shares")),
                cost_basis=_parse_float(_row_value(row, column_map, "cost_basis")),
                market_value=_parse_float(_row_value(row, column_map, "market_value")),
                weight=_parse_weight(_row_value(row, column_map, "weight")),
                sector=_parse_text(_row_value(row, column_map, "sector")),
                account=_parse_text(_row_value(row, column_map, "account")),
                notes=_parse_text(_row_value(row, column_map, "notes")),
            )
        )
    return PortfolioInputResult(holdings, errors)


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
```

- [ ] **Step 5: Run focused parser tests**

Run:

```bash
python -m pytest tests/test_portfolio.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run regression tests for the first ticket**

Run:

```bash
python -m pytest tests/test_portfolio.py tests/test_scoring.py -q
python -m pytest -q
python -m compileall app.py src
git diff --check
```

Expected: all commands exit 0.

---

## Next Plan Candidates After This QA Gate

- B-130.2: Read-only holding analysis that joins holdings to the existing `scored` DataFrame, reports unknown tickers, infers missing weights, and summarizes state/sector exposure.
- B-130.3: Streamlit analyzer section for single-ticker input and CSV/XLSX upload.
- B-130.4: README/backlog closeout after the UI path is verified.
