# B-010 ETF Primary-Flow Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hard-coded ETF primary-flow stub with a tested provider seam that can fetch Massive-rendered issuer flow records and compute five-day ETF primary-flow percent safely.

**Architecture:** Add pure parsing and flow-calculation helpers in `src/flow.py`, then wire `etf_primary_flow_5d_pct()` to a Massive browser-content boundary. Keep `STUB_MODE` enabled by default and return neutral `0.0` whenever live provider mode is not explicitly configured, credentials are absent, source records are incomplete, or the provider request fails.

**Tech Stack:** Python 3, pandas/numpy, requests, pytest, Streamlit secrets/env vars.

---

## Files

- Modify: `src/flow.py`
- Modify: `tests/test_flow.py`
- Modify: `.streamlit/secrets.toml.example`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

---

### Task 1: Add Pure Primary-Flow Calculation Tests

**Files:**
- Modify: `tests/test_flow.py`

- [ ] **Step 1: Write failing tests for parsing and five-day flow math**

Append to `tests/test_flow.py`:

```python
def test_parse_primary_flow_snapshots_accepts_json_records():
    payload = """
    {
      "records": [
        {"as_of": "2026-05-12", "shares_outstanding": "100,000,000", "nav": "$50.00", "aum": "$5,000,000,000"},
        {"as_of": "2026-05-19", "shares_outstanding": "102,000,000", "nav": "$50.00", "aum": "$5,100,000,000"}
      ]
    }
    """

    snapshots = flow.parse_primary_flow_snapshots(payload)

    assert len(snapshots) == 2
    assert snapshots[0].as_of == "2026-05-12"
    assert snapshots[0].shares_outstanding == 100_000_000
    assert snapshots[1].aum == 5_100_000_000


def test_primary_flow_5d_pct_uses_share_change_nav_over_latest_aum():
    snapshots = [
        flow.PrimaryFlowSnapshot("2026-05-12", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-13", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-14", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-15", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-18", 101_000_000, 50.0, 5_050_000_000),
        flow.PrimaryFlowSnapshot("2026-05-19", 102_000_000, 50.0, 5_100_000_000),
    ]

    result = flow.primary_flow_5d_pct_from_snapshots(snapshots)

    assert result == pytest.approx(1.9607843137)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_flow.py -q
```

Expected: fails because `PrimaryFlowSnapshot`, `parse_primary_flow_snapshots`, and `primary_flow_5d_pct_from_snapshots` do not exist yet.

- [ ] **Step 3: Commit is not allowed in RED**

Do not commit until Task 2 makes these tests pass.

---

### Task 2: Implement Pure Parser And Flow Math

**Files:**
- Modify: `src/flow.py`

- [ ] **Step 1: Add imports, dataclass, parser, and calculation helpers**

Add these imports near the top of `src/flow.py`:

```python
import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional
```

Replace the existing `from typing import Optional` import if present so imports stay unique.

Add this helper block above `chaikin_money_flow()`:

```python
@dataclass(frozen=True)
class PrimaryFlowSnapshot:
    as_of: str
    shares_outstanding: float
    nav: float
    aum: float


def _parse_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    multiplier = 1.0
    suffix = text[-1:].upper()
    if suffix in {"K", "M", "B", "T"}:
        multiplier = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0, "T": 1_000_000_000_000.0}[suffix]
        text = text[:-1]
    text = re.sub(r"[^0-9.\\-]", "", text)
    if not text:
        return None
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _pick(record: dict, names: Iterable[str]):
    normalized = {str(k).strip().lower().replace(" ", "_"): v for k, v in record.items()}
    for name in names:
        key = name.lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]
    return None


def _snapshot_from_record(record: dict) -> Optional[PrimaryFlowSnapshot]:
    as_of = _pick(record, ["as_of", "as of", "date", "trade_date", "holdings_date"])
    shares = _parse_float(_pick(record, ["shares_outstanding", "shares outstanding", "sho", "sharesOutstanding"]))
    nav = _parse_float(_pick(record, ["nav", "net_asset_value", "net asset value"]))
    aum = _parse_float(_pick(record, ["aum", "net_assets", "net assets", "total_net_assets", "total net assets"]))
    if as_of is None or shares is None or nav is None or aum is None or aum == 0:
        return None
    return PrimaryFlowSnapshot(str(as_of), shares, nav, aum)


def _records_from_json(payload: str) -> list[dict]:
    parsed = json.loads(payload)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        for key in ("records", "data", "snapshots", "rows"):
            rows = parsed.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _records_from_csv(payload: str) -> list[dict]:
    lines = [line for line in payload.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if ("shares" in lowered or "sho" in lowered) and ("nav" in lowered or "net asset" in lowered):
            reader = csv.DictReader(io.StringIO("\\n".join(lines[idx:])))
            return [row for row in reader]
    reader = csv.DictReader(io.StringIO(payload))
    return [row for row in reader] if reader.fieldnames else []


def parse_primary_flow_snapshots(payload: str) -> list[PrimaryFlowSnapshot]:
    if not payload or not payload.strip():
        return []
    records: list[dict]
    try:
        records = _records_from_json(payload)
    except json.JSONDecodeError:
        records = _records_from_csv(payload)
    snapshots = [_snapshot_from_record(record) for record in records]
    return sorted([snapshot for snapshot in snapshots if snapshot is not None], key=lambda item: item.as_of)


def primary_flow_5d_pct_from_snapshots(
    snapshots: list[PrimaryFlowSnapshot],
    lookback_observations: int = 5,
) -> Optional[float]:
    if len(snapshots) <= lookback_observations:
        return None
    ordered = sorted(snapshots, key=lambda item: item.as_of)
    latest = ordered[-1]
    prior = ordered[-lookback_observations - 1]
    if latest.aum == 0:
        return None
    estimated_net_flow = (latest.shares_outstanding - prior.shares_outstanding) * latest.nav
    return float(estimated_net_flow / latest.aum * 100.0)
```

