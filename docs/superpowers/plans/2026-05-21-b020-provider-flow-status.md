# B-020 Provider Flow Status Verification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion before marking this ticket complete. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the stale B-020 backlog wording with the implementation already present in `backlog-stepwise-qa`.

**Architecture:** No code changes in this slice. The provider seams already live in `src/flow.py`; this note records the implemented state and the verification commands that prove the offline contracts remain green.

**Tech Stack:** Python, pytest, Massive, FINRA, SEC EDGAR 13F data-set integration seams.

---

## Implemented Provider Seams

- `block_trade_upside_ratio()` uses Massive `/v3/trades` when `MASSIVE_TRADES_STUB_MODE=false`.
- `dark_pool_pct()` uses FINRA ATS weekly summary when `FINRA_ATS_STUB_MODE=false`.
- `short_interest_delta_15d()` uses FINRA consolidated short-interest records when `FINRA_SHORT_INTEREST_STUB_MODE=false`.
- `thirteen_f_net_buys_q()` uses configured SEC 13F data-set zip plus `SEC_13F_CUSIP_<TICKER>` mappings when `SEC_13F_STUB_MODE=false`.

## Verification

- [x] `python -m pytest tests/test_flow.py -q` -> `33 passed`
- [x] `python -m pytest -q` -> `184 passed`

## Activation Notes

Leave each provider-specific stub flag unset or `true` until the relevant source is configured. Flip only the feed you are validating:

- `MASSIVE_TRADES_STUB_MODE=false`
- `FINRA_ATS_STUB_MODE=false`
- `FINRA_SHORT_INTEREST_STUB_MODE=false`
- `SEC_13F_STUB_MODE=false`

## Residual Risk

The tests verify request construction, parsers, neutral fallback behavior, and provider seam wiring offline. Live provider validation still depends on local secrets/configuration and should be repeated after changing API keys, SEC user-agent settings, ticker CUSIP mappings, or upstream provider schemas.
