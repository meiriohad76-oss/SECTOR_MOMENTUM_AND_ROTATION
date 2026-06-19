# Visual Pixel Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise all 9 Playwright similarity scores (A1-3, B1-3, C1-3) to ≥ 0.90 so the visual_parity retirement gate passes.

**Architecture:** Iterative fix loop — capture → diff → fix CSS/JSX → re-capture → verify. No new files. All changes in `web/app/globals.css`, `web/app/dashboard-screens-client.tsx`, or `web/app/chart-primitives.tsx`. Run the QA capture after each fix batch to confirm improvement.

**Tech Stack:** Next.js 14, TypeScript, CSS, Playwright via `scripts/capture_next_handoff_qa.py`.

---

## File Map

| File | Role |
|---|---|
| `web/app/globals.css` | Layout, spacing, colour, typography fixes |
| `web/app/dashboard-screens-client.tsx` | Screen layout fixes |
| `web/app/chart-primitives.tsx` | Chart sizing and positioning fixes |
| `scripts/capture_next_handoff_qa.py` | Captures all 9 views and writes similarity reports |
| `docs/browser-qa/next-handoff/latest/` | Updated capture PNGs and similarity JSON reports |

---

## Task 1: Establish baseline captures

**Files:**
- Run: `scripts/capture_next_handoff_qa.py`
- Read: `docs/browser-qa/next-handoff/latest/next_handoff_qa_report.json` (C)
- Read: `docs/browser-qa/next-handoff/latest/next_handoff_qa_report_a.json` (A)
- Read: `docs/browser-qa/next-handoff/latest/next_handoff_qa_report_b.json` (B)

- [ ] **Step 1: Start the QA API server**

In a separate terminal (keep running throughout all tasks):

```powershell
cd "c:\Users\meiri\momentum and flow"
python scripts/serve_next_qa_api.py --port 8765
```

Expected: `Serving on port 8765` (or similar startup message).

- [ ] **Step 2: Start the Next.js dev server**

In a separate terminal (keep running throughout all tasks):

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npm run dev
```

Expected: `Ready - started server on 0.0.0.0:3100`.

- [ ] **Step 3: Run all three capture profiles**

```powershell
cd "c:\Users\meiri\momentum and flow"
python scripts/capture_next_handoff_qa.py --profile c
python scripts/capture_next_handoff_qa.py --profile a
python scripts/capture_next_handoff_qa.py --profile b
```

Expected: 3 reports written to `docs/browser-qa/next-handoff/latest/`.

- [ ] **Step 4: Record baseline similarity scores**

```powershell
cd "c:\Users\meiri\momentum and flow"
python -c "
import json, pathlib
latest = pathlib.Path('docs/browser-qa/next-handoff/latest')
for profile, fname in [('C','next_handoff_qa_report.json'),('A','next_handoff_qa_report_a.json'),('B','next_handoff_qa_report_b.json')]:
    p = latest / fname
    if p.exists():
        data = json.loads(p.read_text())
        for screen in data.get('screens', []):
            print(f'{profile}-{screen[\"name\"]}: {screen.get(\"similarity\",\"n/a\")}')
"
```

Write down the 9 scores. You are targeting ≥ 0.90 for all 9.

---

## Task 2: Fix B2 Deep Dive (largest gap, target score)

**Files:**
- Modify: `web/app/globals.css`
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Open the diff — B2 Deep Dive**

Open these two images side by side and identify the largest visual delta regions:
- Capture: `docs/browser-qa/next-handoff/latest/next_b2_deepdive_candidate.png`
- Reference: `docs/browser-qa/next-handoff/latest/next_b2_deepdive_reference.png`

Look for: element sizes, spacing, column widths, font sizes, missing or extra elements, colour differences.

- [ ] **Step 2: Apply targeted CSS/JSX fixes**

Based on what you see in the diff, edit `web/app/globals.css` or `web/app/dashboard-screens-client.tsx`. Common fix patterns:

For spacing/layout gaps:
```css
/* Example: tighten a section margin */
.b-deep-dive-panel { margin-bottom: 12px; }
```

For font size differences:
```css
/* Example: match reference font size */
.b-article-body { font-size: 0.85rem; line-height: 1.55; }
```

For column width differences in the deep-dive table:
```css
/* Example: fix waterfall column width */
.waterfall-row { min-width: 640px; }
```

Make the minimal changes needed — do not restyle unrelated sections.

- [ ] **Step 3: Re-capture B2 and check score**

```powershell
python scripts/capture_next_handoff_qa.py --profile b
python -c "
import json, pathlib
data = json.loads(pathlib.Path('docs/browser-qa/next-handoff/latest/next_handoff_qa_report_b.json').read_text())
for s in data.get('screens', []):
    print(s['name'], s.get('similarity'))
