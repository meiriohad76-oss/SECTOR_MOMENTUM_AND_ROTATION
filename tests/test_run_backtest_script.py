from __future__ import annotations

import json

import pandas as pd
import pytest

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
    gate_calls = []
    split_calls = []

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
        rebalance_dates = pd.DatetimeIndex(rebalance_dates)
        xlk_states = ["HOLD"] * len(rebalance_dates)
        xlf_states = ["EXIT"] * len(rebalance_dates)
        if len(rebalance_dates) > 1:
            xlk_states[-1] = "WARNING"
            xlf_states[1:] = ["HOLD"] * (len(rebalance_dates) - 1)
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
            states=pd.DataFrame({"XLK": xlk_states, "XLF": xlf_states}, index=rebalance_dates),
            snapshots={},
        )

    def fake_evaluate_acceptance_gates(strategy_metrics, equal_weight_metrics, **kwargs):
        gate_calls.append(
            {
                "strategy_metrics": dict(strategy_metrics),
                "equal_weight_metrics": dict(equal_weight_metrics),
                "kwargs": kwargs,
            }
        )
        return {
            "oos_sharpe": {
                "name": "Out-of-sample Sharpe",
                "value": strategy_metrics["sharpe"],
                "threshold": 0.7,
                "passed": True,
            },
            "max_drawdown": {
                "name": "Max drawdown",
                "value": abs(strategy_metrics["max_drawdown"]),
                "threshold": abs(equal_weight_metrics["max_drawdown"]) * 0.75,
                "passed": True,
            },
            "all_passed": True,
        }

    def metric(total_return, sharpe, max_drawdown):
        return {
            "total_return": total_return,
            "cagr": total_return,
            "sharpe": sharpe,
            "sortino": sharpe,
            "max_drawdown": max_drawdown,
            "calmar": 1.0,
            "annualized_turnover": 0.5,
        }

    split_results = [
        {
            "Full period": metric(0.10, 1.10, -0.10),
            "In-sample": metric(0.05, 0.55, -0.08),
            "Out-of-sample": metric(0.03, 7.77, -0.06),
        },
        {
            "Full period": metric(0.08, 0.80, -0.09),
            "In-sample": metric(0.03, 0.30, -0.07),
            "Out-of-sample": metric(0.02, 0.22, -0.05),
        },
        {
            "Full period": metric(0.09, 0.90, -0.20),
            "In-sample": metric(0.04, 0.40, -0.12),
            "Out-of-sample": metric(0.01, 0.11, -0.44),
        },
    ]

    def fake_split_backtest_metrics(result):
        split_calls.append(result)
        return split_results[len(split_calls) - 1]

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
    monkeypatch.setattr(
        run_backtest.backtest,
        "evaluate_acceptance_gates",
        fake_evaluate_acceptance_gates,
    )
    monkeypatch.setattr(
        run_backtest.backtest,
        "split_backtest_metrics",
        fake_split_backtest_metrics,
    )

    assert run_backtest.main() == 0
    assert calls == [(expected_tickers, "max", "auto")]
    assert target_builder_calls
    assert target_builder_calls[0]["tickers"] == expected_tickers
    assert target_builder_calls[0]["phase"] == "MID"
    assert gate_calls
    assert len(split_calls) == 3
    assert gate_calls[0]["strategy_metrics"]["sharpe"] == pytest.approx(7.77)
    assert gate_calls[0]["strategy_metrics"]["state_transitions_per_ticker_year"] > 0.0
    assert gate_calls[0]["equal_weight_metrics"]["max_drawdown"] == pytest.approx(-0.44)
    assert run_backtest.REPORT_PATH.exists()
    report = run_backtest.REPORT_PATH.read_text(encoding="utf-8")
    assert "Methodology" in report
    assert "## Benchmark Comparison" in report
    assert "60/40 SPY/AGG" in report
    assert "Equal-weight sectors" in report
    assert "## Cost Sensitivity" in report
    assert "## Historical Methodology Simulation" in report
    assert "State transitions per ticker-year" in report
    assert "## In-Sample / Out-of-Sample" in report
    assert "Out-of-sample" in report
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
    assert metadata["simulation_summary"]["state_transition_count"] == 2
    assert metadata["simulation_summary"]["state_transitions_per_ticker_year"] > 0.0
    assert "Methodology" in metadata["equity_columns"]


def test_run_backtest_live_smoke_fetches_short_period_without_artifacts(
    monkeypatch,
    tmp_path,
    capsys,
    ohlcv_frame_factory,
):
    calls = []

    def fake_fetch(tickers, period, provider):
        calls.append((list(tickers), period, provider))
        return {
            ticker: ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0005)
            for ticker in tickers
        }

    def fail_target_builder(*args, **kwargs):
        raise AssertionError("live smoke should not run the expensive historical target builder")

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(
        run_backtest.backtest,
        "build_historical_methodology_targets",
        fail_target_builder,
    )

    assert run_backtest.main(["--live-smoke"]) == 0

    assert calls == [(run_backtest.REQUIRED_TICKERS, "2mo", "auto")]
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.METADATA_PATH.exists()
    output = capsys.readouterr().out
    assert "Live backtest smoke passed" in output
    assert "14 tickers" in output


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
