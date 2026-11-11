from src.api_dashboard_snapshot import _top_rows
from src.bluf import leading_sectors


def _row(ticker, s_score, after_veto=None, state="STAGE_2_BULLISH", quadrant="Leading"):
    payload = {} if after_veto is None else {"S_score_after_veto": after_veto}
    return {
        "ticker": ticker,
        "s_score": s_score,
        "asset_class": "US Sectors",
        "quadrant": quadrant,
        "state": state,
        "payload": payload,
    }


def test_top_rows_puts_vetoed_sector_below_unvetoed_sectors():
    rows = [
        _row("XLE", 0.66, after_veto=-9.99),
        _row("XLB", 0.82, after_veto=0.82),
        _row("XLV", 0.41, after_veto=0.41),
    ]
    top = [r["ticker"] for r in _top_rows(rows, reverse=True, limit=3)]
    assert top == ["XLB", "XLV", "XLE"]


def test_top_rows_falls_back_to_raw_score_without_payload():
    rows = [{"ticker": "A", "s_score": 0.1}, {"ticker": "B", "s_score": 0.5}]
    assert [r["ticker"] for r in _top_rows(rows, reverse=True)] == ["B", "A"]


def test_leading_sectors_do_not_lead_with_a_vetoed_sector():
    rows = [
        _row("XLE", 0.66, after_veto=-9.99),
        _row("XLB", 0.82, after_veto=0.82),
    ]
    tickers = [r["ticker"] for r in leading_sectors(rows)]
    assert tickers[0] == "XLB"
