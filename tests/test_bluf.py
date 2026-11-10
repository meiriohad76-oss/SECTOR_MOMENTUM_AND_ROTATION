from __future__ import annotations

from src.bluf import build_bluf, leading_sectors, portfolio_view, top_leading_stocks


def _row(ticker, asset_class, state, score, quadrant="Leading"):
    return {"ticker": ticker, "asset_class": asset_class, "state": state, "s_score": score, "quadrant": quadrant}


ROWS = [
    _row("XLK", "US Sectors", "STAGE_2_BULLISH", 2.0),
    _row("XLF", "US Sectors", "HOLD", 1.0),
    _row("XLE", "US Sectors", "EXIT", 3.0),
    _row("XLU", "US Sectors", "STAGE_2_BULLISH", 0.5, quadrant="Lagging"),
    _row("NVDA", "Mega-Cap Stocks", "STAGE_2_BULLISH", 1.8),
    _row("AAPL", "Mega-Cap Stocks", "HOLD", 1.2),
    _row("JPM", "Mega-Cap Stocks", "HOLD", 0.9),
    _row("XOM", "Mega-Cap Stocks", "STAGE_2_BULLISH", 2.5),
    _row("KO", "Mega-Cap Stocks", "EXIT", 2.9),
]
SECTOR_MAP = {"NVDA": "XLK", "AAPL": "XLK", "JPM": "XLF", "XOM": "XLE", "KO": "XLP"}


def test_leading_sectors_need_leading_quadrant_and_eligible_state():
    assert [r["ticker"] for r in leading_sectors(ROWS)] == ["XLK", "XLF"]


def test_top_leading_stocks_only_from_leading_sectors_and_eligible_states():
    picks = top_leading_stocks(ROWS, SECTOR_MAP)

    assert [p["ticker"] for p in picks] == ["NVDA", "AAPL", "JPM"]
    assert picks[0]["sector"] == "XLK"


def test_unmapped_and_exit_stocks_are_never_picked():
    picks = top_leading_stocks(ROWS, SECTOR_MAP)

    assert "XOM" not in [p["ticker"] for p in picks]
    assert "KO" not in [p["ticker"] for p in picks]


def test_portfolio_view_reports_sector_and_leadership_and_unscored():
    view = portfolio_view(ROWS, SECTOR_MAP, ["nvda", "KO", "ZZZ", "XLK"], {"XLK", "XLF"})

    assert view[0] == {"ticker": "NVDA", "sector": "XLK", "sector_leading": True, "state": "STAGE_2_BULLISH", "s_score": 1.8, "scored": True, "sector_note": None}
    assert view[1]["sector_leading"] is False
    assert view[2]["sector"] is None and view[2]["scored"] is False
    assert view[3]["sector"] == "XLK" and view[3]["sector_leading"] is True


def test_build_bluf_summarizes_and_labels_actions_only():
    bluf = build_bluf(
        rows=ROWS,
        sector_map=SECTOR_MAP,
        holdings=["KO", "AAPL"],
        watchlist=["JPM"],
        risk_on=True,
        degraded=False,
        flow_coverage=0.97,
        flow_ledger=[{"from": "XLE", "to": "XLK", "amount": 0.02}],
    )

    assert bluf["conclusions"][0].startswith("Regime: risk-on")
    assert any("Largest sector money move: XLE to XLK." == c for c in bluf["conclusions"])
    assert bluf["actions"][0] == "Review KO: EXIT."
    assert all(a.split()[0] in {"Review", "Hold", "Watch"} for a in bluf["actions"])
    assert len(bluf["actions"]) <= 3


def test_degraded_run_is_the_first_conclusion():
    bluf = build_bluf(
        rows=ROWS, sector_map=SECTOR_MAP, holdings=[], watchlist=[],
        risk_on=None, degraded=True, flow_coverage=0.0,
    )

    assert bluf["conclusions"][0] == "Data warning: degraded run, flow coverage 0%."
    assert bluf["degraded"] is True
