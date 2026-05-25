# B-142 Pytest Safety Net Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic pytest coverage for the dashboard's pure data, indicator, flow, and scoring modules before provider integration work begins.

**Architecture:** Keep Streamlit out of the first test harness because `app.py` performs live data loading and state writes at import time. Tests should exercise pure helpers in `src/` with deterministic OHLCV fixtures, mocked network boundaries, and a patched state file.

**Tech Stack:** Python 3, pytest, pandas, numpy, existing `src/` modules.

---

## Files

- Modify: `requirements.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_data.py`
- Create: `tests/test_indicators.py`
- Create: `tests/test_flow.py`
- Create: `tests/test_scoring.py`
- Modify: `docs/BACKLOG.md` after tests pass, marking `B-142` as started/completed.

---

### Task 1: Add Pytest Dependency And Deterministic Fixtures

**Files:**
- Modify: `requirements.txt`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add pytest dependency**

Append this line to `requirements.txt`:

```text
pytest>=8.3
```

- [ ] **Step 2: Create deterministic OHLCV fixtures**

Create `tests/conftest.py`:

```python
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv_frame_factory():
    def _make(
        days: int = 900,
        start: str = "2020-01-01",
        start_price: float = 100.0,
        daily_return: float = 0.001,
        volume: int = 1_000_000,
    ) -> pd.DataFrame:
        dates = pd.bdate_range(start=start, periods=days)
        steps = np.arange(days, dtype=float)
        close = pd.Series(start_price * np.power(1.0 + daily_return, steps), index=dates)
        open_ = close.shift(1).fillna(close.iloc[0] * 0.999)
        high = pd.concat([open_, close], axis=1).max(axis=1) * 1.01
        low = pd.concat([open_, close], axis=1).min(axis=1) * 0.99
        vol = pd.Series(volume + (steps.astype(int) % 20) * 1_000, index=dates)
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "adj_close": close * 0.995,
                "volume": vol,
            },
            index=dates,
        )

    return _make


@pytest.fixture
def market_ohlcv(ohlcv_frame_factory):
    return {
        "XLK": ohlcv_frame_factory(start_price=100, daily_return=0.0014),
        "XLF": ohlcv_frame_factory(start_price=80, daily_return=0.0007),
        "SOXX": ohlcv_frame_factory(start_price=120, daily_return=0.0018),
        "SPY": ohlcv_frame_factory(start_price=100, daily_return=0.0010),
        "BIL": ohlcv_frame_factory(start_price=90, daily_return=0.0001),
        "^TNX": ohlcv_frame_factory(start_price=40, daily_return=0.0002),
    }
```

- [ ] **Step 3: Install dependencies**

Run:

```powershell
python -m pip install -r requirements.txt
```

Expected: command exits with code 0 and pytest is importable.

- [ ] **Step 4: Verify pytest bootstrap**

Run:

```powershell
python -m pytest --version
```

Expected: command exits with code 0 and prints a pytest version.

- [ ] **Step 5: Commit task**

```powershell
git add requirements.txt tests/conftest.py
git commit -m "test: add pytest fixtures"
```

---

### Task 2: Add Data Module Tests

**Files:**
- Create: `tests/test_data.py`

- [ ] **Step 1: Write tests for resampling, close selection, and mocked download**

Create `tests/test_data.py`:

