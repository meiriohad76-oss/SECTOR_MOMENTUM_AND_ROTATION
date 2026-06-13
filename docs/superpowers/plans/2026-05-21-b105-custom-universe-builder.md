# B-105 Custom Universe Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Streamlit custom universe builder that lets a user paste tickers or upload a ticker file, then ranks those tickers against the current methodology snapshot.

**Architecture:** Keep the global configured universe unchanged. Add a pure `src/custom_universe.py` helper for input parsing, validation, de-duplication, scored-snapshot joining, summary buckets, and display frames. Wire `app.py` to render the helper output without fetching new data, mutating `scored`, writing `state.json`, or persisting watchlists.

**Tech Stack:** Python 3, pandas, Streamlit, pytest, existing portfolio parser helpers, existing drill-link controls.

---

### Task 1: Pure Parser And Analyzer

**Files:**
- Create: `src/custom_universe.py`
- Create: `tests/test_custom_universe.py`

- [ ] **Step 1: Write failing parser and analyzer tests**

Add tests that require:

```python
from src import custom_universe


def test_parse_custom_universe_text_normalizes_deduplicates_and_reports_invalid_tokens():
    result = custom_universe.parse_custom_universe_text("xlk, xlf\nXLK;BRK/B")

    assert result.tickers == ["XLK", "XLF"]
    assert result.duplicate_tickers == ["XLK"]
    assert len(result.errors) == 1
    assert result.errors[0].message == "ticker has invalid characters"
    assert result.errors[0].token == "BRK/B"
```

```python
def test_analyze_custom_universe_ranks_available_tickers_and_keeps_missing_rows():
    scored = _scored_fixture()

    analysis = custom_universe.analyze_custom_universe(["XLF", "ZZZZ", "XLK"], scored)

    assert analysis.available_tickers == ["XLK", "XLF"]
    assert analysis.missing_tickers == ["ZZZZ"]
    assert [row.ticker for row in analysis.rows] == ["XLK", "XLF", "ZZZZ"]
    assert [row.custom_rank for row in analysis.rows] == [1, 2, None]
    assert analysis.class_counts == {"US Sectors": 2, "MISSING": 1}
    assert analysis.state_counts == {"STAGE_2_BULLISH": 1, "WARNING": 1, "MISSING": 1}
```

```python
def test_custom_universe_rows_frame_formats_rank_scores_and_missing_values():
    analysis = custom_universe.analyze_custom_universe(["XLF", "ZZZZ", "XLK"], _scored_fixture())

    frame = custom_universe.custom_universe_rows_frame(analysis)

    assert frame.to_dict("records") == [
        {
            "Custom Rank": "1",
            "Ticker": "XLK",
            "Class": "US Sectors",
            "State": "STAGE 2 BULLISH",
            "S": "1.25",
            "F": "0.80",
            "Class Rank": "1",
            "Selected": "YES",
            "Veto": "NO",
        },
        {
            "Custom Rank": "2",
            "Ticker": "XLF",
            "Class": "US Sectors",
            "State": "WARNING",
            "S": "-0.35",
            "F": "-0.20",
            "Class Rank": "5",
            "Selected": "NO",
            "Veto": "NO",
        },
        {
            "Custom Rank": "-",
            "Ticker": "ZZZZ",
            "Class": "MISSING",
            "State": "MISSING",
            "S": "-",
            "F": "-",
            "Class Rank": "-",
            "Selected": "-",
            "Veto": "-",
        },
    ]
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_custom_universe.py -q`

Expected: FAIL because `src.custom_universe` does not exist yet.

- [ ] **Step 3: Implement minimal pure helper**

Create `src/custom_universe.py` with frozen dataclasses:

```python
CustomUniverseInputError(message, token=None, row_number=None, column=None)
CustomUniverseInputResult(tickers, errors, duplicate_tickers)
CustomUniverseAnalysisRow(...)
CustomUniverseAnalysis(rows, available_tickers, missing_tickers, class_counts, state_counts, action_tickers)
```

Implement:

```python
parse_custom_universe_text(value: str) -> CustomUniverseInputResult
parse_custom_universe_file(payload: str | bytes, filename: str) -> CustomUniverseInputResult
analyze_custom_universe(tickers: list[str], scored_df: pd.DataFrame) -> CustomUniverseAnalysis
custom_universe_rows_frame(analysis: CustomUniverseAnalysis) -> pd.DataFrame
summary_counts_frame(counts: dict[str, int], label: str) -> pd.DataFrame
```

Use `src.portfolio.normalize_ticker`, `parse_holdings_csv`, and `parse_holdings_excel` so file ticker aliases stay consistent with B-130. Sort matched rows by `S_score` descending, assign `custom_rank`, append missing rows, and never mutate `scored_df`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_custom_universe.py -q`

Expected: PASS.

### Task 2: Streamlit Section

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Create or modify: `tests/test_custom_universe_app_static.py`

- [ ] **Step 1: Write failing static app tests**

Add tests that require:

```python
def test_app_wires_custom_universe_builder_without_new_fetch_path():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.custom_universe import" in app_source
    assert "def render_custom_universe_builder():" in app_source
    assert "parse_custom_universe_text(" in app_source
    assert "parse_custom_universe_file(" in app_source
    assert "analyze_custom_universe(result.tickers, scored)" in app_source
    assert "custom_universe_rows_frame(analysis)" in app_source
    assert "fetch_ohlcv(result.tickers" not in app_source
```

```python
def test_custom_universe_renders_between_portfolio_and_backtest_labs():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        "render_portfolio_analyzer()\nrender_custom_universe_builder()\n"
        "render_backtest_lab()"
        in app_source
    )
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_custom_universe_app_static.py -q`

Expected: FAIL because the Streamlit section is not wired yet.

- [ ] **Step 3: Implement minimal UI**

In `app.py`, import helper functions from `src.custom_universe`, add:

```python
def _render_custom_universe_analysis(result):
    ...

def render_custom_universe_builder():
    ...
```

The section should render after the portfolio analyzer and before the backtest lab. It should offer a radio with `Paste tickers` and `Upload file`, a text area or file uploader, duplicate/missing warnings, two count dataframes, action buckets, a scored custom-universe table, and drill buttons for available tickers.

In `static/style.css`, reuse portfolio action styling and add a compact `.custom-universe-summary` grid.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_custom_universe.py tests/test_custom_universe_app_static.py -q
```

Expected: PASS.

### Task 3: Docs, Backlog, Full QA, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b105-custom-universe-builder.md`

- [ ] **Step 1: Update docs and backlog**

README must describe the read-only custom universe builder and its paste/upload modes. Backlog must move B-105 from Ideas into the completed section with status, files, behavior, safety, and evidence.

- [ ] **Step 2: Run full local QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: all pass with no whitespace errors.

- [ ] **Step 3: Review**

Dispatch a reviewer for B-105. Fix any Critical or Important issues, then rerun focused and full QA.

- [ ] **Step 4: Commit and push**

Run:

```powershell
git add app.py src/custom_universe.py static/style.css tests/test_custom_universe.py tests/test_custom_universe_app_static.py README.md docs/BACKLOG.md docs/superpowers/plans/2026-05-21-b105-custom-universe-builder.md
git commit -m "feat: add custom universe builder"
git push
```

- [ ] **Step 5: Deploy to Pi**

Run the standard Pi pull, focused B-105 tests, full pytest, service restart, and dashboard HTTP smoke at `http://127.0.0.1:8501/?ticker=XLK`.