"
```

Expected: B2 similarity increased. If not at 0.90 yet, repeat steps 1-2 with the updated capture.

- [ ] **Step 4: Commit B2 fix**

```powershell
cd "c:\Users\meiri\momentum and flow"
git add web/app/globals.css web/app/dashboard-screens-client.tsx docs/browser-qa/next-handoff/latest/
git commit -m "fix: visual parity B2 deep dive — raise similarity"
```

---

## Task 3: Fix C1 Overview (second largest gap)

**Files:**
- Modify: `web/app/globals.css`
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Open the diff — C1 Overview**

Compare:
- `docs/browser-qa/next-handoff/latest/next_c1_overview_candidate.png`
- `docs/browser-qa/next-handoff/latest/next_c1_overview_reference.png`

- [ ] **Step 2: Apply targeted CSS/JSX fixes for C1**

Make minimal targeted edits to close the visual delta. Focus on the largest mismatching regions first.

- [ ] **Step 3: Re-capture C and check score**

```powershell
python scripts/capture_next_handoff_qa.py --profile c
python -c "
import json, pathlib
data = json.loads(pathlib.Path('docs/browser-qa/next-handoff/latest/next_handoff_qa_report.json').read_text())
for s in data.get('screens', []):
    print(s['name'], s.get('similarity'))
"
```

- [ ] **Step 4: Commit C1 fix**

```powershell
git add web/app/globals.css web/app/dashboard-screens-client.tsx docs/browser-qa/next-handoff/latest/
git commit -m "fix: visual parity C1 overview — raise similarity"
```

---

## Task 4: Fix remaining views (C2, B1, B3, C3, A1, A2, A3)

Repeat the same diff → fix → recapture → commit loop for each remaining view. Work through them in order of largest gap first: C2 → B1 → B3 → C3 → A1 → A2 → A3.

**Files:**
- Modify: `web/app/globals.css`
- Modify: `web/app/dashboard-screens-client.tsx`
- Modify: `web/app/chart-primitives.tsx` (for chart sizing/positioning issues)

For each view:

- [ ] **Step 1: Open the diff**

Identify the view's candidate and reference PNGs in `docs/browser-qa/next-handoff/latest/`. The naming pattern is `next_{profile}{N}_{screenname}_{candidate|reference}.png`.

- [ ] **Step 2: Apply targeted CSS/JSX fixes**

Keep changes minimal and scoped to the identified delta regions.

- [ ] **Step 3: Re-capture the affected profile and verify score improved**

```powershell
# For A-profile views:
python scripts/capture_next_handoff_qa.py --profile a

# For B-profile views:
python scripts/capture_next_handoff_qa.py --profile b

# For C-profile views:
python scripts/capture_next_handoff_qa.py --profile c
```

- [ ] **Step 4: Commit each view's fix**

```powershell
git add web/app/globals.css web/app/dashboard-screens-client.tsx web/app/chart-primitives.tsx docs/browser-qa/next-handoff/latest/
git commit -m "fix: visual parity {view} — raise similarity"
```

---

## Task 5: Gate verification — all 9 views ≥ 0.90

**Files:**
- Run: `scripts/capture_next_handoff_qa.py` (all three profiles)
- Read: `scripts/check_b170_retirement_readiness.py`

- [ ] **Step 1: Run final capture for all three profiles**

```powershell
python scripts/capture_next_handoff_qa.py --profile c
python scripts/capture_next_handoff_qa.py --profile a
python scripts/capture_next_handoff_qa.py --profile b
```

- [ ] **Step 2: Verify all 9 scores are ≥ 0.90**

```powershell
python -c "
import json, pathlib
latest = pathlib.Path('docs/browser-qa/next-handoff/latest')
all_pass = True
for profile, fname in [('C','next_handoff_qa_report.json'),('A','next_handoff_qa_report_a.json'),('B','next_handoff_qa_report_b.json')]:
    data = json.loads((latest / fname).read_text())
    for s in data.get('screens', []):
        score = s.get('similarity', 0)
        status = 'PASS' if score >= 0.90 else 'FAIL'
        if score < 0.90:
            all_pass = False
        print(f'{status} {profile}-{s[\"name\"]}: {score:.4f}')
print()
print('ALL PASS' if all_pass else 'SOME VIEWS BELOW 0.90 — continue fixing')
"
```

Expected: All 9 lines print `PASS`.

- [ ] **Step 3: Run the retirement readiness checker with the 0.90 gate**

```powershell
python scripts/check_b170_retirement_readiness.py --min-similarity 0.90
```

Expected: `b170_visual_parity ok=true`.

- [ ] **Step 4: Gate commit**

```powershell
git add docs/browser-qa/next-handoff/latest/
git commit -m "chore: visual parity gate passed — all 9 views ≥ 0.90"
```
