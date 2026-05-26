# Browser QA Evidence

Generated: `2026-05-26T20:27:19Z`

Targets: `10/10` passed

| Target | Viewport | Tickets | Status | Screenshot | Notes |
| --- | --- | --- | --- | --- | --- |
| `desktop-overview` | `desktop` | B-110, B-147 | **PASS** | `docs/browser-qa/latest/desktop-overview.png` | focused text: SENTIMENT BOARD visible=true top=128 height=24 scrollTop=0; nonblank screenshot |
| `desktop-palette-view-options` | `desktop` | B-117 | **PASS** | `docs/browser-qa/latest/desktop-palette-view-options.png` | expanded: VIEW OPTIONS; checked radio: Solarized; focused text: Palette visible=true top=429 height=22 scrollTop=0; nonblank screenshot |
| `desktop-rrg-spaghetti-drill` | `desktop` | B-111, B-112, B-116 | **PASS** | `docs/browser-qa/latest/desktop-rrg-spaghetti-drill.png` | focused text: US SECTOR RELATIVE STRENGTH visible=true top=429 height=17 scrollTop=6486; nonblank screenshot |
| `desktop-comparison-view` | `desktop` | B-115 | **PASS** | `docs/browser-qa/latest/desktop-comparison-view.png` | focused text: COMPARE TICKERS visible=true top=418 height=22 scrollTop=9104; nonblank screenshot |
| `desktop-transition-pulse` | `desktop` | B-114 | **PASS** | `docs/browser-qa/latest/desktop-transition-pulse.png` | focused text: Recent transitions visible=true top=418 height=22 scrollTop=3811; visible selector: .alert-row.pulse-transition; nonblank screenshot |
| `desktop-provider-status-banner` | `desktop` | B-146 | **PASS** | `docs/browser-qa/latest/desktop-provider-status-banner.png` | focused text: Provider gap visible=true top=123 height=16 scrollTop=0; visible selector: .provider-status-banner; nonblank screenshot |
| `desktop-data-health-lanes` | `desktop` | B-147 | **PASS** | `docs/browser-qa/latest/desktop-data-health-lanes.png` | focused text: Data and dashboard health visible=true top=418 height=18 scrollTop=658; visible selector: .data-health-panel; visible selector: div[class*="st-key-data_health_refresh_market_ohlcv"] button; nonblank screenshot |
| `desktop-full-matrix-table` | `desktop` | B-113 | **PASS** | `docs/browser-qa/latest/desktop-full-matrix-table.png` | focused text: FULL 7 visible=true top=418 height=26 scrollTop=13037; hovered first full-table row; visible selector: .full-table tbody tr:first-child .row-preview; nonblank screenshot |
| `tablet-dashboard` | `tablet` | B-110, B-112, B-115 | **PASS** | `docs/browser-qa/latest/tablet-dashboard.png` | focused text: Risk regime visible=true top=669 height=45 scrollTop=0; nonblank screenshot |
| `mobile-dashboard` | `mobile` | B-110, B-112, B-114, B-116, B-117 | **PASS** | `docs/browser-qa/latest/mobile-dashboard.png` | focused text: BLUF visible=true top=380 height=22 scrollTop=474; nonblank screenshot |

Checks:
- `desktop-overview`: `text:SENTIMENT BOARD`, `text:BLUF`, `text:VIEW OPTIONS`
- `desktop-palette-view-options`: `text:VIEW OPTIONS`, `text:Palette`, `text:Solarized`
- `desktop-rrg-spaghetti-drill`: `text:SECTOR SPAGHETTI`, `text:DRILL`, `text:CMF`
- `desktop-comparison-view`: `text:COMPARE TICKERS`
- `desktop-transition-pulse`: `text:Recent transitions`, `text:BROWSER QA`, `text:STAGE 2 BULLISH`
- `desktop-provider-status-banner`: `text:Provider gap`, `text:Browser QA provider fallback fixture`
- `desktop-data-health-lanes`: `text:Data and dashboard health`, `text:Refresh market OHLCV`, `text:Refresh FRED macro`, `text:Recompute dashboard`, `text:Recompute flow signals`, `text:Refresh all lanes`
- `desktop-full-matrix-table`: `text:FULL 7`, `text:HIDE FULL`
- `tablet-dashboard`: `text:SENTIMENT BOARD`, `text:Risk regime`, `text:DRILL`
- `mobile-dashboard`: `text:SENTIMENT BOARD`, `text:BLUF`, `text:INSTRUMENTS`

Scope:
- Local dashboard browser rendering only.
- No credentials, account data, notification endpoints, or private config values are required.
- Screenshots are stored as local QA artifacts and should be regenerated after major UI changes.
