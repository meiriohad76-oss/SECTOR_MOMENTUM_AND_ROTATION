# ADV20 Flow River Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface 20-day average daily dollar volume (ADV20) on each Flow River node label, changing `CMF 0.12` to `CMF 0.12 · $1.2B`, and replace the placeholder caption sentence with real figures.

**Architecture:** Four layers in order — Python indicator function → snapshot serialisation → TypeScript type → React render. Each layer is null-safe: old snapshots without `adv_20d` display gracefully without the volume suffix.

**Tech Stack:** Python/pandas (`src/flow.py`), Python dict serialisation (`src/api_dashboard_snapshot.py`), TypeScript types (`web/lib/api.ts`), React/SVG (`web/app/chart-primitives.tsx`).

---

## File Map

| File | Change |
|---|---|
| `src/flow.py` | Add `adv_20d(df, lookback)` function; add `"adv_20d"` key to each row dict in `compute_flow_signals()` |
| `src/api_dashboard_snapshot.py` | Explicitly extract `adv_20d` from `row["payload"]` in `_row_payload()` |
| `web/lib/api.ts` | Add `adv_20d: number \| null` field to `SnapshotRow` |
| `web/app/chart-primitives.tsx` | Add `fmtDollarVolume()` helper; update outflow node text, inflow node text, and caption |
| `tests/test_flow.py` | Tests for `adv_20d()` function and `compute_flow_signals` column |
| `tests/test_api_dashboard_snapshot.py` | Test that `adv_20d` passes through `_row_payload()` |

---

## Task 1: `adv_20d()` indicator function

**Files:**
- Modify: `src/flow.py:593-599` (add after `relative_volume`)
- Test: `tests/test_flow.py`

- [ ] **Step 1: Write failing tests for `adv_20d`**

Open `tests/test_flow.py` and append these two tests at the bottom of the file:

```python
def test_adv_20d_returns_mean_dollar_volume_over_lookback(ohlcv_frame_factory):
    # 20 days, close=50, volume=200_000 → dv per day = 10_000_000 → mean = 10_000_000
    df = ohlcv_frame_factory(days=25, start_price=50.0, daily_return=0.0, volume=200_000)
    result = flow.adv_20d(df, lookback=20)
    assert result == pytest.approx(50.0 * 200_000, rel=1e-4)


def test_adv_20d_returns_none_when_fewer_than_lookback_rows(ohlcv_frame_factory):
    df = ohlcv_frame_factory(days=10)
    assert flow.adv_20d(df, lookback=20) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_flow.py::test_adv_20d_returns_mean_dollar_volume_over_lookback tests/test_flow.py::test_adv_20d_returns_none_when_fewer_than_lookback_rows -v
```

Expected: FAILED with `AttributeError: module 'src.flow' has no attribute 'adv_20d'`

- [ ] **Step 3: Implement `adv_20d` in `src/flow.py`**

Find `relative_volume` at line 593. Add the new function immediately after it (after line 599):

```python
def adv_20d(df: pd.DataFrame, lookback: int = 20) -> Optional[float]:
    """20-day average daily dollar volume (close × volume).

    Returns None when fewer than lookback rows are available.
    """
    if len(df) < lookback:
        return None
    dv = df["close"] * df["volume"]
    result = dv.iloc[-lookback:].mean()
    return float(result) if np.isfinite(result) else None
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_flow.py::test_adv_20d_returns_mean_dollar_volume_over_lookback tests/test_flow.py::test_adv_20d_returns_none_when_fewer_than_lookback_rows -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/flow.py tests/test_flow.py
git commit -m "feat: add adv_20d() indicator — 20-day avg daily dollar volume"
```

---

## Task 2: Wire `adv_20d` into `compute_flow_signals`

**Files:**
- Modify: `src/flow.py:1323-1341` (the `rows.append({...})` dict inside `compute_flow_signals`)
- Test: `tests/test_flow.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_flow.py`:

