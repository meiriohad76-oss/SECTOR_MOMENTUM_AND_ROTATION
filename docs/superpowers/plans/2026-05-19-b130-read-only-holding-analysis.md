# B-130.2 Read-Only Holding Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Join parsed single-ticker or portfolio holdings to the existing methodology `scored` DataFrame and return read-only analysis summaries.

**Architecture:** Extend `src/portfolio.py` with pure dataclasses and `analyze_holdings()`. The function accepts `HoldingInput` objects from B-130.1 and a caller-provided scored DataFrame. It must not import Streamlit, fetch data, import `src.scoring`, call `apply_state_machine()`, write `state.json`, or mutate the scored DataFrame.

**Tech Stack:** Python 3, pandas, pytest, existing `HoldingInput` parser objects.

---

## Files

- Modify: `src/portfolio.py`
- Modify: `tests/test_portfolio.py`

---

### Task 1: Read-Only Holding Analysis Core

**Files:**
- Modify: `src/portfolio.py`
- Modify: `tests/test_portfolio.py`

- [ ] **Step 1: Write failing holding-analysis tests**

Append these tests to `tests/test_portfolio.py`:

```python
def _scored_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "state": ["STAGE_2_BULLISH", "WARNING", "EXIT"],
            "class": ["US Sectors", "US Sectors", "US Industries"],
            "S_score": [1.25, -0.35, -2.0],
            "F_score": [0.80, -0.20, -1.10],
            "rank_in_class": [1, 5, 12],
            "selected": [True, False, False],
            "veto": [False, False, True],
        },
        index=["XLK", "XLF", "SOXX"],
    )


def test_analyze_holdings_joins_scored_rows_and_state_exposure():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", weight=0.60),
        portfolio.HoldingInput(ticker="XLF", weight=0.40),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert analysis.missing_tickers == []
    assert [row.ticker for row in analysis.rows] == ["XLK", "XLF"]
    assert analysis.rows[0].state == "STAGE_2_BULLISH"
    assert analysis.rows[0].asset_class == "US Sectors"
    assert analysis.rows[0].s_score == pytest.approx(1.25)
    assert analysis.rows[0].f_score == pytest.approx(0.80)
    assert analysis.rows[0].selected is True
    assert analysis.rows[0].veto is False
    assert analysis.state_exposure == pytest.approx(
        {"STAGE_2_BULLISH": 0.60, "WARNING": 0.40}
    )
    assert analysis.class_exposure == pytest.approx({"US Sectors": 1.0})
    assert analysis.action_tickers == {
        "exit": [],
        "warning": ["XLF"],
        "bullish": ["XLK"],
    }


def test_analyze_holdings_reports_unknown_tickers_and_keeps_missing_exposure():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", weight=0.25),
        portfolio.HoldingInput(ticker="ZZZZ", weight=0.75),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert analysis.missing_tickers == ["ZZZZ"]
    assert analysis.rows[1].missing is True
    assert analysis.rows[1].missing_reason == "ticker not found in scored universe"
    assert analysis.rows[1].state is None
    assert analysis.rows[1].analysis_weight == pytest.approx(0.75)
    assert analysis.state_exposure == pytest.approx(
        {"STAGE_2_BULLISH": 0.25, "MISSING": 0.75}
    )
    assert analysis.class_exposure == pytest.approx(
        {"US Sectors": 0.25, "MISSING": 0.75}
    )


def test_analyze_holdings_infers_weights_from_market_value_when_weights_missing():
    holdings = [
        portfolio.HoldingInput(ticker="XLK", market_value=2500.0),
        portfolio.HoldingInput(ticker="XLF", market_value=7500.0),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert [row.analysis_weight for row in analysis.rows] == pytest.approx([0.25, 0.75])
    assert analysis.state_exposure == pytest.approx(
        {"STAGE_2_BULLISH": 0.25, "WARNING": 0.75}
    )


def test_analyze_holdings_equal_weights_when_no_weight_or_market_value_exists():
    holdings = [
        portfolio.HoldingInput(ticker="XLK"),
        portfolio.HoldingInput(ticker="XLF"),
        portfolio.HoldingInput(ticker="SOXX"),
    ]

    analysis = portfolio.analyze_holdings(holdings, _scored_fixture())

    assert [row.analysis_weight for row in analysis.rows] == pytest.approx(
        [1 / 3, 1 / 3, 1 / 3]
    )
    assert analysis.action_tickers["exit"] == ["SOXX"]
    assert analysis.action_tickers["warning"] == ["XLF"]
    assert analysis.action_tickers["bullish"] == ["XLK"]
```

- [ ] **Step 2: Run analysis tests and verify they fail**

Run:

```bash
python -m pytest tests/test_portfolio.py -q
```

Expected: fail because `analyze_holdings()` does not exist yet.

- [ ] **Step 3: Implement analysis dataclasses and helpers**

Add these dataclasses below `PortfolioInputResult` in `src/portfolio.py`:

```python
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
```

Add this implementation near the parser public functions:

```python
def analyze_holdings(holdings: list[HoldingInput], scored_df: pd.DataFrame) -> PortfolioAnalysis:
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
```

Add private helpers:

```python
def _analysis_weights(holdings: list[HoldingInput]) -> list[float]:
    if not holdings:
        return []

    explicit = [holding.weight for holding in holdings]
    if all(weight is not None and weight > 0 for weight in explicit):
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
    text = _parse_text(value)
    return text


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
    return bool(value)


def _add_exposure(exposures: dict[str, float], key: str, weight: float) -> None:
    exposures[key] = exposures.get(key, 0.0) + float(weight)


def _add_action_ticker(action_tickers: dict[str, list[str]], ticker: str, state: str | None) -> None:
    if state in {"EXIT", "BEARISH_STAGE_4"}:
        action_tickers["exit"].append(ticker)
    elif state == "WARNING":
        action_tickers["warning"].append(ticker)
    elif state == "STAGE_2_BULLISH":
        action_tickers["bullish"].append(ticker)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_portfolio.py -q
```

Expected: all portfolio tests pass.

- [ ] **Step 5: Run the B-130.2 QA gate**

Run:

```bash
python -m pytest tests/test_portfolio.py tests/test_scoring.py -q
python -m pytest -q
python -m compileall app.py src
git diff --check
```

Expected: all commands exit 0. `git diff --check` may print CRLF warnings only.

- [ ] **Step 6: Review before moving on**

Request a code/spec review focused on:

- No scoring recomputation or `apply_state_machine()` call.
- Missing tickers are represented instead of crashing.
- Weight inference behavior is deterministic.
- Exposure summaries include missing holdings.
- The scored DataFrame is read-only.
