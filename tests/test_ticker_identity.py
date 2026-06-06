from src.ticker_identity import ticker_display_label, ticker_display_name


def test_ticker_identity_names_cover_core_universe_examples():
    assert ticker_display_name("XLK") == "Technology sector"
    assert ticker_display_label("XLK") == "XLK | Technology sector"
    assert ticker_display_label("EWJ") == "EWJ | Japan"
    assert ticker_display_label("MTUM") == "MTUM | Momentum factor"
    assert ticker_display_label("ARKK") == "ARKK | Innovation theme"
    assert ticker_display_label("NVDA") == "NVDA | NVIDIA"


def test_unknown_ticker_identity_falls_back_to_ticker():
    assert ticker_display_name("ABCX") == "ABCX"
    assert ticker_display_label("ABCX") == "ABCX"
