# Custom Universe Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /api/v1/universe/analyze` endpoint and a `CustomUniversePanel` collapsible component in the A1 overview screen where users paste a ticker list and get it ranked by S-score against the current snapshot.

**Architecture:** New `src/api_universe.py` builds a DataFrame from the snapshot rows (column-name mapping), calls the existing `src/custom_universe.analyze_custom_universe()`, and serializes the result. New route in `src/api_server.py` calls `snapshot_reader()` then `build_universe_analysis_payload()`. Frontend: client-side POST on submit — no server-side fetch needed (user-driven, not pre-loaded).

**Tech Stack:** Python/FastAPI (`src/`), pytest, TypeScript, React (`"use client"`), CSS.

---

## File Map

| File | Role |
|---|---|
| `src/api_universe.py` | `build_universe_analysis_payload()` — maps snapshot → scored_df → `CustomUniverseAnalysis` → dict |
| `tests/test_api_universe.py` | Unit tests for `build_universe_analysis_payload` |
| `src/api_server.py` | Add `POST /api/v1/universe/analyze` route |
| `web/components/CustomUniversePanel.tsx` | Client component: textarea + submit + results table |
| `web/app/globals.css` | `CustomUniversePanel` styles |
| `web/app/dashboard-screens-client.tsx` | Render `CustomUniversePanel` in A1 `OverviewScreen` |

---

## Task 1: `build_universe_analysis_payload` — failing tests

**Files:**
- Create: `tests/test_api_universe.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api_universe.py`:

```python
from __future__ import annotations

from src.api_universe import build_universe_analysis_payload


SNAPSHOT_ROWS = [
    {
        "ticker": "XLK",
        "s_score": 1.2,
        "f_score": 0.4,
        "state": "STAGE_2_BULLISH",
        "asset_class": "US Sectors",
        "quadrant": "Leading",
        "momentum_pct": 0.22,
        "cmf21": 0.12,
    },
    {
        "ticker": "XLE",
        "s_score": -0.5,
        "f_score": -0.3,
        "state": "WARNING",
        "asset_class": "US Sectors",
        "quadrant": "Weakening",
        "momentum_pct": -0.04,
        "cmf21": -0.10,
    },
]


def test_build_universe_analysis_returns_ranked_rows_for_known_tickers():
    result = build_universe_analysis_payload(["XLK", "XLE"], SNAPSHOT_ROWS)

    assert result["available_count"] == 2
    assert result["missing_count"] == 0
    rows = result["rows"]
    assert len(rows) == 2
    # XLK has higher s_score, should rank first (descending by default)
    assert rows[0]["ticker"] == "XLK"
    assert rows[0]["missing"] is False
    assert rows[0]["state"] == "STAGE_2_BULLISH"


def test_build_universe_analysis_flags_missing_tickers():
    result = build_universe_analysis_payload(["XLK", "FAKE"], SNAPSHOT_ROWS)

    assert result["available_count"] == 1
    assert result["missing_count"] == 1
    missing_row = next(r for r in result["rows"] if r["ticker"] == "FAKE")
    assert missing_row["missing"] is True


def test_build_universe_analysis_empty_tickers_returns_empty_rows():
    result = build_universe_analysis_payload([], SNAPSHOT_ROWS)

    assert result["available_count"] == 0
    assert result["missing_count"] == 0
    assert result["rows"] == []


def test_build_universe_analysis_empty_snapshot_marks_all_missing():
    result = build_universe_analysis_payload(["XLK", "XLE"], [])

    assert result["available_count"] == 0
    assert result["missing_count"] == 2
    for row in result["rows"]:
        assert row["missing"] is True


def test_build_universe_analysis_returns_class_and_state_counts():
    result = build_universe_analysis_payload(["XLK", "XLE"], SNAPSHOT_ROWS)

    assert "US Sectors" in result["class_counts"]
    assert result["class_counts"]["US Sectors"] == 2
    assert "STAGE_2_BULLISH" in result["state_counts"]
    assert "WARNING" in result["state_counts"]


def test_build_universe_analysis_returns_action_buckets():
    result = build_universe_analysis_payload(["XLK", "XLE"], SNAPSHOT_ROWS)

    assert "bullish" in result["action_tickers"]
    assert "warning" in result["action_tickers"]
    assert "exit" in result["action_tickers"]
    assert "XLK" in result["action_tickers"]["bullish"]
    assert "XLE" in result["action_tickers"]["warning"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -m pytest tests/test_api_universe.py -v
```

Expected: `ImportError: cannot import name 'build_universe_analysis_payload' from 'src.api_universe'`.

---

## Task 2: Implement `src/api_universe.py`

**Files:**
- Create: `src/api_universe.py`

- [ ] **Step 1: Create the module**

Create `src/api_universe.py`:

