from __future__ import annotations

from src.browser_qa_data import browser_qa_ohlcv_result


def test_browser_qa_ohlcv_result_returns_complete_secret_free_fixture():
    result = browser_qa_ohlcv_result(["SPY", "BIL", "XLK"], period="3y")

    assert result.provider == "browser_qa_fixture"
    assert result.fetched == ()
    assert result.missing == ()
    assert result.warnings == ()
    assert list(result.data) == ["SPY", "BIL", "XLK"]
    assert len(result.data["SPY"]) >= 700
    assert set(result.data["XLK"].columns) == {"open", "high", "low", "close", "volume", "adj_close"}
    assert result.data["XLK"]["close"].iloc[-1] > result.data["XLK"]["close"].iloc[0]
    assert "secret" not in repr(result).lower()
    assert "token" not in repr(result).lower()
