# B-101 Crypto Exposure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add crypto exposure ETFs as a separate z-score universe class.

**Architecture:** `src/universe.py` remains the source of truth for grouped tickers. B-101 introduces a `CRYPTO` list for `BITO`, `IBIT`, and `ETHE`, adds a `Crypto` class to `UNIVERSE_BY_CLASS`, and caps crypto picks at one because the backlog explicitly calls out a distinct volatility regime.

**Tech Stack:** Python, pytest, existing Streamlit/scoring universe helpers.

---

### Task 1: Add Crypto Universe Coverage Tests

**Files:**
- Modify: `tests/test_universe.py`
- Test: `tests/test_universe.py`

- [ ] **Step 1: Write the failing test**

```python
from src import universe

EXPECTED_CRYPTO_TICKERS = ("BITO", "IBIT", "ETHE")


def test_crypto_universe_contains_backlog_crypto_etfs():
    assert tuple(universe.CRYPTO) == EXPECTED_CRYPTO_TICKERS
    assert universe.UNIVERSE_BY_CLASS["Crypto"] == universe.CRYPTO


def test_crypto_tickers_classify_as_crypto():
    for ticker in EXPECTED_CRYPTO_TICKERS:
        assert universe.class_of(ticker) == "Crypto"


def test_product_design_summary_documents_crypto_universe_count():
    text = (ROOT / "docs" / "PRODUCT_DESIGN.md").read_text(encoding="utf-8")

    assert "76+ ETFs" in text
    assert "crypto exposures" in text
    assert "73+ ETFs" not in text
    assert "67+ ETFs" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe.py -q`
Expected: FAIL because `src.universe` does not define `CRYPTO` and docs still say `73+ ETFs`.

### Task 2: Implement Crypto in the Universe Source

**Files:**
- Modify: `src/universe.py`
- Test: `tests/test_universe.py`

- [ ] **Step 1: Write minimal implementation**

Add `CRYPTO = ["BITO", "IBIT", "ETHE"]`.
Add `"Crypto": CRYPTO` to `UNIVERSE_BY_CLASS`.
Add `+ CRYPTO` to `ALL_TICKERS`.
Add `"Crypto": 1` to `TOP_N`.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_universe.py -q`
Expected: all tests pass.

### Task 3: Update Source-of-Truth Documentation and Backlog

**Files:**
- Modify: `README.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/sector-rotation-methodology.md`
- Modify: `docs/BACKLOG.md`
- Test: `tests/test_universe.py`, `git diff --check`

- [ ] **Step 1: Update visible count and class wording**

Change "73+ ETFs" to "76+ ETFs" and mention crypto exposures in README and product design text.

- [ ] **Step 2: Reconcile the methodology source of truth**

Add a crypto exposure section containing `BITO IBIT ETHE`, and add `N_crypto = 1` to the top-N target table.

- [ ] **Step 3: Move B-101 from Ideas to completed backlog**

Add a B-101 completed note with files and behavior, then remove the B-101 bullet from Ideas.

### Task 4: Verify, Commit, Push, and Deploy

**Files:**
- All modified files from Tasks 1-3

- [ ] **Step 1: Run local QA**

Run:

```powershell
python -m pytest tests/test_universe.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: tests pass, compileall exits 0, whitespace check exits 0.

- [ ] **Step 2: Commit and push**

Run:

```powershell
git add src/universe.py tests/test_universe.py README.md docs/BACKLOG.md docs/PRODUCT_DESIGN.md docs/sector-rotation-methodology.md docs/superpowers/plans/2026-05-21-b101-crypto-exposure.md
git commit -m "feat: add crypto exposure universe"
git push
```

- [ ] **Step 3: Deploy to Pi and smoke test**

Run:

```powershell
ssh -i "$env:USERPROFILE\.ssh\codex_ahadpi_ed25519" -o BatchMode=yes -o ConnectTimeout=8 ahad@10.100.102.18 'cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION && git pull --ff-only && git rev-parse --short HEAD && ./.venv/bin/python -m pytest tests/test_universe.py -q && ./.venv/bin/python -m pytest -q && old_pid=$(systemctl show sector-dashboard -p MainPID --value || true); if [ -n "$old_pid" ] && [ "$old_pid" != "0" ]; then kill -TERM "$old_pid" 2>/dev/null || true; fi; for i in 1 2 3 4 5 6 7 8 9 10; do active=$(systemctl is-active sector-dashboard || true); code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:8501/?ticker=XLK" || true); echo "poll_$i active=$active http=$code"; if [ "$active" = "active" ] && [ "$code" = "200" ]; then exit 0; fi; sleep 2; done; systemctl status sector-dashboard --no-pager; exit 1'
```

Expected: Pi pulls the commit, tests pass, service is active, and HTTP smoke returns `200`.