```python
def test_compute_flow_signals_includes_adv_20d_column(ohlcv_frame_factory):
    out = flow.compute_flow_signals({"XLK": ohlcv_frame_factory(days=80)})
    assert "adv_20d" in out.columns
    # close starts at 100, volume at 1_000_000 → adv_20d ≈ 100_000_000
    assert out.loc["XLK", "adv_20d"] == pytest.approx(100_000_000, rel=0.05)
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_flow.py::test_compute_flow_signals_includes_adv_20d_column -v
```

Expected: FAILED with `KeyError: 'adv_20d'`

- [ ] **Step 3: Add `adv_20d` to `compute_flow_signals` row dict**

In `src/flow.py`, find `compute_flow_signals` and the `rows.append({...})` block (around line 1323). Add one line after the `"rvol"` entry:

```python
rows.append({
    "ticker":          t,
    "cmf21":           chaikin_money_flow(df, 21),
    "obv_slope":       obv_slope(df, 20),
    "mfi14":           money_flow_index(df, 14),
    "rvol":            relative_volume(df, 20),
    "adv_20d":         adv_20d(df, 20),       # ← new
    "dist_days_25":    distribution_day_count(df, 25),
    "obv_divergence":  obv_price_divergence(df, 20),
    "etf_flow_5d_pct": etf_flow_5d_pct,
    "etf_flow_5d_pct_live": _provider_signal_live("etf_primary_flow", t),
    "block_up_ratio":  block_up_ratio,
    "block_up_ratio_live": _provider_signal_live("massive_block_trades", t),
    "dark_pool_pct":   dark_pool_share,
    "dark_pool_pct_live": _provider_signal_live("finra_ats_dark_pool", t),
    "si_delta_15d":    si_delta_15d,
    "si_delta_15d_live": _provider_signal_live("finra_short_interest", t),
    "thirteen_f_q":    thirteen_f_q,
    "thirteen_f_q_live": _provider_signal_live("sec_13f", t),
})
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_flow.py::test_compute_flow_signals_includes_adv_20d_column -v
```

Expected: PASSED

- [ ] **Step 5: Run the full flow test suite to confirm no regressions**

```
python -m pytest tests/test_flow.py -v
```

Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/flow.py tests/test_flow.py
git commit -m "feat: include adv_20d in compute_flow_signals output"
```

---

## Task 3: Expose `adv_20d` in dashboard snapshot payload

**Files:**
- Modify: `src/api_dashboard_snapshot.py:76-95` (`_row_payload` function)
- Test: `tests/test_api_dashboard_snapshot.py`

- [ ] **Step 1: Write failing test**

First, check the imports at the top of `tests/test_api_dashboard_snapshot.py`. It already imports `build_latest_dashboard_snapshot_payload`, `RunRecord`, `ScoredSnapshotRecord`, and `append_run`. Add `import pytest` if it isn't already there (it is not in the baseline file).

Add `import pytest` after the existing imports, then append these two tests at the bottom of the file:

```python
def test_row_payload_includes_adv_20d_from_payload_dict(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-adv",
            started_at_utc="2026-06-15T10:00:00Z",
            provider="massive",
            universe_count=1,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.0,
                f_score=0.3,
                pillar_scores={"cmf21": 0.12},
                payload={"adv_20d": 1_200_000_000.0},
            ),
        ],
        decisions=[],
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        saved_inputs_path=tmp_path / "missing.json",
        transition_journal_path=tmp_path / "missing.jsonl",
        generated_at="2026-06-15T12:00:00+00:00",
    )

    row = next(r for r in payload["rows"] if r["ticker"] == "XLK")
    assert row["adv_20d"] == pytest.approx(1_200_000_000.0)


