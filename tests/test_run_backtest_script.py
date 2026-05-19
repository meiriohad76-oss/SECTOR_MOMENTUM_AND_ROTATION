from __future__ import annotations

from scripts import run_backtest


def test_run_backtest_returns_manual_data_error_when_required_prices_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", lambda tickers, period: {})

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()


def test_run_backtest_returns_manual_data_error_when_fetch_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")

    def fail_fetch(tickers, period):
        raise RuntimeError("download failed")

    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fail_fetch)

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()


def test_run_backtest_fetches_required_smoke_tickers_only(monkeypatch, tmp_path, ohlcv_frame_factory):
    calls = []

    def fake_fetch(tickers, period):
        calls.append((tickers, period))
        return {
            "AGG": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0002),
            "SPY": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.001),
        }

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 0
    assert calls == [(["AGG", "SPY"], "max")]
    assert run_backtest.REPORT_PATH.exists()


def test_run_backtest_returns_manual_data_error_when_prices_are_too_short(
    monkeypatch,
    tmp_path,
    ohlcv_frame_factory,
):
    calls = []

    def fake_fetch(tickers, period):
        calls.append((tickers, period))
        return {
            "AGG": ohlcv_frame_factory(days=1, start_price=100.0, daily_return=0.0002),
            "SPY": ohlcv_frame_factory(days=1, start_price=100.0, daily_return=0.001),
        }

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 2
    assert calls == [(["AGG", "SPY"], "max")]
    assert not run_backtest.REPORT_PATH.exists()
