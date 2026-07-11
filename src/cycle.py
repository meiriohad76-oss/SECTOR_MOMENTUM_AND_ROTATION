"""Business-cycle phase → sector basket mapping (Phase 4.1 import decoupling).

This module is intentionally import-free (no data.py, no yfinance) so that
``src.scoring`` can import ``cycle_tilt`` without dragging in the network I/O
chain:  scoring → macro → data → yfinance.

The full macro-regime *classifier* lives in src/macro.py and may import
data.py as needed.  This module only provides the pure lookup table used
during composite score computation.
"""
from __future__ import annotations


# Fidelity Business Cycle — which US-sector ETFs are favoured in each phase.
# Matches the PHASE_FAVORED_SECTORS definition that was previously in macro.py.
PHASE_FAVORED_SECTORS: dict[str, set[str]] = {
    "EARLY":     {"XLY", "XLF", "XLRE", "XLI", "XLK", "XLB"},
    "MID":       {"XLK", "XLC", "XLI"},
    "LATE":      {"XLE", "XLB", "XLP", "XLV"},
    "RECESSION": {"XLP", "XLU", "XLV"},
}


def cycle_tilt(ticker: str, phase: str) -> float:
    """Return +1 (favoured), -1 (disfavoured US sector), or 0 (neutral/unknown).

    Favoured: ticker is in the phase basket.
    Disfavoured: any XL* sector ETF *not* in the basket (relative headwind).
    Neutral: non-sector tickers, global/country/theme ETFs, or unknown phase.
    """
    favored = PHASE_FAVORED_SECTORS.get(phase, set())
    if not favored:
        return 0.0
    if ticker in favored:
        return 1.0
    if ticker.startswith("XL"):
        return -1.0
    return 0.0
