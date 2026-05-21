# Sentiment Dashboard — Product Design Document

**Audience:** UX designers, mockup tools (Claude Design, Google Stitch, Figma AI), front-end engineers.
**Companion to:** [`sector-rotation-methodology.md`](sector-rotation-methodology.md), [`../app.py`](../app.py)
**Live URL:** https://sentimentdashboard.ahaddashboards.uk

---

## 1. Product summary

A single-page institutional-grade sector rotation dashboard that monitors **73+ ETFs** across US sectors, US industries, international markets, style factors, and thematic exposures. Implements a 7-pillar methodology (cross-sectional momentum, Faber, Weinstein Stage 2, Antonacci dual momentum, RRG, business cycle, institutional flow) to identify bullish sectors and alert on bearish reversals.

**One-line product positioning:**
*"Bloomberg Terminal aesthetic, retail-trader simplicity. See sector rotation at a glance, get alerted before the breakdown."*

---

## 2. Target user

**Primary persona — "The active multi-asset retail trader" (Meiri):**
- 35–55 years old, trades ETFs and individual stocks for personal account
- Has a paid trading edge: time-series momentum, sector rotation, factor tilts
- Uses TradingView + broker apps daily, follows ~20 newsletters, watches CNBC mute on second screen
- Wants a single page that summarizes what's leading, what's breaking down, and what to act on
- Comfortable with technical analysis vocabulary (RRG, RS, CMF, OBV, etc.)
- Hates noise: refuses to scan tables; needs the dashboard to *tell* him what changed
- Reviews mornings (US pre-market for him is mid-day Israel time) and evenings (Asia open)

**Secondary persona — "The friend with portfolio access":**
- Less technical, but trusts the primary persona's signals
- Will be granted access via Cloudflare Access email allowlist
- Needs the dashboard to make sense without a tutorial

---

## 3. Core user flows

### Flow A — Morning check-in (60 seconds)
1. Visitor lands on dashboard
2. Top status row tells them at-a-glance: **risk regime** / **cycle phase** / **active warnings count**
3. Alert banner lists the last 3–8 state transitions in reverse chrono
4. They scan the **picks** cards (4 wide) — sparkline + state pill + composite score per pick
5. If something bearish: click into per-ticker drill-down → see weekly chart with 30wMA / CMF / OBV divergence
6. Close tab, take action in broker

### Flow B — Weekend deep-dive (10–20 minutes)
1. Open dashboard
2. Use sidebar to filter to one class at a time (US Sectors → US Industries → Countries → Factors)
3. Look at the big **RRG quadrant chart** for each — visually scan rotations
4. Click into 5–10 individual tickers via the drill-down picker
5. Read the full 7-pillar table (expandable section at bottom) for the entire universe
6. Cross-reference against own watchlist; update positions Monday

### Flow C — Alert investigation (3 minutes)
1. Email/Telegram pings: "XLF transitioned to BEARISH_STAGE_4"
2. Click link → dashboard opens with that ticker pre-selected in drill-down
3. Sees price < 30wMA, MA sloping down, RRG in Lagging, CMF < -0.10, Mansfield RS negative — confirms the alert
4. Acts: exits position in broker, sets short candidate

---

## 4. Information architecture

```
HOME (single scrollable page)
├── Header
│   ├── Logo / title
│   └── Last-update timestamp + theme toggle
├── Status row (3 tiles, always visible)
│   ├── Risk regime (RISK-ON / RISK-OFF)
│   ├── Cycle phase (EARLY / MID / LATE / RECESSION)
│   └── Active warnings count
├── Alerts banner (last 8 state transitions, color-coded dots)
├── Picks grid (4 cards per row, scrollable horizontally on mobile)
│   └── Card: ticker, state pill, sparkline, S-score, F-score, momentum, RRG quadrant
├── Rotation centerpiece
│   ├── Class selector (US Sectors / Industries / Countries / Factors)
│   └── Big RRG quadrant chart (interactive, hover + click)
├── Full 7-pillar table (collapsed by default, expandable)
└── Per-ticker drill-down
    ├── Ticker picker
    ├── 4 metric tiles (S-score, F-score, state, RRG quadrant)
    ├── Weekly price + 30wMA chart
    ├── CMF chart
    └── OBV / price divergence chart

SIDEBAR (persistent)
├── Theme toggle (dark default)
├── Lookback selector (3y / 5y / max)
├── Refresh data button
├── Asset class filter (multi-select)
└── Status indicators (stub mode, cache TTL)
```

---

## 5. Visual design system

### 5.1 Color palette

