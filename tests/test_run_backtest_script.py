from __future__ import annotations

import json

import pandas as pd

from src import backtest
from scripts import run_backtest


def test_run_backtest_artifact_paths_are_repo_root_anchored():
    assert run_backtest.REPORT_PATH == run_backtest.ROOT / "docs" / "backtest_report.md"
    assert run_backtest.EQUITY_PATH == run_backtest.ROOT / "docs" / "backtest_equity.csv"
    assert run_backtest.METADATA_PATH == run_backtest.ROOT / "docs" / "backtest_metadata.json"


def test_run_backtest_returns_manual_data_error_when_required_prices_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", lambda tickers, period, provider: {})

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.METADATA_PATH.exists()


def test_run_backtest_returns_manual_data_error_when_fetch_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)

    def fail_fetch(tickers, period, provider):
        raise RuntimeError("download failed")

    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fail_fetch)

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.METADATA_PATH.exists()


def test_run_backtest_fetches_benchmarks_and_writes_rich_report(monkeypatch, tmp_path, ohlcv_frame_factory):
    calls = []
    expected_tickers = [
        "AGG",
        "BIL",
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
    target_builder_calls = []

    def fake_fetch(tickers, period, provider):
        calls.append((tickers, period, provider))
        return {
            "AGG": ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0002),
            "BIL": ohlcv_frame_factory(days=40, start_price=90.0, daily_return=0.0001),
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

    def fake_build_historical_methodology_targets(ohlcv, rebalance_dates, phase):
        target_builder_calls.append(
            {
                "tickers": sorted(ohlcv),
                "rebalance_dates": list(rebalance_dates),
                "phase": phase,
            }
        )
        weights = pd.DataFrame({"XLK": [1.0] * len(rebalance_dates)}, index=rebalance_dates)
        return backtest.HistoricalSignalTargets(
            target_weights=weights,
            states=pd.DataFrame(index=rebalance_dates),
            snapshots={},
        )

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(
        run_backtest.backtest,
        "build_historical_methodology_targets",
        fake_build_historical_methodology_targets,
    )

    assert run_backtest.main() == 0
    assert calls == [(expected_tickers, "max", "auto")]
    assert target_builder_calls
    assert target_builder_calls[0]["tickers"] == expected_tickers
    assert target_builder_calls[0]["phase"] == "MID"
    assert run_backtest.REPORT_PATH.exists()
    report = run_backtest.REPORT_PATH.read_text(encoding="utf-8")
    assert "Methodology" in report
    assert "## Benchmark Comparison" in report
    assert "60/40 SPY/AGG" in report
    assert "Equal-weight sectors" in report
    assert "## Cost Sensitivity" in report
    assert run_backtest.EQUITY_PATH.exists()
    equity = run_backtest.EQUITY_PATH.read_text(encoding="utf-8")
    assert "Methodology" in equity
    assert "60/40 SPY/AGG" in equity
    assert "Equal-weight sectors" in equity
    assert run_backtest.METADATA_PATH.exists()
    metadata = json.loads(run_backtest.METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["report_sha256"] == run_backtest._sha256_bytes(run_backtest.REPORT_PATH.read_bytes())
    assert metadata["equity_sha256"] == run_backtest._sha256_bytes(run_backtest.EQUITY_PATH.read_bytes())
    assert metadata["required_tickers"] == expected_tickers
    assert "Methodology" in metadata["equity_columns"]


def test_run_backtest_returns_manual_data_error_when_prices_are_too_short(
    monkeypatch,
    tmp_path,
    ohlcv_frame_factory,
):
    calls = []
    expected_tickers = [
        "AGG",
        "BIL",
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

    def fake_fetch(tickers, period, provider):
        calls.append((tickers, period, provider))
        return {
            "AGG": ohlcv_frame_factory(days=1, start_price=100.0, daily_return=0.0002),
            "SPY": ohlcv_frame_factory(days=1, start_price=100.0, daily_return=0.001),
        }

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 2
    assert calls == [(expected_tickers, "max", "auto")]
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.METADATA_PATH.exists()


def test_run_backtest_honors_configured_ohlcv_provider(monkeypatch, tmp_path):
    calls = []

    def fake_fetch(tickers, period, provider):
        calls.append(provider)
        return {}

    monkeypatch.setenv("OHLCV_PROVIDER", "massive")
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 2
    assert calls == ["massive"]