```python
"""Read-only custom universe analysis payload for the B-170 React migration."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from .custom_universe import (
    CustomUniverseAnalysisRow,
    analyze_custom_universe,
    parse_custom_universe_text,
)


def _serialize_row(row: CustomUniverseAnalysisRow) -> dict[str, Any]:
    return {
        "ticker":        row.ticker,
        "custom_rank":   row.custom_rank,
        "state":         row.state,
        "asset_class":   row.asset_class,
        "s_score":       row.s_score,
        "f_score":       row.f_score,
        "stage":         row.stage,
        "rrg_quadrant":  row.rrg_quadrant,
        "mom_12_1":      row.mom_12_1,
        "cmf21":         row.cmf21,
        "breadth_50d":   row.breadth_50d,
        "rank_in_class": row.rank_in_class,
        "selected":      row.selected,
        "veto":          row.veto,
        "missing":       row.missing,
        "missing_reason": row.missing_reason,
    }


def _snapshot_rows_to_df(snapshot_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert snapshot API rows to a DataFrame with column names expected by analyze_custom_universe."""
    if not snapshot_rows:
        return pd.DataFrame()

    df = pd.DataFrame(snapshot_rows)

    # Map API field names to the column names analyze_custom_universe expects
    rename = {
        "s_score":      "S_score",
        "f_score":      "F_score",
        "asset_class":  "class",
        "quadrant":     "rrg_quadrant",
        "momentum_pct": "mom_12_1",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "ticker" not in df.columns:
        return pd.DataFrame()

    df = df.drop_duplicates(subset=["ticker"])
    df = df.set_index("ticker")
    return df


def build_universe_analysis_payload(
    tickers: list[str],
    snapshot_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze a custom ticker list against the current snapshot rows."""
    if not tickers:
        return {
            "rows": [],
            "available_count": 0,
            "missing_count": 0,
            "class_counts": {},
            "state_counts": {},
            "action_tickers": {"exit": [], "warning": [], "bullish": []},
        }

    df = _snapshot_rows_to_df(snapshot_rows)

    if df.empty:
        # No snapshot data — all tickers are missing
        normalized = [t.strip().upper() for t in tickers if t]
        return {
            "rows": [
                {
                    "ticker": t,
                    "custom_rank": None,
                    "state": None,
                    "asset_class": None,
                    "s_score": None,
                    "f_score": None,
                    "stage": None,
                    "rrg_quadrant": None,
                    "mom_12_1": None,
                    "cmf21": None,
                    "breadth_50d": None,
                    "rank_in_class": None,
                    "selected": None,
                    "veto": None,
                    "missing": True,
                    "missing_reason": "no snapshot data",
                }
                for t in normalized
            ],
            "available_count": 0,
            "missing_count": len(normalized),
            "class_counts": {},
            "state_counts": {},
            "action_tickers": {"exit": [], "warning": [], "bullish": []},
        }

    analysis = analyze_custom_universe(tickers, df)

    return {
        "rows":           [_serialize_row(r) for r in analysis.rows],
        "available_count": len(analysis.available_tickers),
        "missing_count":   len(analysis.missing_tickers),
        "class_counts":    analysis.class_counts,
        "state_counts":    analysis.state_counts,
        "action_tickers":  analysis.action_tickers,
    }
```

- [ ] **Step 2: Run tests to verify they pass**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -m pytest tests/test_api_universe.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 3: Run full test suite to confirm no regressions**

