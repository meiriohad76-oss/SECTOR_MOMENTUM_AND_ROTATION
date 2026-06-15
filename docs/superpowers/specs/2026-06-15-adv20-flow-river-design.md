# ADV20 on Flow River — Design Spec

**Date:** 2026-06-15  
**Status:** Approved  
**Scope:** Backend pipeline + frontend display only. No scoring model changes.

---

## Goal

Surface 20-day average daily dollar volume (ADV20 = mean of `close × volume` over 20 trading days) for each sector in the Flow River chart. Each node label changes from `CMF 0.12` to `CMF 0.12 · $1.2B`, and the caption placeholder is replaced with actual volume figures.

---

## Architecture

Four layers in sequence. No changes to `src/run_journal.py`, `src/scoring.py`, or the QA API server.

```
OHLCV DataFrame (close, volume)
    ↓  src/flow.py: adv_20d(df, lookback=20)
    ↓  compute_flow_signals() → adds "adv_20d" column
    ↓  src/scoring.py: compute_composite() joins flow_df (unchanged)
    ↓  src/run_journal.py: scored_snapshot_records_from_frame()
       → adv_20d NOT in PILLAR_SCORE_COLUMNS → flows to payload dict automatically
    ↓  src/api_dashboard_snapshot.py: _row_payload()
       → explicit extraction: "adv_20d": _float_or_none(_payload_value(row, "adv_20d"))
    ↓  web/lib/api.ts: SnapshotRow.adv_20d: number | null
    ↓  web/app/chart-primitives.tsx: FlowRiver renders CMF · ADV
```

---

## Layer 1: `src/flow.py`

### New function: `adv_20d`

Add alongside `relative_volume()`:

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

### Modify `compute_flow_signals`

Add `adv_20d` to each row dict:

```python
rows.append({
    "ticker":          t,
    "cmf21":           chaikin_money_flow(df, 21),
    "obv_slope":       obv_slope(df, 20),
    "mfi14":           money_flow_index(df, 14),
    "rvol":            relative_volume(df, 20),
    "adv_20d":         adv_20d(df, 20),       # ← new
    "dist_days_25":    distribution_day_count(df, 25),
    ...
})
```

`adv_20d` is intentionally excluded from `PILLAR_SCORE_COLUMNS` in `run_journal.py` — it is a display descriptor, not a scoring signal. It therefore routes to `payload` automatically in `scored_snapshot_records_from_frame()`.

---

## Layer 2: `src/api_dashboard_snapshot.py`

### Modify `_row_payload`

Add one line inside the return dict:

```python
"adv_20d": _float_or_none(_payload_value(row, "adv_20d")),
```

Placed after `"cmf21"` for readability. Uses the existing `_payload_value()` helper which reads from `row["payload"]`.

---

## Layer 3: `web/lib/api.ts`

### Modify `SnapshotRow`

Add after `cmf21`:

```typescript
adv_20d: number | null;
```

Matches the existing `cmf21: number | null` pattern.

---

## Layer 4: `web/app/chart-primitives.tsx`

### New helper: `fmtDollarVolume`

```typescript
function fmtDollarVolume(adv: number | null | undefined): string {
  if (adv === null || adv === undefined || !Number.isFinite(adv)) return "";
  if (adv >= 1e9) return `$${(adv / 1e9).toFixed(1)}B`;
  if (adv >= 1e6) return `$${Math.round(adv / 1e6)}M`;
  return `$${Math.round(adv / 1e3)}K`;
}
```

### Modify outflow node text

```tsx
<text x={leftX - 26} y={y + 13} textAnchor="end" className="flow-value">
  CMF {fmt(row.cmf21 ?? row.f_score, 2)}
  {row.adv_20d ? ` · ${fmtDollarVolume(row.adv_20d)}` : ""}
</text>
```

### Modify inflow node text

```tsx
<text x={rightX + 26} y={y + 13} className="flow-value">
  CMF +{fmt(row.cmf21 ?? row.f_score, 2)}
  {row.adv_20d ? ` · ${fmtDollarVolume(row.adv_20d)}` : ""}
</text>
```

### Update caption

Replace `{" "}Dollar volume figures require additional backend work.` with:

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

---

## Null-safety contract

| Condition | Behavior |
|---|---|
| Fresh snapshot with ADV20 | `CMF 0.12 · $1.2B` on node; caption shows avg daily vol |
| Old snapshot (no ADV20 in payload) | `CMF 0.12` on node; caption omits volume sentence |
| ADV20 computed but NaN/Inf | `adv_20d` returned as `None` from Python, `null` in JSON; same as above |
| Fewer than 20 OHLCV rows | `adv_20d()` returns `None`; same as above |

---

## Out of scope

- Real-time sparklines (separate deferred item)
- Any change to scoring weights or pillar definitions
- QA server snapshot update (null-safe UI means no urgency)
- Strand width using dollar volume (current width encodes CMF magnitude — keep as-is)

---

## Files changed

| File | Change |
|---|---|
| `src/flow.py` | Add `adv_20d()`, add column in `compute_flow_signals()` |
| `src/api_dashboard_snapshot.py` | Add `adv_20d` field in `_row_payload()` |
| `web/lib/api.ts` | Add `adv_20d: number | null` to `SnapshotRow` |
| `web/app/chart-primitives.tsx` | Add `fmtDollarVolume()`, update node text + caption |