def test_row_payload_adv_20d_is_none_when_absent_from_payload(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-noadv",
            started_at_utc="2026-06-15T10:00:00Z",
            provider="massive",
            universe_count=1,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLE",
                asset_class="US Sectors",
                state="WARNING",
                s_score=-0.5,
                f_score=-0.2,
                pillar_scores={"cmf21": -0.08},
                payload={},   # no adv_20d
            ),
        ],
        decisions=[],
    )

    payload = build_latest_dashboard_snapshot_payload(
        journal_path=journal_path,
        saved_inputs_path=tmp_path / "missing.json",
        transition_journal_path=tmp_path / "missing.jsonl",
        generated_at="2026-06-15T12:00:00+00:00",
    )

    row = next(r for r in payload["rows"] if r["ticker"] == "XLE")
    assert row["adv_20d"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_api_dashboard_snapshot.py::test_row_payload_includes_adv_20d_from_payload_dict tests/test_api_dashboard_snapshot.py::test_row_payload_adv_20d_is_none_when_absent_from_payload -v
```

Expected: FAILED with `KeyError: 'adv_20d'`

- [ ] **Step 3: Add `adv_20d` extraction to `_row_payload`**

In `src/api_dashboard_snapshot.py`, find `_row_payload` (line 76). Add one line inside the return dict, immediately after the `"cmf21"` line (line 92):

```python
def _row_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    ticker = _clean_text(row.get("ticker")).upper()
    state = _clean_text(row.get("state"), "UNKNOWN")
    identity = ticker_display_name(ticker)
    return {
        "ticker": ticker,
        "identity": identity,
        "display_label": f"{ticker} | {identity}" if identity != ticker else ticker,
        "asset_class": _clean_text(row.get("asset_class"), "Other"),
        "state": state,
        "s_score": _score_value(row, "s_score"),
        "f_score": _score_value(row, "f_score"),
        "quadrant": _quadrant(row),
        "momentum_pct": _float_or_none(_pillar_value(row, "mom_12_1")),
        "rs_ratio": _float_or_none(_pillar_value(row, "rs_ratio")),
        "rs_momentum": _float_or_none(_pillar_value(row, "rs_momentum")),
        "cmf21": _float_or_none(_pillar_value(row, "cmf21")),
        "adv_20d": _float_or_none(_payload_value(row, "adv_20d")),   # ← new
        "pillar_scores": dict(row.get("pillar_scores", {}) or {}),
        "payload": dict(row.get("payload", {}) or {}),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_api_dashboard_snapshot.py::test_row_payload_includes_adv_20d_from_payload_dict tests/test_api_dashboard_snapshot.py::test_row_payload_adv_20d_is_none_when_absent_from_payload -v
```

Expected: PASSED

- [ ] **Step 5: Run full snapshot test suite**

```
python -m pytest tests/test_api_dashboard_snapshot.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/api_dashboard_snapshot.py tests/test_api_dashboard_snapshot.py
git commit -m "feat: expose adv_20d in dashboard snapshot row payload"
```

---

## Task 4: Add `adv_20d` to `SnapshotRow` TypeScript type

**Files:**
- Modify: `web/lib/api.ts:54-69` (`SnapshotRow` type)

No TypeScript unit tests exist in this project. TypeScript compilation is the verification step.

- [ ] **Step 1: Add `adv_20d` to `SnapshotRow`**

In `web/lib/api.ts`, find `SnapshotRow` (line 54). Add `adv_20d` immediately after the `cmf21` field (line 66):

```typescript
export type SnapshotRow = {
  ticker: string;
  identity: string;
  display_label: string;
  asset_class: string;
  state: string;
  s_score: number;
  f_score: number;
  quadrant: string;
  momentum_pct: number | null;
  rs_ratio: number | null;
  rs_momentum: number | null;
  cmf21: number | null;
  adv_20d: number | null;           // ← new
  pillar_scores: Record<string, number | string | boolean | null>;
  payload: Record<string, number | string | boolean | null>;
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd web && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add web/lib/api.ts
git commit -m "feat: add adv_20d field to SnapshotRow type"
```

---

## Task 5: Render ADV20 in FlowRiver component

**Files:**
- Modify: `web/app/chart-primitives.tsx:644-787` (FlowRiver and surrounding helpers)

- [ ] **Step 1: Add `fmtDollarVolume` helper**

In `web/app/chart-primitives.tsx`, find `flowTooltip` (line 644). Add the new helper immediately before it (insert before line 644):

```typescript
function fmtDollarVolume(adv: number | null | undefined): string {
  if (adv === null || adv === undefined || !Number.isFinite(adv)) return "";
  if (adv >= 1e9) return `$${(adv / 1e9).toFixed(1)}B`;
  if (adv >= 1e6) return `$${Math.round(adv / 1e6)}M`;
  return `$${Math.round(adv / 1e3)}K`;
}
```

- [ ] **Step 2: Update outflow node text to include ADV20**

Find line 759 (the outflow `<text>` with class `flow-value`):

```tsx
<text x={leftX - 26} y={y + 13} textAnchor="end" className="flow-value">CMF {fmt(row.cmf21 ?? row.f_score, 2)}</text>
```

Replace with:

```tsx
<text x={leftX - 26} y={y + 13} textAnchor="end" className="flow-value">
  CMF {fmt(row.cmf21 ?? row.f_score, 2)}
  {row.adv_20d ? ` · ${fmtDollarVolume(row.adv_20d)}` : ""}
</text>
```

- [ ] **Step 3: Update inflow node text to include ADV20**

Find line 772 (the inflow `<text>` with class `flow-value`):

```tsx
<text x={rightX + 26} y={y + 13} className="flow-value">CMF +{fmt(row.cmf21 ?? row.f_score, 2)}</text>
```

Replace with:

```tsx
<text x={rightX + 26} y={y + 13} className="flow-value">
  CMF +{fmt(row.cmf21 ?? row.f_score, 2)}
  {row.adv_20d ? ` · ${fmtDollarVolume(row.adv_20d)}` : ""}
</text>
```

- [ ] **Step 4: Replace the caption placeholder sentence**

Find line 783 in the `<p className="flow-caption">` block:

```tsx
{" "}Dollar volume figures require additional backend work.
```

Replace with:

```tsx
{(outflows[0]?.adv_20d || inflows[0]?.adv_20d) ? (
  <>
    {" "}Avg daily vol (20d): <strong>{outflows[0].display_label}</strong>{" "}
    {fmtDollarVolume(outflows[0].adv_20d)}{" / "}
    <strong>{inflows[0].display_label}</strong>{" "}
    {fmtDollarVolume(inflows[0].adv_20d)}.
  </>
) : null}
```

- [ ] **Step 5: Verify TypeScript compiles**

```
cd web && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add web/app/chart-primitives.tsx
git commit -m "feat: render ADV20 on flow river nodes and caption"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run the full Python test suite**

```
python -m pytest tests/test_flow.py tests/test_api_dashboard_snapshot.py -v
```

Expected: All PASS

- [ ] **Step 2: Verify TypeScript compiles cleanly**

```
cd web && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Start the QA server and dev server, spot-check the flow river**

In one terminal:
```powershell
cd "c:\Users\meiri\momentum and flow"
python scripts/serve_next_qa_api.py --port 8765
```

In a second terminal:
```powershell
cd "c:\Users\meiri\momentum and flow\web"
npm run dev
```

Open http://localhost:3100 in a browser. Navigate to the Flow River chart. 

- The QA snapshot does **not** have `adv_20d` in its payload (null-safe path).
- Node labels should show `CMF 0.XX` (no dollar suffix — graceful degradation confirmed).
- Caption should show no volume sentence (graceful degradation confirmed).

- [ ] **Step 4: Create a final integration commit**

```bash
git commit --allow-empty -m "feat: ADV20 flow river — pipeline complete, null-safe rendering confirmed"
```