```powershell
python -m pytest -q
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```powershell
git add src/api_universe.py tests/test_api_universe.py
git commit -m "feat: build_universe_analysis_payload — custom universe API module"
```

---

## Task 3: Add `POST /api/v1/universe/analyze` route to `api_server.py`

**Files:**
- Modify: `src/api_server.py`

- [ ] **Step 1: Add the import**

In `src/api_server.py`, find the existing import block. Add after the existing `from .api_*` imports:

```python
from .api_universe import build_universe_analysis_payload
```

- [ ] **Step 2: Add the route inside `create_app`**

Inside `create_app`, after the `@app.get("/api/v1/debrief")` route (added in the Debrief Lab plan), add:

```python
    @app.post("/api/v1/universe/analyze")
    def universe_analyze(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        body = payload or {}
        raw_tickers = body.get("tickers", [])
        tickers = [str(t).strip().upper() for t in raw_tickers if t]
        snapshot = snapshot_reader()
        return build_universe_analysis_payload(tickers, snapshot.get("rows", []))
```

- [ ] **Step 3: Verify the server imports cleanly**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -c "from src.api_server import create_app; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Run full test suite**

```powershell
python -m pytest -q
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/api_server.py
git commit -m "feat: POST /api/v1/universe/analyze route"
```

---

## Task 4: Create `CustomUniversePanel` component

**Files:**
- Create: `web/components/CustomUniversePanel.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create the component**

Create `web/components/CustomUniversePanel.tsx`:

```tsx
// web/components/CustomUniversePanel.tsx
"use client";
import { useState } from "react";
import { stateColor, stateShortLabel } from "../lib/state-colors";

type UniverseRow = {
  ticker: string;
  custom_rank: number | null;
  state: string | null;
  asset_class: string | null;
  s_score: number | null;
  f_score: number | null;
  mom_12_1: number | null;
  cmf21: number | null;
  missing: boolean;
  missing_reason: string | null;
};

type UniverseResult = {
  rows: UniverseRow[];
  available_count: number;
  missing_count: number;
  class_counts: Record<string, number>;
  state_counts: Record<string, number>;
  action_tickers: { exit: string[]; warning: string[]; bullish: string[] };
};

function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2);
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
}

export default function CustomUniversePanel() {
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<UniverseResult | null>(null);
  const [error, setError]       = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const tickers = input
      .split(/[\s,;]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (tickers.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/universe/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers }),
      });
      if (!res.ok) {
        setError(`Server error: HTTP ${res.status}`);
        return;
      }
      const data = (await res.json()) as UniverseResult;
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <details className="custom-universe-panel">
      <summary className="cup-summary">Custom Universe Analyzer</summary>

      <form className="cup-form" onSubmit={handleSubmit}>
        <label className="cup-label" htmlFor="cup-input">
          Paste tickers (comma, space, or newline separated):
        </label>
        <textarea
          id="cup-input"
          className="cup-textarea"
          rows={3}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="XLK, XLE, NVDA, AAPL..."
          disabled={loading}
        />
        <button className="cup-submit" type="submit" disabled={loading || !input.trim()}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && <p className="cup-error">{error}</p>}

      {result && (
        <div className="cup-results">
          <div className="cup-summary-row">
            <span>{result.available_count} matched</span>
            {result.missing_count > 0 && (
              <span className="cup-missing-badge">{result.missing_count} not found</span>
            )}
          </div>

          {result.action_tickers.bullish.length > 0 && (
            <div className="cup-bucket cup-bucket-bullish">
              <span className="cup-bucket-label">BULLISH</span>{" "}
              {result.action_tickers.bullish.join(", ")}
            </div>
          )}
          {result.action_tickers.warning.length > 0 && (
            <div className="cup-bucket cup-bucket-warning">
              <span className="cup-bucket-label">WARN</span>{" "}
              {result.action_tickers.warning.join(", ")}
            </div>
          )}
          {result.action_tickers.exit.length > 0 && (
            <div className="cup-bucket cup-bucket-exit">
              <span className="cup-bucket-label">EXIT</span>{" "}
              {result.action_tickers.exit.join(", ")}
            </div>
          )}

          <div className="cup-table-scroll">
            <table className="cup-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ticker</th>
                  <th>State</th>
                  <th>Class</th>
                  <th>S</th>
                  <th>F</th>
                  <th>MOM</th>
                  <th>CMF</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr key={row.ticker} className={row.missing ? "cup-row-missing" : ""}>
                    <td>{row.custom_rank ?? "—"}</td>
                    <td className="cup-ticker">{row.ticker}</td>
                    <td>
                      {row.state ? (
                        <span
                          className="state-pill mono"
                          style={{
                            background: stateColor(row.state),
                            color: "#fff",
                            padding: "1px 6px",
                            borderRadius: "8px",
                            fontSize: "0.67rem",
                            fontWeight: 600,
                          }}
                        >
                          {stateShortLabel(row.state)}
                        </span>
                      ) : (
                        <span className="cup-not-found">not found</span>
                      )}
                    </td>
                    <td>{row.asset_class ?? "—"}</td>
                    <td className={row.s_score !== null ? (row.s_score >= 0 ? "cup-pos" : "cup-neg") : ""}>
                      {fmtScore(row.s_score)}
                    </td>
                    <td className={row.f_score !== null ? (row.f_score >= 0 ? "cup-pos" : "cup-neg") : ""}>
                      {fmtScore(row.f_score)}
                    </td>
                    <td>{fmtPct(row.mom_12_1)}</td>
                    <td>{fmtScore(row.cmf21)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </details>
  );
}
```

- [ ] **Step 2: Add CSS styles**

Append to the end of `web/app/globals.css`:

```css
/* ── Custom Universe Panel ────────────────────────────── */
.custom-universe-panel {
  margin: 18px 0 0;
}
.cup-summary {
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.65;
  padding: 6px 0;
  user-select: none;
}
.cup-summary:hover { opacity: 1; }
.cup-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}
.cup-label {
  font-size: 0.75rem;
  opacity: 0.65;
}
.cup-textarea {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  color: inherit;
  font-family: var(--font-mono, monospace);
  font-size: 0.8rem;
  padding: 8px 10px;
  resize: vertical;
}
.cup-textarea:focus {
  outline: none;
  border-color: rgba(255,255,255,0.3);
}
.cup-submit {
  align-self: flex-start;
  background: rgba(92,157,203,0.2);
  border: 1px solid rgba(92,157,203,0.4);
  border-radius: 6px;
  color: #5c9dcb;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 5px 14px;
}
.cup-submit:hover:not(:disabled) {
  background: rgba(92,157,203,0.35);
}
.cup-submit:disabled { opacity: 0.4; cursor: not-allowed; }
.cup-error {
  color: #e07070;
  font-size: 0.78rem;
  margin: 8px 0;
}
.cup-results { margin-top: 12px; }
.cup-summary-row {
  font-size: 0.75rem;
  opacity: 0.7;
  margin-bottom: 8px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.cup-missing-badge {
  background: rgba(224,112,112,0.15);
  color: #e07070;
  border-radius: 8px;
  padding: 1px 7px;
  font-size: 0.7rem;
}
.cup-bucket {
  font-size: 0.75rem;
  padding: 4px 10px;
  border-radius: 6px;
  margin-bottom: 5px;
  font-family: var(--font-mono, monospace);
}
.cup-bucket-label {
  font-weight: 700;
  margin-right: 6px;
  font-size: 0.7rem;
}
.cup-bucket-bullish { background: rgba(76,175,135,0.12); }
.cup-bucket-warning { background: rgba(226,165,58,0.12); }
.cup-bucket-exit    { background: rgba(224,112,112,0.12); }
.cup-table-scroll { overflow-x: auto; margin-top: 10px; }
.cup-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.75rem;
  font-family: var(--font-mono, monospace);
}
.cup-table th {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.12);
  font-weight: 600;
  opacity: 0.65;
  white-space: nowrap;
}
.cup-table th:nth-child(n+5) { text-align: right; }
.cup-table td {
  padding: 4px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  white-space: nowrap;
}
.cup-table td:nth-child(n+5) { text-align: right; }
.cup-ticker { font-weight: 600; }
.cup-pos { color: #4caf87; }
.cup-neg { color: #e07070; }
.cup-row-missing { opacity: 0.45; }
.cup-not-found {
  font-size: 0.68rem;
  opacity: 0.5;
  font-style: italic;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors (the component uses the existing `/api/v1/universe/analyze` fetch target, which is a proxy — Next.js handles routing).

---

## Task 5: Add Next.js API proxy route for `POST /api/v1/universe/analyze`

The `CustomUniversePanel` fetches `/api/v1/universe/analyze` from the browser. The Next.js dev server needs a proxy route so browser requests reach the FastAPI backend.

**Files:**
- Check: `web/api/v1/` — look for existing proxy pattern

- [ ] **Step 1: Check the existing proxy pattern**

```powershell
ls "c:\Users\meiri\momentum and flow\web\api\v1\"
```

Look at how `web/api/v1/refresh/route.ts` proxies to FastAPI. Follow the same pattern.

- [ ] **Step 2: Create the proxy route**

Create `web/api/v1/universe/analyze/route.ts`:

```typescript
// web/api/v1/universe/analyze/route.ts
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body = await request.json();
    const res = await fetch(`${API_BASE}/api/v1/universe/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

---

## Task 6: Wire `CustomUniversePanel` into `OverviewScreen`

**Files:**
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Add the import**

At the top of `web/app/dashboard-screens-client.tsx`, add:

```tsx
import CustomUniversePanel from "../components/CustomUniversePanel";
```

- [ ] **Step 2: Add `CustomUniversePanel` to `OverviewScreen`**

Inside `function OverviewScreen` (the A-profile overview), find where `<DebriefLab>` was added (at the bottom of the `<section>`). Add `CustomUniversePanel` immediately before `DebriefLab`:

```tsx
      <CustomUniversePanel />
      <DebriefLab debrief={debriefData} />
    </section>
```

- [ ] **Step 3: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Smoke-check in browser**

With the dev server running at `http://localhost:3100/?presentation=a`:
- Open the page
- Scroll to find "Custom Universe Analyzer" `<details>` toggle
- Click to expand
- Paste `XLK, XLE` into the textarea
- Click "Analyze"
- Verify the results table appears with XLK ranked #1 (highest S-score) and XLE ranked #2. If the API is not running, the form shows `Server error: HTTP 502` — that is correct behaviour for the QA environment.

- [ ] **Step 5: Commit**

```powershell
cd "c:\Users\meiri\momentum and flow"
git add src/api_universe.py tests/test_api_universe.py src/api_server.py \
        web/components/CustomUniversePanel.tsx \
        web/api/v1/universe/analyze/route.ts \
        web/app/dashboard-screens-client.tsx \
        web/app/globals.css
git commit -m "feat: Custom Universe Panel — POST /api/v1/universe/analyze + client component in A1"
```