**Dark theme (default):**
| Token | Hex | Use |
|---|---|---|
| `bg` | `#0a0a0a` | Page background |
| `panel` | `#141414` | Tile/card background |
| `border` | `#222` | Card borders, dividers |
| `fg` | `#e6e6e6` | Primary text |
| `muted` | `#8b8b8b` | Labels, captions, secondary text |
| `accent` | `#5fa8d3` | Interactive elements, hover, focus |
| `green` | `#26d65b` | Bullish state, positive momentum, gains |
| `red` | `#ef4f4a` | Bearish state, negative momentum, losses |
| `amber` | `#e6b450` | Warning state, neutral / improving |
| `blue` | `#5fa8d3` | Improving quadrant accents |

**Light theme:**
| Token | Hex |
|---|---|
| `bg` | `#fafafa` |
| `panel` | `#fff` |
| `border` | `#e0e0e0` |
| `fg` | `#111` |
| `muted` | `#666` |
| (greens/reds/amber stay the same for state consistency) |

### 5.2 Typography

**Two-font system:**
- **Inter** (variable weights 400/500/600/700) — for prose, labels, navigation
- **JetBrains Mono** (400/500/700) — for **all numeric values**, ticker symbols, state pills, timestamps, quadrant labels, indicator names

> **Rule of thumb:** if it's a number or a code-like identifier (TICKER, +1.83, RISK-ON, STAGE_2_BULLISH), use JetBrains Mono. If it's a sentence, use Inter.

**Type scale:**
| Element | Family | Size | Weight | Letter-spacing |
|---|---|---|---|---|
| Page title | JetBrains Mono | 1.6rem | 700 | 0.04em |
| Section header | JetBrains Mono | 0.75rem | 600 | 0.12em uppercase |
| Tile label | Inter | 0.72rem | 500 | 0.08em uppercase |
| Tile value (number) | JetBrains Mono | 1.4rem | 600 | 0 |
| Tile sub (caption) | JetBrains Mono | 0.78rem | 400 | 0 |
| Card ticker | JetBrains Mono | 1.05rem | 700 | 0.04em |
| Card metrics (numbers) | JetBrains Mono | 0.78rem | 500 | 0 |
| Card footer (e.g. quadrant) | JetBrains Mono | 0.7rem | 500 | 0.04em uppercase |
| Body prose | Inter | 0.9rem | 400 | 0 |
| State pill | JetBrains Mono | 0.72rem | 600 | 0.03em |

### 5.3 Spacing & layout

- **Grid:** 12-column responsive, 24px gutters
- **Tile/card padding:** 14px vertical, 18px horizontal (tiles), 12px/14px (cards)
- **Section spacing:** 24px between major sections, divider line above each section header
- **Border radius:** 6px on tiles, cards, and pills (matches Bloomberg-style rectangularity — keep it tight, not pill-shaped)
- **Border thickness:** 1px standard; 3px left-accent on cards (state-colored)
- **Page max-width:** 1440px centered (works comfortably on 16:9 monitors)

### 5.4 State colors (consistent across product)

| State | Color | When |
|---|---|---|
| `STAGE_2_BULLISH` | green `#1A8A4E` | Active buy candidate, all gates passed |
| `HOLD` | blue `#5C9DCB` | In a position that's intact, no action |
| `WARNING` | amber `#E2A53A` | One+ pillars deteriorating, tighten stops |
| `EXIT` | red-orange `#D5562C` | Sell on next open |
| `BEARISH_STAGE_4` | dark red `#A21E2C` | Avoid; short candidate |
| `STAGE_1_BASING` | gray `#9E9E9E` | Watch list, recovering from bear |

Apply the state color as:
- The left border (3px) of picks cards
- The background of state pills (white text on color)
- The bullet dot on alert rows
- The marker fill on RRG dots

---

## 6. Key components (with specs)

### 6.1 Status tile

```
┌────────────────────────┐
│ RISK REGIME            │  ← label, uppercase, 0.72rem, muted color
│ 🟢 RISK-ON             │  ← value, JetBrains Mono 1.4rem 600
│ SPY > 10mo SMA         │  ← sub caption, JetBrains Mono 0.78rem muted
└────────────────────────┘
```

- Width: column 1/3 on desktop, full-width on mobile
- Background: `panel`, 1px border, 6px radius
- Padding: 14px / 18px
- Value color is green or red based on regime
- Three tiles in a row at top of page

### 6.2 Alert row

```
┌──────────────────────────────────────────────────────┐
│ 🔴 XLF        EXIT → BEARISH_STAGE_4    yesterday    │
└──────────────────────────────────────────────────────┘
```

- Single row of mono text, 0.84rem, 8/12 padding
- 8px round dot at left (state color)
- Ticker bold (min-width 64px), state-change text in muted color, date right-aligned
- 1px bottom border between rows
- Container has 1px outer border, 6px radius, `panel` background

### 6.3 Pick card