```python
from __future__ import annotations

import pandas as pd

from src import data


def test_to_weekly_aggregates_ohlcv_to_friday_close():
    dates = pd.bdate_range("2024-01-01", periods=10)
    df = pd.DataFrame(
        {
            "open": range(10, 20),
            "high": range(20, 30),
            "low": range(0, 10),
            "close": range(30, 40),
            "adj_close": range(40, 50),
            "volume": [100] * 10,
        },
        index=dates,
    )

    weekly = data.to_weekly(df)

    assert list(weekly["open"]) == [10, 15]
    assert list(weekly["high"]) == [24, 29]
    assert list(weekly["low"]) == [0, 5]
    assert list(weekly["close"]) == [34, 39]
    assert list(weekly["adj_close"]) == [44, 49]
    assert list(weekly["volume"]) == [500, 500]
    assert all(idx.weekday() == 4 for idx in weekly.index)


def test_to_monthly_aggregates_to_month_end():
    dates = pd.bdate_range("2024-01-29", periods=8)
    df = pd.DataFrame(
        {
            "open": range(8),
            "high": range(10, 18),
            "low": range(8),
            "close": range(20, 28),
            "adj_close": range(30, 38),
            "volume": [10] * 8,
        },
        index=dates,
    )

    monthly = data.to_monthly(df)

    assert list(monthly["open"]) == [0, 3]
    assert list(monthly["close"]) == [22, 27]
    assert list(monthly["adj_close"]) == [32, 37]
    assert list(monthly["volume"]) == [30, 50]


def test_close_price_prefers_adjusted_close_and_falls_back_to_close():
    idx = pd.date_range("2024-01-01", periods=2)
    with_adj = pd.DataFrame({"close": [10, 11], "adj_close": [9, 10]}, index=idx)
    without_adj = pd.DataFrame({"close": [10, 11]}, index=idx)

    assert list(data.close_price(with_adj)) == [9, 10]
    assert list(data.close_price(without_adj)) == [10, 11]


def test_fetch_ohlcv_flattens_mocked_yfinance_response(monkeypatch):
    dates = pd.bdate_range("2024-01-01", periods=40)
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["XLK"]]
    )
    raw = pd.DataFrame(1.0, index=dates, columns=columns)
    raw[("Volume", "XLK")] = 1_000_000
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return raw

    monkeypatch.setattr(data.yf, "download", fake_download)

    out = data.fetch_ohlcv(["XLK", "XLK"], period="1y")

    assert list(out.keys()) == ["XLK"]
    assert list(out["XLK"].columns) == ["open", "high", "low", "close", "volume", "adj_close"]
    assert len(out["XLK"]) == 40
    assert calls[0]["tickers"] == ["XLK"]
    assert calls[0]["period"] == "1y"
```

- [ ] **Step 2: Run targeted data tests**

Run:

```powershell
python -m pytest tests/test_data.py -q
```

Expected: all tests pass. If any test fails, fix only `src/data.py` or the test if the expectation is incorrect, then rerun this command.

- [ ] **Step 3: Commit task**

```powershell
git add tests/test_data.py src/data.py
git commit -m "test: cover data ingestion helpers"
```

---

### Task 3: Add Indicator Module Tests

**Files:**
- Create: `tests/test_indicators.py`

- [ ] **Step 1: Write tests for short-history guards and full-indicator shape**

Create `tests/test_indicators.py`:

```python
from __future__ import annotations

import pytest

from src import indicators


def test_indicator_helpers_return_none_for_short_history(ohlcv_frame_factory):
    short = ohlcv_frame_factory(days=40)

    assert indicators.momentum_12_1(short) is None
    assert indicators.faber_signal(short) is None
    assert indicators.stage_analysis(short, short) is None
    assert indicators.antonacci_absolute(short, short) is None
    assert indicators.rrg(short, short) is None
    assert indicators.breadth_proxy(short) is None


def test_compute_all_indicators_requires_benchmark_and_tbill(market_ohlcv):
    missing_bil = dict(market_ohlcv)
    missing_bil.pop("BIL")

    with pytest.raises(ValueError, match="Benchmark SPY or T-bill BIL missing"):
        indicators.compute_all_indicators(missing_bil)


def test_compute_all_indicators_excludes_tbill_and_index_tickers(market_ohlcv):
    out = indicators.compute_all_indicators(market_ohlcv)

    assert "BIL" not in out.index
    assert "^TNX" not in out.index
    assert {"XLK", "XLF", "SOXX", "SPY"}.issubset(set(out.index))
    assert {
        "mom_12_1",
        "faber",
        "stage",
        "above_30wma",
        "ma_slope_pos",
        "mansfield_rs",
        "antonacci",
        "rs_ratio",
        "rs_momentum",
        "rrg_quadrant",
        "breadth_50d",
    }.issubset(set(out.columns))
```