- [ ] **Step 2: Run targeted flow tests**

Run:

```powershell
python -m pytest tests/test_flow.py -q
```

Expected: all flow tests pass.

- [ ] **Step 3: Commit task**

```powershell
git add src/flow.py tests/test_flow.py
git commit -m "test: add ETF primary flow math"
```

---

### Task 3: Add Massive Provider Boundary Tests

**Files:**
- Modify: `tests/test_flow.py`

- [ ] **Step 1: Write failing tests for provider fallback and Massive request shape**

Append to `tests/test_flow.py`:

```python
def test_etf_primary_flow_returns_neutral_when_live_mode_has_no_source(monkeypatch):
    monkeypatch.setattr(flow, "STUB_MODE", False)
    monkeypatch.delenv("ETF_PRIMARY_FLOW_URL_XLK", raising=False)

    assert flow.etf_primary_flow_5d_pct("XLK") == 0.0


def test_etf_primary_flow_uses_provider_payload_when_configured(monkeypatch):
    payload = {
        "records": [
            {"as_of": "2026-05-12", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-13", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-14", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-15", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-18", "shares_outstanding": 101_000_000, "nav": 50.0, "aum": 5_050_000_000},
            {"as_of": "2026-05-19", "shares_outstanding": 102_000_000, "nav": 50.0, "aum": 5_100_000_000},
        ]
    }
    monkeypatch.setattr(flow, "STUB_MODE", False)
    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", lambda ticker: json.dumps(payload))

    assert flow.etf_primary_flow_5d_pct("XLK") == pytest.approx(1.9607843137)


def test_fetch_massive_browser_content_sends_bearer_token_and_browser_params(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200
        text = "content"

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(flow.requests, "get", fake_get)

    content = flow._fetch_massive_browser_content(
        "https://issuer.example/flow.csv",
        api_key="secret",
        timeout=7,
    )

    assert content == "content"
    assert calls[0][0] == flow.MASSIVE_BROWSER_URL
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"
    assert calls[0][1]["params"]["url"] == "https://issuer.example/flow.csv"
    assert calls[0][1]["params"]["format"] == "raw"
    assert calls[0][1]["timeout"] == 7
```

Also add `import json` near the top of `tests/test_flow.py`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_flow.py -q
```

Expected: fails because `_fetch_massive_browser_content`, `_fetch_primary_flow_payload`, env URL resolution, and live-mode `etf_primary_flow_5d_pct()` do not exist yet.

- [ ] **Step 3: Commit is not allowed in RED**

Do not commit until Task 4 makes these tests pass.

---

### Task 4: Implement Massive Provider Boundary And Wire Stub

**Files:**
- Modify: `src/flow.py`

- [ ] **Step 1: Add provider imports and constants**

Add these imports to `src/flow.py`:

```python
import os

import requests
```

Then add this config helper block above the `STUB_MODE` assignment and replace `STUB_MODE = True`:

```python
def _resolve_secret(name: str) -> Optional[str]:
    try:
        import streamlit as st  # type: ignore
        if hasattr(st, "secrets"):
            try:
                value = st.secrets.get(name)
                if value:
                    return str(value).strip()
            except Exception:
                pass
    except Exception:
        pass
    value = os.environ.get(name)
    return value.strip() if value else None


def _config_flag(name: str, default: bool) -> bool:
    value = _resolve_secret(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}
```

Replace `STUB_MODE = True` with:

```python
STUB_MODE = _config_flag("FLOW_STUB_MODE", True)
```

Add these constants below `STUB_MODE`:

```python
MASSIVE_BROWSER_URL = os.environ.get("MASSIVE_BROWSER_URL", "https://render.joinmassive.com/browser")
PRIMARY_FLOW_SOURCE_ENV_PREFIX = "ETF_PRIMARY_FLOW_URL_"
```

- [ ] **Step 2: Add provider helpers above `etf_primary_flow_5d_pct()`**

```python
def _primary_flow_source_url(ticker: str) -> Optional[str]:
    key = f"{PRIMARY_FLOW_SOURCE_ENV_PREFIX}{ticker.upper().replace('-', '_')}"
    return _resolve_secret(key)


