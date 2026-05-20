from __future__ import annotations

from scripts import run_backtest


def test_run_backtest_returns_manual_data_error_when_required_prices_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", lambda tickers, period: {})

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()


def test_run_backtest_returns_manual_data_error_when_fetch_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")

    def fail_fetch(tickers, period):
        raise RuntimeError("download failed")

    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fail_fetch)

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()


def test_run_backtest_fetches_benchmarks_and_writes_rich_report(monkeypatch, tmp_path, ohlcv_frame_factory):
    calls = []
    expected_tickers = [
        "AGG",
        "SPY",
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLRE",
        "XLU",
        "XLV",
        "XLY",
    ]

    def fake_fetch(tickers, period):
        calls.append((tickers, period))
        return {
            "AGG": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0002),
            "SPY": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.001),
            "XLB": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0004),
            "XLC": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0005),
            "XLE": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0006),
            "XLF": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0007),
            "XLI": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0008),
            "XLK": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0009),
            "XLP": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0003),
            "XLRE": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0002),
            "XLU": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0001),
            "XLV": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0005),
            "XLY": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0006),
        }

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 0
    assert calls == [(expected_tickers, "max")]
    assert run_backtest.REPORT_PATH.exists()
    report = run_backtest.REPORT_PATH.read_text(encoding="utf-8")
    assert "## Benchmark Comparison" in report
    assert "60/40 SPY/AGG" in report
    assert "Equal-weight sectors" in report
    assert "## Cost Sensitivity" in report
    assert run_backtest.EQUITY_PATH.exists()
    equity = run_backtest.EQUITY_PATH.read_text(encoding="utf-8")
    assert "60/40 SPY/AGG" in equity
    assert "Equal-weight sectors" in equity


def test_run_backtest_returns_manual_data_error_when_prices_are_too_short(
    monkeypatch,
    tmp_path,
    ohlcv_frame_factory,
):
    calls = []
    expected_tickers = [
        "AGG",
        "SPY",
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLRE",
        "XLU",
        "XLV",
        "XLY",
    ]

    def fake_fetch(tickers, period):
        calls.append((tickers, period))
        return {
            "AGG": ohlcv_frame_factory(days=1, start_price=100.0, daily_return=0.0002),
            "SPY": ohlcv_frame_factory(days=1, start_price=100.0, daily_return=0.001),
        }

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 2
    assert calls == [(expected_tickers, "max")]
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