```
┌──────────────────────┐
│ XLK            HOLD  │  ← ticker (mono) + pill (right)
│ US Sectors           │  ← class name, small, muted
│                      │
│ ▁▂▃▅▇█ sparkline     │  ← 50px tall, no axes, green or red fill
│                      │
│ S +1.83  ·  F +0.67  │  ← composite + flow scores, mono
│ MOM +32.4%  Stage 2  │  ← momentum colored, stage number
│ LEADING              │  ← RRG quadrant, footer caption
└──────────────────────┘
```

- Width: 1/4 column on desktop, 1/2 on tablet, full on mobile
- Background: `panel`, 1px border, 3px LEFT border (state color)
- Padding: 12px / 14px
- Hover: left border shifts to `accent` color, slight `border-color` transition
- Click target: entire card (opens drill-down panel scrolled to position with ticker pre-selected)

### 6.4 State pill

- Background: state color
- Foreground: white
- Padding: 2px / 9px
- Border-radius: 11px (slightly pill-shaped — this is the one place we go round)
- Font: JetBrains Mono, 0.72rem, 600, 0.03em letter-spacing
- All caps (already in the state name)

### 6.5 RRG chart (centerpiece)

- Plotly scatter, square aspect ratio, 560px tall on desktop
- X axis: `JdK RS-Ratio`, range [80, 120], no grid above 100/100 (just zero lines)
- Y axis: `JdK RS-Momentum`, range [80, 120]
- Four quadrant background tints (7% opacity each):
  - Top-right (Leading): green tint
  - Bottom-right (Weakening): amber tint
  - Bottom-left (Lagging): red tint
  - Top-left (Improving): blue tint
- Quadrant labels in corners, mono, all caps, 0.7rem
- Each ticker rendered as a marker dot (state-colored) + ticker label above
- Hover tooltip: ticker, RS-Ratio, RS-Momentum
- Click: opens drill-down with that ticker

### 6.6 Per-ticker drill-down

Four metric tiles in a row:
- Composite score (mono, signed)
- Flow score (color: green/red by sign; sub label: "VETO" or "OK")
- State (pill or large colored text)
- RRG quadrant (text only)

Then three full-width charts stacked or in 2-column:
- Weekly price + 30wMA line (Plotly)
- CMF(21) with ±0.10 reference lines
- OBV + price overlay (dual-axis)

Below: expandable raw table of every indicator value for that ticker.

---

## 7. Responsive behavior

- **Desktop ≥ 1200px:** 4-up cards, side-by-side charts in drill-down, sidebar visible
- **Tablet 768–1199px:** 3-up cards, stacked charts in drill-down, sidebar collapsible
- **Mobile < 768px:** 1-up cards (vertical stack), full-width charts, hamburger sidebar
- Status tiles always 3-up horizontally; on phones they get smaller but stay in row

---

## 8. Interaction & animation notes

- **No flashy animations.** This is a trading dashboard — fast, calm, instant feedback.
- **Hover states:** card left border accent change (`var(--border)` → `var(--accent)`), 150ms ease
- **Loading states:** subtle inline skeleton bars in cards; never a full-page spinner
- **State transitions:** when a state changes, briefly (500ms) pulse the card's left border in the new state color before settling
- **Refresh data button:** during fetch, replace text with "FETCHING…" and animated dots
- **Chart hover:** instant tooltip, no fade

---

## 9. Accessibility

- All text must hit WCAG AA on dark theme: `fg #e6e6e6` on `bg #0a0a0a` = contrast 17:1 ✅
- State pills: white on state color, all meet AA at 0.72rem font size
- Keyboard navigation: tab through tiles → alerts → cards → RRG → table → drill-down
- Focus rings: 2px solid `accent` color, 2px offset
- All charts must have a fallback table/text representation in expandable section beneath (we already do this — the full 7-pillar table)
- Sparklines on cards have aria-label describing the trend ("XLK price up 32% over the last year")

---

## 10. Aesthetic references

When building mockups, draw inspiration from:

**Primary:**
- **Bloomberg Terminal** — dense, mono numerics, dark, state-colored cells. The gold standard for institutional dashboards.
- **TradingView Pro layout** — clean charts, dark theme, pill-shaped indicators, hover tooltips

**Secondary:**
- **Linear app** — for the typography hierarchy (Inter for prose, mono for IDs/numbers), card design, subtle hover states
- **Stripe dashboard** — for the spacing, restraint, and the way they handle status indicators
- **Datadog/Grafana** — for the alert banner pattern, time-series charts

**Anti-patterns (avoid):**
- ❌ Pastel colors / Material Design — too "consumer app", not professional
- ❌ Heavy shadows / gradients — flat is the rule
- ❌ Round avatars / cute illustrations — strictly information, no decoration
- ❌ Auto-playing sounds or motion — never
- ❌ Onboarding overlays / tooltips on first visit — assume user is sophisticated

---

## 11. Component checklist for mockup tools

