# Debrief Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `GET /api/v1/debrief` endpoint that returns run-journal history and decisions, and a `DebriefLab` collapsible panel in the A1 overview screen.

**Architecture:** New `src/api_debrief.py` reads the run journal (run metadata + decision records) without requiring OHLCV or computing forward outcomes — MVP shows what happened, not the hit-rate. New route added to `create_app()` in `src/api_server.py` via injectable `debrief_provider`. Frontend: `web/components/DebriefLab.tsx` fetched server-side in `web/app/page.tsx`, passed through `DisplayShell` → `DashboardScreensClient` → rendered in `OverviewScreen` (A1).

**Tech Stack:** Python/FastAPI (`src/`), pytest, TypeScript, React (server + client components), CSS.

---

## File Map

| File | Role |
|---|---|
| `src/api_debrief.py` | `build_debrief_payload()` — reads journal, returns runs + decisions |
| `tests/test_api_debrief.py` | Unit tests for `build_debrief_payload` |
| `src/api_server.py` | Add `GET /api/v1/debrief` route + `debrief_provider` param |
| `web/lib/api.ts` | `DebriefPayload` type + `fetchDebrief()` helper |
| `web/app/page.tsx` | Add server-side `fetchDebrief()` call |
| `web/components/DisplayShell.tsx` | Pass `debriefData` prop through |
| `web/app/dashboard-screens-client.tsx` | Render `DebriefLab` in A1 `OverviewScreen` |
| `web/components/DebriefLab.tsx` | Collapsible panel showing runs + decisions |
| `web/app/globals.css` | `DebriefLab` styles |

---

## Task 1: `build_debrief_payload` — failing tests

**Files:**
- Create: `tests/test_api_debrief.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api_debrief.py`:

```python
from __future__ import annotations

import pytest

from src.api_debrief import build_debrief_payload
from src.run_journal import DecisionRecord, RunRecord, ScoredSnapshotRecord, append_run


def test_build_debrief_payload_returns_empty_when_journal_missing(tmp_path):
    payload = build_debrief_payload(
        journal_path=tmp_path / "missing.sqlite",
        limit=20,
    )
    assert payload["runs"] == []
    assert payload["decisions"] == []
    assert "api_version" in payload
    assert "generated_at" in payload


def test_build_debrief_payload_returns_runs_from_journal(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-debrief-1",
            started_at_utc="2026-06-01T10:00:00Z",
            provider="massive",
            universe_count=3,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLK",
                asset_class="US Sectors",
                state="STAGE_2_BULLISH",
                s_score=1.2,
                f_score=0.4,
                pillar_scores={"cmf21": 0.12},
            ),
        ],
        decisions=[
            DecisionRecord(
                decision_type="bluf",
                action="BUY",
                ticker="XLK",
                rationale="Leading RRG quadrant",
            ),
        ],
    )

    payload = build_debrief_payload(journal_path=journal_path, limit=20)

    assert len(payload["runs"]) == 1
    run = payload["runs"][0]
    assert run["run_id"] == "run-debrief-1"
    assert run["provider"] == "massive"
    assert run["universe_count"] == 3


def test_build_debrief_payload_returns_decisions_with_scores(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    append_run(
        journal_path,
        RunRecord(
            run_id="run-debrief-2",
            started_at_utc="2026-06-02T10:00:00Z",
            provider="massive",
            universe_count=2,
            metadata={},
        ),
        scored_rows=[
            ScoredSnapshotRecord(
                ticker="XLE",
                asset_class="US Sectors",
                state="WARNING",
                s_score=-0.5,
                f_score=-0.3,
                pillar_scores={},
            ),
        ],
        decisions=[
            DecisionRecord(
                decision_type="bluf",
                action="EXIT",
                ticker="XLE",
                rationale="Weakening RS",
            ),
        ],
    )

    payload = build_debrief_payload(journal_path=journal_path, limit=20)

    assert len(payload["decisions"]) >= 1
    decision = next(d for d in payload["decisions"] if d["ticker"] == "XLE")
    assert decision["action"] == "EXIT"
    assert decision["state"] == "WARNING"
    assert decision["s_score"] == pytest.approx(-0.5)


def test_build_debrief_payload_respects_limit(tmp_path):
    journal_path = tmp_path / "runs.sqlite"
    for i in range(5):
        append_run(
            journal_path,
            RunRecord(
                run_id=f"run-limit-{i}",
                started_at_utc=f"2026-06-{i+1:02d}T10:00:00Z",
                provider="massive",
                universe_count=1,
                metadata={},
            ),
            scored_rows=[],
            decisions=[],
        )

    payload = build_debrief_payload(journal_path=journal_path, limit=3)

    assert len(payload["runs"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -m pytest tests/test_api_debrief.py -v
```