def _fetch_massive_browser_content(
    source_url: str,
    api_key: Optional[str] = None,
    timeout: int = 20,
) -> Optional[str]:
    token = api_key or _resolve_secret("MASSIVE_API_KEY")
    if not token:
        return None
    response = requests.get(
        MASSIVE_BROWSER_URL,
        params={
            "url": source_url,
            "format": "raw",
            "expiration": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def _fetch_primary_flow_payload(ticker: str) -> Optional[str]:
    source_url = _primary_flow_source_url(ticker)
    if not source_url:
        return None
    return _fetch_massive_browser_content(source_url)
```

- [ ] **Step 3: Replace `etf_primary_flow_5d_pct()` implementation**

Replace the current function with:

```python
def etf_primary_flow_5d_pct(ticker):
    if STUB_MODE:
        return 0.0
    try:
        payload = _fetch_primary_flow_payload(ticker)
        if not payload:
            return 0.0
        snapshots = parse_primary_flow_snapshots(payload)
        value = primary_flow_5d_pct_from_snapshots(snapshots)
        return float(value) if value is not None else 0.0
    except Exception:
        return 0.0
```

- [ ] **Step 4: Run targeted flow tests**

Run:

```powershell
python -m pytest tests/test_flow.py -q
```

Expected: all flow tests pass.

- [ ] **Step 5: Run full pytest suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit task**

```powershell
git add src/flow.py tests/test_flow.py
git commit -m "feat: wire ETF primary flow provider seam"
```

---

### Task 5: Document Configuration And Mark B-010

**Files:**
- Modify: `.streamlit/secrets.toml.example`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Document secrets**

Append to `.streamlit/secrets.toml.example`:

```toml
# Optional Pillar 7 primary-flow provider.
# Keep FLOW_STUB_MODE unset/true for neutral stub behavior.
# Set FLOW_STUB_MODE=false only after configuring Massive and per-ticker source URLs.
MASSIVE_API_KEY = "your-massive-api-key-here"
FLOW_STUB_MODE = "true"
ETF_PRIMARY_FLOW_URL_SOXX = "https://issuer.example/path/to/soxx-primary-flow.csv"
```

- [ ] **Step 2: Update README provider notes**

Replace the sentence:

```markdown
Each stubbed signal has a `get_<signal>()` hook in `src/flow.py`. After wiring, flip `STUB_MODE = False` at the top of that file.
```

with:

```markdown
Each stubbed signal has a hook in `src/flow.py`. ETF primary flow now has a provider seam: leave `FLOW_STUB_MODE=true` for neutral local behavior, or set `FLOW_STUB_MODE=false` plus `MASSIVE_API_KEY` and `ETF_PRIMARY_FLOW_URL_<TICKER>` values in Streamlit secrets or environment variables.
```

- [ ] **Step 3: Mark B-010 in backlog**

Replace the B-010 status details in `docs/BACKLOG.md` with:

```markdown
**Status:** provider seam implemented in `backlog-stepwise-qa`; production default remains neutral until `FLOW_STUB_MODE=false`, `MASSIVE_API_KEY`, and per-ticker source URLs are configured.
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src
git diff --check HEAD
git status --short --branch
```

Expected: tests pass, compile check exits 0, diff check is clean, and branch has only intentional committed changes after the next commit.

- [ ] **Step 5: Commit task**

```powershell
git add .streamlit/secrets.toml.example README.md docs/BACKLOG.md
git commit -m "docs: document ETF primary flow configuration"
```

---

### Task 6: Final B-010 QA Gate

**Files:**
- No new file edits unless a verification failure requires a fix.

- [ ] **Step 1: Run B-010 verification suite**

Run:

```powershell
python -m pytest tests/test_flow.py -q
python -m pytest -q
python -m compileall app.py src
git diff --check origin/main...HEAD
git status --short --branch
```

Expected: all commands pass and the working tree is clean.

- [ ] **Step 2: Confirm provider is safe by default**

Run:

```powershell
@'
from src.flow import STUB_MODE, etf_primary_flow_5d_pct
print("STUB_MODE", STUB_MODE)
print("XLK_FLOW", etf_primary_flow_5d_pct("XLK"))
'@ | python -
```

Expected:

```text
STUB_MODE True
XLK_FLOW 0.0
```

- [ ] **Step 3: Request final subagent review**

Reviewers must confirm:

- No live network calls happen while `STUB_MODE` is true.
- Missing Massive config returns neutral flow instead of crashing.
- Parser/calculation tests protect the `nf_5d_pct` formula.
- Docs do not imply live provider mode is enabled by default.