Build mockups for these screens, in this order of priority:

1. **Main dashboard (desktop, dark)** — full scroll, all sections visible
2. **Main dashboard (desktop, light)** — same content, light theme
3. **Per-ticker drill-down state** — what the page looks like when a ticker is selected
4. **Alert state** — a moment with 3+ active warnings showing
5. **Mobile view (dark)** — full scroll on a phone
6. **Empty state** — what shows when no picks meet gates (e.g., during risk-off)
7. **Loading state** — first page load while data is being fetched

For each screen, include:
- Status tiles with realistic values
- 4–8 picks cards with varied states and sparkline shapes
- Realistic RRG with 10–15 dots scattered across quadrants
- 5+ recent state transitions in the alerts banner

---

## 12. Sample data for mockups

Use this realistic mock data set when populating mockups:

**Status:**
- Risk regime: RISK-ON
- Cycle phase: MID
- Active warnings: 3

**Recent transitions:**
- 🔴 XLF — EXIT → BEARISH_STAGE_4 — yesterday
- 🟠 SOXX — HOLD → WARNING — 2d ago
- 🟢 XLE — HOLD → STAGE_2_BULLISH — 5d ago
- 🟡 KRE — STAGE_2_BULLISH → WARNING — 1w ago
- 🟢 SMH — WARNING → HOLD — 1w ago

**Top picks (cards):**
| Ticker | Class | State | S | F | Mom | Stage | Quadrant |
|---|---|---|---|---|---|---|---|
| XLK | US Sectors | HOLD | +1.83 | +0.67 | +32.4% | 2 | LEADING |
| XLE | US Sectors | STAGE_2_BULLISH | +1.14 | +0.46 | +32.7% | 2 | LEADING |
| SMH | US Industries | STAGE_2_BULLISH | +1.28 | +0.64 | +88.4% | 2 | LEADING |
| MTUM | Factors | HOLD | +0.75 | +0.49 | +20.8% | 2 | LEADING |
| EWY | Countries | WARNING | +2.29 | +0.33 | +164.9% | 2 | WEAKENING |
| ICLN | US Industries | STAGE_2_BULLISH | +0.98 | +1.01 | +52.0% | 2 | LEADING |
| OIH | US Industries | STAGE_2_BULLISH | +0.83 | +0.29 | +78.0% | 2 | LEADING |
| VLUE | Factors | WARNING | +1.36 | +0.01 | +48.7% | 2 | LEADING |

**Per-ticker drill-down (use XLF as the example — most dramatic):**
- Composite: −0.94
- Flow: −0.48 (VETO)
- State: BEARISH_STAGE_4
- RRG: LAGGING
- Price chart: weekly close declining below 30wMA, MA sloping down
- CMF chart: dipping below −0.10
- OBV chart: making lower lows while price was making higher highs (clear divergence)

---

## 13. Tools & deliverables

**For UX mockups, use:**
- **Claude Design** — paste sections 5–12 of this doc, ask for the main dashboard mockup first
- **Google Stitch** — similar workflow; emphasizes the typography system in section 5.2
- **Figma AI** — if you want editable vectors after

**Expected deliverables from mockup phase:**
- 7 screen mockups (per section 11) in PNG or Figma
- Color/typography token export (CSS variables file)
- Component spec sheet (one component per page) — Figma annotations or PDF

**Hand-off to implementation:**
- Compare proposed mockup to existing `app.py` and `src/visuals.py`
- File an issue per visual change with before/after screenshots
- Implement in Streamlit + CSS

---

## 14. Out of scope (for v2; document but don't design)

- Native iOS/Android apps (we have a responsive web app)
- Real-time WebSocket data (we run on yfinance 1-hour cache)
- Position tracking / P&L (this dashboard is signals-only, not a broker)
- News integration (out of scope; Bloomberg-style headline ticker is a v3 idea)
- Custom universe builder UI (currently in `src/universe.py` code; web UI to manage is v3)
- Multi-user / multi-tenant (Cloudflare Access is per-email allowlist for now)

---

## 15. Open questions for designer

1. Should the **sparklines** on cards include a horizontal "30-week MA" line so the Weinstein context is visible in a glance? Or keep cards pure-price for cleanliness?
2. The **state pill** — do we double-encode (color + emoji icon), or keep it text-only? Text-only is more "Bloomberg," icon-tagged is more "Linear."
3. For **mobile**, do we ditch the RRG chart entirely (too small to read on a phone) or render it with a "fullscreen" expand button?
4. **Resolved in B-130:** add a read-only portfolio / single-stock analyzer. It accepts one ticker or CSV/XLS/XLSX holdings upload, maps positions to the existing methodology snapshot, flags WARNING / EXIT / BULLISH action lists, and does not save portfolios or connect to broker APIs.

---

End of document.