Expected: `ImportError: cannot import name 'build_debrief_payload' from 'src.api_debrief'` (module doesn't exist yet).

---

## Task 2: Implement `src/api_debrief.py`

**Files:**
- Create: `src/api_debrief.py`

- [ ] **Step 1: Create the module**

Create `src/api_debrief.py`:

```python
"""Read-only debrief payload for the B-170 React migration."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .run_journal import DEFAULT_JOURNAL_PATH, list_runs, load_run_details


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
        return result if result == result else None  # NaN guard
    except (TypeError, ValueError):
        return None


def build_debrief_payload(
    journal_path: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return run journal history and decisions without OHLCV or forward outcomes."""
    path = Path(journal_path) if journal_path is not None else DEFAULT_JOURNAL_PATH

    if not path.exists():
        return {
            "api_version": "v1",
            "generated_at": _utc_now(),
            "runs": [],
            "decisions": [],
        }

    runs = list_runs(path, limit=int(limit))

    result_runs: list[dict[str, Any]] = []
    result_decisions: list[dict[str, Any]] = []

    for run in runs:
        result_runs.append({
            "run_id": run["run_id"],
            "started_at_utc": run["started_at_utc"],
            "provider": run.get("provider"),
            "universe_count": run.get("universe_count", 0),
        })

        try:
            details = load_run_details(path, run["run_id"])
        except (KeyError, Exception):
            continue

        scores_by_ticker: dict[str, dict[str, Any]] = {
            str(row.get("ticker", "")).upper(): row
            for row in details.get("scores", [])
            if row.get("ticker")
        }

        for decision in details.get("decisions", []):
            ticker = decision.get("ticker")
            if not ticker:
                continue
            symbol = str(ticker).upper()
            score = scores_by_ticker.get(symbol, {})
            result_decisions.append({
                "run_id": run["run_id"],
                "started_at_utc": run["started_at_utc"],
                "ticker": symbol,
                "action": decision.get("action"),
                "decision_type": decision.get("decision_type"),
                "rationale": decision.get("rationale"),
                "state": score.get("state"),
                "s_score": _float_or_none(score.get("s_score")),
                "f_score": _float_or_none(score.get("f_score")),
            })

    return {
        "api_version": "v1",
        "generated_at": _utc_now(),
        "runs": result_runs,
        "decisions": result_decisions,
    }
```

- [ ] **Step 2: Run tests to verify they pass**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -m pytest tests/test_api_debrief.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 3: Run full test suite to confirm no regressions**

```powershell
python -m pytest -q
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```powershell
git add src/api_debrief.py tests/test_api_debrief.py
git commit -m "feat: build_debrief_payload — run journal history API module"
```

---

## Task 3: Add `GET /api/v1/debrief` route to `api_server.py`

**Files:**
- Modify: `src/api_server.py`

- [ ] **Step 1: Add the import and provider type**

In `src/api_server.py`, find the existing import block at the top. Add this import after the existing `from .api_*` imports:

```python
from .api_debrief import build_debrief_payload
```

After the existing type aliases (around line 39 where `BacktestArtifactsProvider` is defined), add:

```python
DebriefProvider = Callable[[], dict[str, Any]]
```

- [ ] **Step 2: Add `debrief_provider` parameter to `create_app`**

Find the `create_app` function signature (around line 58). Add `debrief_provider` as the last parameter:

```python
def create_app(
    status_provider: StatusProvider | None = None,
    refresh_runner: RefreshRunner | None = None,
    data_health_provider: DataHealthProvider | None = None,
    snapshot_provider: SnapshotProvider | None = None,
    backtest_artifacts_provider: BacktestArtifactsProvider | None = None,
    ticker_chart_provider: TickerChartProvider | None = None,
    saved_inputs_path: str | None = None,
    debrief_provider: DebriefProvider | None = None,
):
```

- [ ] **Step 3: Wire the provider inside `create_app`**

Inside `create_app`, after the line `ticker_chart_reader = ticker_chart_provider or build_ticker_chart_payload` (around line 78), add:

```python
    debrief_reader = debrief_provider or build_debrief_payload
```

- [ ] **Step 4: Add the route**

Inside `create_app`, after the `@app.get("/api/v1/backtest-artifacts")` route (around line 128), add:

```python
    @app.get("/api/v1/debrief")
    def debrief() -> dict[str, Any]:
        return debrief_reader()
```

- [ ] **Step 5: Verify the API server still imports cleanly**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -c "from src.api_server import create_app; print('ok')"
```

Expected: `ok`.

- [ ] **Step 6: Run full test suite**

```powershell
python -m pytest -q
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/api_server.py
git commit -m "feat: GET /api/v1/debrief route — injectable debrief provider"
```

---

## Task 4: TypeScript type and fetch helper

**Files:**
- Modify: `web/lib/api.ts`

- [ ] **Step 1: Add `DebriefPayload` type and `fetchDebrief` function**

Open `web/lib/api.ts`. Find the end of the file (after the last existing type/function). Append:

```typescript
export type DebriefRun = {
  run_id: string;
  started_at_utc: string;
  provider: string | null;
  universe_count: number;
};

export type DebriefDecision = {
  run_id: string;
  started_at_utc: string;
  ticker: string;
  action: string | null;
  decision_type: string | null;
  rationale: string | null;
  state: string | null;
  s_score: number | null;
  f_score: number | null;
};

export type DebriefPayload = {
  api_version: string;
  generated_at: string;
  runs: DebriefRun[];
  decisions: DebriefDecision[];
};

export async function fetchDebrief(): Promise<{
  data: DebriefPayload | null;
  error: string | null;
}> {
  const base = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${base}/api/v1/debrief`, { cache: "no-store" });
    if (!res.ok) return { data: null, error: `HTTP ${res.status}` };
    const data = (await res.json()) as DebriefPayload;
    return { data, error: null };
  } catch (err) {
    return { data: null, error: String(err) };
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```powershell
cd "c:\Users\meiri\momentum and flow"
git add web/lib/api.ts
git commit -m "feat: DebriefPayload type and fetchDebrief helper"
```

---

## Task 5: Server-side fetch in `page.tsx`

**Files:**
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Add `fetchDebrief` to the server-side fetch**

Open `web/app/page.tsx`. The current content is:

```tsx
// web/app/page.tsx
import { fetchDashboardSnapshot, fetchBacktestArtifacts } from "../lib/api";
import DisplayShell from "../components/DisplayShell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function HomePage() {
  const [snapshotResult, backtestResult] = await Promise.all([
    fetchDashboardSnapshot(),
    fetchBacktestArtifacts(),
  ]);
  const backtestArtifacts = backtestResult.data;
  return (
    <main>
      <DisplayShell
        snapshot={snapshotResult.data}
        backtestArtifacts={backtestArtifacts}
        backtestError={backtestResult.error}
      />
    </main>
  );
}
```

Replace it entirely with:

```tsx
// web/app/page.tsx
import { fetchDashboardSnapshot, fetchBacktestArtifacts, fetchDebrief } from "../lib/api";
import DisplayShell from "../components/DisplayShell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function HomePage() {
  const [snapshotResult, backtestResult, debriefResult] = await Promise.all([
    fetchDashboardSnapshot(),
    fetchBacktestArtifacts(),
    fetchDebrief(),
  ]);
  return (
    <main>
      <DisplayShell
        snapshot={snapshotResult.data}
        backtestArtifacts={backtestResult.data}
        backtestError={backtestResult.error}
        debriefData={debriefResult.data}
      />
    </main>
  );
}
```

- [ ] **Step 2: Update `DisplayShell` to accept and forward `debriefData`**

Open `web/components/DisplayShell.tsx`. Find the props interface:

```tsx
}: {
  snapshot: DashboardSnapshotPayload | null;
  backtestArtifacts?: BacktestArtifactsPayload | null;
  backtestError?: string | null;
```

Replace the import line and props with:

```tsx
import type { BacktestArtifactsPayload, DebriefPayload, DashboardSnapshotPayload } from "../lib/api";
```

And update the props interface:

```tsx
}: {
  snapshot: DashboardSnapshotPayload | null;
  backtestArtifacts?: BacktestArtifactsPayload | null;
  backtestError?: string | null;
  debriefData?: DebriefPayload | null;
```

Then find where `DashboardScreensClient` is rendered (there is a call to it inside DisplayShell). Add `debriefData={debriefData}` to that call:

```tsx
        <DashboardScreensClient
          snapshot={snapshot}
          backtestArtifacts={backtestArtifacts}
          debriefData={debriefData}
        />
```

- [ ] **Step 3: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: Errors about `debriefData` not being in `DashboardScreensClient` props — that's expected, you'll fix that in Task 6.

- [ ] **Step 4: Commit (WIP — TypeScript will be clean after Task 6)**

Skip commit until Task 6 completes.

---

## Task 6: Create `DebriefLab` component and wire into `OverviewScreen`

**Files:**
- Create: `web/components/DebriefLab.tsx`
- Modify: `web/app/globals.css`
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Create `DebriefLab.tsx`**

Create `web/components/DebriefLab.tsx`:

```tsx
// web/components/DebriefLab.tsx
import type { DebriefPayload, DebriefDecision } from "../lib/api";
import { stateColor, stateShortLabel } from "../lib/state-colors";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2);
}

function ActionBadge({ action }: { action: string | null }) {
  if (!action) return <span className="dl-action dl-action-neutral">—</span>;
  const normalized = action.toUpperCase();
  const cls =
    normalized === "BUY" || normalized === "ADD"
      ? "dl-action-buy"
      : normalized === "EXIT" || normalized === "SELL"
      ? "dl-action-exit"
      : normalized === "HOLD"
      ? "dl-action-hold"
      : "dl-action-neutral";
  return <span className={`dl-action ${cls}`}>{normalized}</span>;
}

export default function DebriefLab({
  debrief,
}: {
  debrief: DebriefPayload | null | undefined;
}) {
  if (!debrief || debrief.runs.length === 0) {
    return (
      <details className="debrief-lab-panel">
        <summary className="debrief-lab-summary">Debrief Lab</summary>
        <p className="dl-empty">No run journal data available.</p>
      </details>
    );
  }

  const decisions = debrief.decisions;

  return (
    <details className="debrief-lab-panel">
      <summary className="debrief-lab-summary">
        Debrief Lab — {debrief.runs.length} runs, {decisions.length} decisions
      </summary>

      <section className="dl-section">
        <h4 className="dl-heading">Recent runs</h4>
        <table className="dl-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Provider</th>
              <th>Universe</th>
            </tr>
          </thead>
          <tbody>
            {debrief.runs.map((run) => (
              <tr key={run.run_id}>
                <td>{fmtDate(run.started_at_utc)}</td>
                <td>{run.provider ?? "—"}</td>
                <td>{run.universe_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {decisions.length > 0 && (
        <section className="dl-section">
          <h4 className="dl-heading">Decisions</h4>
          <table className="dl-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Ticker</th>
                <th>Action</th>
                <th>State</th>
                <th>S</th>
                <th>F</th>
              </tr>
            </thead>
            <tbody>
              {decisions.map((d: DebriefDecision, i: number) => (
                <tr key={`${d.run_id}-${d.ticker}-${i}`}>
                  <td>{fmtDate(d.started_at_utc)}</td>
                  <td className="dl-ticker">{d.ticker}</td>
                  <td><ActionBadge action={d.action} /></td>
                  <td>
                    {d.state ? (
                      <span
                        className="state-pill mono"
                        style={{
                          background: stateColor(d.state),
                          color: "#fff",
                          padding: "1px 6px",
                          borderRadius: "8px",
                          fontSize: "0.67rem",
                          fontWeight: 600,
                        }}
                      >
                        {stateShortLabel(d.state)}
                      </span>
                    ) : "—"}
                  </td>
                  <td className={d.s_score !== null ? (d.s_score >= 0 ? "dl-pos" : "dl-neg") : ""}>
                    {fmtScore(d.s_score)}
                  </td>
                  <td className={d.f_score !== null ? (d.f_score >= 0 ? "dl-pos" : "dl-neg") : ""}>
                    {fmtScore(d.f_score)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </details>
  );
}
```

- [ ] **Step 2: Add CSS styles for DebriefLab**

Append to the end of `web/app/globals.css`:

```css
/* ── Debrief Lab ──────────────────────────────────────── */
.debrief-lab-panel {
  margin: 18px 0 0;
}
.debrief-lab-summary {
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.65;
  padding: 6px 0;
  user-select: none;
}
.debrief-lab-summary:hover { opacity: 1; }
.dl-empty {
  font-size: 0.8rem;
  opacity: 0.5;
  margin: 8px 0;
}
.dl-section { margin-top: 14px; }
.dl-heading {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.55;
  margin: 0 0 6px;
}
.dl-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.75rem;
  font-family: var(--font-mono, monospace);
}
.dl-table th {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.12);
  font-weight: 600;
  opacity: 0.65;
  white-space: nowrap;
}
.dl-table td {
  padding: 4px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  white-space: nowrap;
}
.dl-ticker { font-weight: 600; }
.dl-pos { color: #4caf87; }
.dl-neg { color: #e07070; }
.dl-action {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 0.67rem;
  font-weight: 700;
}
.dl-action-buy     { background: rgba(76,175,135,0.25); color: #4caf87; }
.dl-action-exit    { background: rgba(224,112,112,0.25); color: #e07070; }
.dl-action-hold    { background: rgba(92,157,203,0.25); color: #5c9dcb; }
.dl-action-neutral { opacity: 0.5; }
```

- [ ] **Step 3: Wire `DebriefLab` into `DashboardScreensClient`**

Open `web/app/dashboard-screens-client.tsx`.

**3a.** Add import near the top of the file (with other imports):

```tsx
import DebriefLab from "../components/DebriefLab";
import type { DebriefPayload } from "../lib/api";
```

**3b.** Find the `DashboardScreensClient` props type (around line 20–30, it defines the props the component receives). Add `debriefData` to it:

```tsx
  debriefData?: DebriefPayload | null;
```

**3c.** Find `function OverviewScreen` (the A-profile overview, around line 248). Update its signature to receive `debriefData`:

```tsx
function OverviewScreen({
  snapshot,
  debriefData,
  ...
}: {
  snapshot: DashboardSnapshotPayload;
  debriefData?: DebriefPayload | null;
  ...
}) {
```

**3d.** Inside `OverviewScreen`, before the closing `</section>`, add:

```tsx
      <DebriefLab debrief={debriefData} />
    </section>
```

**3e.** Find where `OverviewScreen` is called inside `DashboardScreensClient`. Pass `debriefData` to it:

```tsx
<OverviewScreen snapshot={snapshot} debriefData={debriefData} />
```

- [ ] **Step 4: Verify TypeScript compiles cleanly**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Smoke-check in browser**

With the dev server running at `http://localhost:3100/?presentation=a`:
- Open the page
- Scroll to find the "Debrief Lab" `<details>` panel
- Click to expand it
- Verify it shows either "No run journal data available" (QA server has no journal) or a runs table if journal data is present

- [ ] **Step 6: Commit**

```powershell
cd "c:\Users\meiri\momentum and flow"
git add src/api_debrief.py tests/test_api_debrief.py src/api_server.py \
        web/lib/api.ts web/app/page.tsx web/components/DisplayShell.tsx \
        web/components/DebriefLab.tsx web/app/dashboard-screens-client.tsx \
        web/app/globals.css
git commit -m "feat: Debrief Lab — GET /api/v1/debrief + DebriefLab panel in A1 overview"
```