- [ ] **Step 2: Run targeted indicator tests**

Run:

```powershell
python -m pytest tests/test_indicators.py -q
```

Expected: all tests pass. If any test fails, fix only `src/indicators.py` or the test if the expectation is incorrect, then rerun this command.

- [ ] **Step 3: Commit task**

```powershell
git add tests/test_indicators.py src/indicators.py
git commit -m "test: cover indicator helpers"
```

---

### Task 4: Add Flow Module Tests

**Files:**
- Create: `tests/test_flow.py`

- [ ] **Step 1: Write tests for flow metrics, stub fields, and composite stability**

Create `tests/test_flow.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from src import flow


def test_chaikin_money_flow_is_positive_when_closes_near_high():
    idx = pd.bdate_range("2024-01-01", periods=30)
    df = pd.DataFrame(
        {
            "high": [10.0] * 30,
            "low": [0.0] * 30,
            "close": [9.0] * 30,
            "volume": [1000] * 30,
        },
        index=idx,
    )

    assert flow.chaikin_money_flow(df, period=21) == pytest.approx(0.8)


def test_relative_volume_compares_last_volume_to_previous_average():
    idx = pd.bdate_range("2024-01-01", periods=21)
    df = pd.DataFrame(
        {
            "high": [10.0] * 21,
            "low": [9.0] * 21,
            "close": [9.5] * 21,
            "volume": [100.0] * 20 + [250.0],
        },
        index=idx,
    )

    assert flow.relative_volume(df, lookback=20) == pytest.approx(2.5)


def test_compute_flow_signals_excludes_index_tickers_and_uses_stub_values(ohlcv_frame_factory):
    out = flow.compute_flow_signals(
        {
            "XLK": ohlcv_frame_factory(days=80),
            "^TNX": ohlcv_frame_factory(days=80),
        }
    )

    assert list(out.index) == ["XLK"]
    assert out.loc["XLK", "etf_flow_5d_pct"] == 0.0
    assert out.loc["XLK", "block_up_ratio"] == 1.0
    assert out.loc["XLK", "dark_pool_pct"] == 0.40
    assert out.loc["XLK", "si_delta_15d"] == 0.0
    assert out.loc["XLK", "thirteen_f_q"] == 0.0


def test_flow_composite_z_handles_constant_inputs_without_nan():
    flow_df = pd.DataFrame(
        {
            "cmf21": [0.1, 0.1],
            "obv_slope": [0.0, 0.0],
            "etf_flow_5d_pct": [0.0, 0.0],
            "block_up_ratio": [1.0, 1.0],
            "rvol": [1.0, 1.0],
            "si_delta_15d": [0.0, 0.0],
        },
        index=["XLK", "XLF"],
    )

    out = flow.flow_composite_z(flow_df)

    assert out.name == "F"
    assert list(out.index) == ["XLK", "XLF"]
    assert not out.isna().any()
    assert out.tolist() == [0.0, 0.0]
```

- [ ] **Step 2: Run targeted flow tests**

Run:

```powershell
python -m pytest tests/test_flow.py -q
```

Expected: all tests pass. If any test fails, fix only `src/flow.py` or the test if the expectation is incorrect, then rerun this command.

- [ ] **Step 3: Commit task**

```powershell
git add tests/test_flow.py src/flow.py
git commit -m "test: cover flow signals"
```

---

### Task 5: Add Scoring Module Tests

**Files:**
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Write tests for state gates, composite veto, and transition persistence**

Create `tests/test_scoring.py`:

```python
from __future__ import annotations

import json

import pandas as pd
import pytest

from src import scoring


def _row(**overrides) -> pd.Series:
    base = {
        "stage": 2,
        "above_30wma": True,
        "ma_slope_pos": True,
        "mansfield_rs": 5.0,
        "antonacci": 1,
        "rrg_quadrant": "Leading",
        "breadth_50d": 0.70,
        "cmf21": 0.08,
        "rvol": 1.0,
        "etf_flow_5d_pct": 0.0,
        "block_up_ratio": 1.0,
        "obv_divergence": False,
        "dist_days_25": 0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_decide_state_prioritizes_bearish_stage_four_before_exit():
    row = _row(
        above_30wma=False,
        ma_slope_pos=False,
        mansfield_rs=-2.0,
        cmf21=-0.20,
    )

    assert scoring.decide_state(row) == "BEARISH_STAGE_4"


def test_decide_state_returns_warning_for_weakening_quadrant():
    row = _row(rrg_quadrant="Weakening", cmf21=0.02)

    assert scoring.decide_state(row) == "WARNING"


def test_decide_state_returns_strict_stage_two_bullish():
    assert scoring.decide_state(_row()) == "STAGE_2_BULLISH"


def test_compute_composite_applies_flow_veto_and_ranks_within_class():
    indicators_df = pd.DataFrame(
        {
            "mom_12_1": [0.30, 0.05],
            "faber": [1, 1],
            "stage": [2, 2],
            "mansfield_rs": [12.0, -2.0],
            "antonacci": [1, 1],
            "rs_ratio": [110.0, 95.0],
            "rs_momentum": [108.0, 96.0],
        },
        index=["XLK", "XLF"],
    )
    flow_df = pd.DataFrame({"cmf21": [0.2, -0.2]}, index=["XLK", "XLF"])
    flow_z = pd.Series([2.0, -2.0], index=["XLK", "XLF"], name="F")

    out = scoring.compute_composite(indicators_df, flow_df, flow_z, phase="MID")

    assert out.loc["XLF", "veto"] == True
    assert out.loc["XLF", "S_score_after_veto"] == pytest.approx(-9.99)
    assert out.loc["XLK", "rank_in_class"] < out.loc["XLF", "rank_in_class"]


def test_apply_state_machine_persists_transitions_to_patched_state_file(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "updated": "2026-05-18T00:00:00",
                "by_ticker": {"XLK": {"state": "HOLD", "date": "2026-05-18"}},
                "transitions": [],
            }
        )
    )
    monkeypatch.setattr(scoring, "STATE_FILE", state_file)
    df = pd.DataFrame([_row(rrg_quadrant="Weakening", cmf21=0.02)], index=["XLK"])

    out = scoring.apply_state_machine(df)
    saved = json.loads(state_file.read_text())

    assert out.loc["XLK", "state"] == "WARNING"
    assert out.loc["XLK", "prior_state"] == "HOLD"
    assert saved["by_ticker"]["XLK"]["state"] == "WARNING"
    assert saved["transitions"][-1]["ticker"] == "XLK"
    assert saved["transitions"][-1]["from"] == "HOLD"
    assert saved["transitions"][-1]["to"] == "WARNING"
```

- [ ] **Step 2: Run targeted scoring tests**

Run:

```powershell
python -m pytest tests/test_scoring.py -q
```

Expected: all tests pass. If any test fails, fix only `src/scoring.py` or the test if the expectation is incorrect, then rerun this command.

- [ ] **Step 3: Commit task**

```powershell
git add tests/test_scoring.py src/scoring.py
git commit -m "test: cover scoring state machine"
```

---

### Task 6: Full QA And Backlog Update

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Run full pytest suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m compileall app.py src
```

Expected: command exits with code 0.

- [ ] **Step 3: Mark B-142 in backlog**

Add this entry under Engineering and ops in `docs/BACKLOG.md`, replacing the existing one-line idea if present:

```markdown
- **B-142** Unit tests for indicators/data/flow/scoring - DONE in `backlog-stepwise-qa`; pytest harness covers pure modules before provider integration.
```

- [ ] **Step 4: Review diff**

Run:

```powershell
git diff --stat HEAD
git diff -- tests src requirements.txt docs/BACKLOG.md
```

Expected: diff only contains the B-142 test harness, minimal source fixes if tests exposed issues, and backlog status update.

- [ ] **Step 5: Commit task**

```powershell
git add docs/BACKLOG.md
git commit -m "docs: mark B-142 safety net complete"
```

- [ ] **Step 6: Final verification before moving to B-010**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src
git status --short --branch
```

Expected: all tests pass, compile check exits 0, and branch is clean except for intentional commits.
