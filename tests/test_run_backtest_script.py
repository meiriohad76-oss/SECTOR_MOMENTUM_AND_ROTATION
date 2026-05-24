from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from src import backtest
from src import provider_snapshots
from scripts import run_backtest


def test_run_backtest_artifact_paths_are_repo_root_anchored():
    assert run_backtest.REPORT_PATH == run_backtest.ROOT / "docs" / "backtest_report.md"
    assert run_backtest.METHODOLOGY_REPORT_PATH == run_backtest.ROOT / "docs" / "backtest_methodology_report.md"
    assert run_backtest.EQUITY_PATH == run_backtest.ROOT / "docs" / "backtest_equity.csv"
    assert run_backtest.STATES_PATH == run_backtest.ROOT / "docs" / "backtest_states.csv"
    assert run_backtest.METADATA_PATH == run_backtest.ROOT / "docs" / "backtest_metadata.json"
    assert run_backtest._calibration_baseline_config_path() == (
        run_backtest.ROOT / "docs" / "calibration_10y_baseline_config.json"
    )
    assert run_backtest.CALIBRATION_REPORT_PATH == (
        run_backtest.ROOT / "docs" / "calibration_10y_report.md"
    )
    assert run_backtest.CALIBRATION_SUMMARY_PATH == (
        run_backtest.ROOT / "docs" / "calibration_10y_summary.csv"
    )
    assert run_backtest.CALIBRATION_METADATA_PATH == (
        run_backtest.ROOT / "docs" / "calibration_10y_metadata.json"
    )
    assert run_backtest.FRED_VALIDATION_REPORT_PATH == (
        run_backtest.ROOT / "docs" / "fred_macro_validation_report.md"
    )
    assert run_backtest.FRED_VALIDATION_SUMMARY_PATH == (
        run_backtest.ROOT / "docs" / "fred_macro_validation_summary.csv"
    )
    assert run_backtest.MASSIVE_VALIDATION_REPORT_PATH == (
        run_backtest.ROOT / "docs" / "massive_provider_validation_report.md"
    )
    assert run_backtest.MASSIVE_VALIDATION_SUMMARY_PATH == (
        run_backtest.ROOT / "docs" / "massive_provider_validation_summary.csv"
    )


def test_static_calibration_baseline_config_matches_current_runner_baseline():
    expected = backtest.frozen_baseline_config(
        universe=run_backtest.REQUIRED_TICKERS,
        benchmark_tickers=["AGG", "SPY", *run_backtest.SECTOR_BENCHMARK_TICKERS],
        ohlcv_provider="auto",
        transaction_cost_bps=5.0,
        phase="MID",
    )

    artifact = json.loads(run_backtest._calibration_baseline_config_path().read_text(encoding="utf-8"))

    assert artifact == expected


def test_run_backtest_parser_exposes_macro_variants_flag():
    args = run_backtest._parser().parse_args(["--macro-variants"])

    assert args.macro_variants is True


def test_run_backtest_parser_exposes_massive_variants_flag():
    args = run_backtest._parser().parse_args(["--massive-variants"])

    assert args.massive_variants is True


def test_build_calibration_baseline_artifacts_summarizes_directional_metrics(monkeypatch):
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(["2020-01-03", "2020-01-10"]),
            "ticker": ["XLK", "XLF"],
            "class": ["sector", "sector"],
        }
    )
    metric_calls = []

    def fake_build_labels(targets, prices, horizons_weeks):
        assert targets == "targets"
        assert prices.equals(pd.DataFrame({"XLK": [100.0]}))
        assert horizons_weeks == run_backtest.CALIBRATION_HORIZONS_WEEKS
        return labels

    def fake_metrics(label_frame, horizons_weeks, group_by=None):
        metric_calls.append({"horizons": horizons_weeks, "group_by": group_by})
        assert label_frame is labels
        base = {
            "horizon_weeks": 4,
            "total_count": 2,
            "available_count": 2,
            "signal_count": 1,
            "signal_available_count": 1,
            "success_count": 1,
            "failure_count": 0,
            "hit_rate": 1.0,
            "precision": 1.0,
            "recall": 0.5,
            "f1": 2 / 3,
            "average_forward_return": 0.04,
            "average_forward_excess_return": 0.02,
            "average_post_entry_drawdown": -0.01,
            "average_drawdown_avoided": 0.0,
        }
        if group_by == "class":
            return pd.DataFrame([{**base, "class": "sector", "direction": "positive"}])
        return pd.DataFrame(
            [
                {**base, "direction": "positive"},
                {
                    **base,
                    "direction": "negative",
                    "hit_rate": 0.0,
                    "success_count": 0,
                    "failure_count": 1,
                    "average_drawdown_avoided": 0.03,
                },
            ]
        )

    monkeypatch.setattr(run_backtest.backtest, "build_calibration_feature_labels", fake_build_labels)
    monkeypatch.setattr(run_backtest.backtest, "calibration_label_metrics", fake_metrics)

    summary, report, metadata = run_backtest._build_calibration_baseline_artifacts(
        targets="targets",
        prices=pd.DataFrame({"XLK": [100.0]}),
        baseline_config={"ticket": "B-163"},
        calibration_split_summary={"status": "ready", "fold_count": 3},
        ohlcv_source={"provider": "yfinance"},
    )

    assert metric_calls == [
        {"horizons": run_backtest.CALIBRATION_HORIZONS_WEEKS, "group_by": None},
        {"horizons": run_backtest.CALIBRATION_HORIZONS_WEEKS, "group_by": "class"},
    ]
    assert summary["scope"].tolist() == ["overall", "overall", "class"]
    assert summary["direction"].tolist() == ["positive", "negative", "positive"]
    assert summary.loc[0, "hit_rate"] == pytest.approx(1.0)
    assert "Positive momentum hit rate" in report
    assert "Negative momentum hit rate" in report
    assert report.index("Positive momentum hit rate") < report.index("Negative momentum hit rate")
    assert "research-only" in report
    assert metadata["ticket"] == "B-163"
    assert metadata["slice"] == "B-163.5"
    assert metadata["research_only"] is True
    assert metadata["live_promotion_allowed"] is False
    assert metadata["label_rows"] == 2
    assert metadata["summary_rows"] == 3
    assert metadata["horizons_weeks"] == list(run_backtest.CALIBRATION_HORIZONS_WEEKS)
    assert metadata["calibration_split_summary"]["status"] == "ready"
    assert metadata["ohlcv_source"]["provider"] == "yfinance"


def test_build_massive_provider_validation_summary_compares_default_and_massive_without_cache(
    monkeypatch,
    ohlcv_frame_factory,
):
    calls = []

    def fake_fetch_ohlcv_result(tickers, period, provider, use_cache=True):
        calls.append(
            {
                "tickers": list(tickers),
                "period": period,
                "provider": provider,
                "use_cache": use_cache,
            }
        )
        daily_return = 0.0012 if provider == "massive" else 0.0008
        return SimpleNamespace(
            data={
                ticker: ohlcv_frame_factory(days=80, start_price=100.0, daily_return=daily_return)
                for ticker in tickers
            },
            provider=provider,
            fetched=tuple(tickers),
            fresh_cache_hits=(),
            stale_cache_hits=(),
            missing=(),
            warnings=(),
            used_stale_cache=False,
        )

    def fake_build_historical_methodology_targets(ohlcv, rebalance_dates, phase):
        del ohlcv, phase
        rebalance_dates = pd.DatetimeIndex(rebalance_dates)
        weights = pd.DataFrame({"XLK": [1.0] * len(rebalance_dates)}, index=rebalance_dates)
        return backtest.HistoricalSignalTargets(
            target_weights=weights,
            states=pd.DataFrame({"XLK": ["HOLD"] * len(rebalance_dates)}, index=rebalance_dates),
            snapshots={},
        )

    monkeypatch.setattr(run_backtest, "fetch_ohlcv_result", fake_fetch_ohlcv_result)
    monkeypatch.setattr(
        run_backtest.backtest,
        "build_historical_methodology_targets",
        fake_build_historical_methodology_targets,
    )

    summary = run_backtest._build_massive_provider_validation_summary(
        enabled=True,
        oos_start="2020-02-03",
    )

    provider_rows = summary[summary["row_type"] == "provider_comparison"].reset_index(drop=True)
    feature_rows = summary[summary["row_type"] == "provider_feature_sweep"].reset_index(drop=True)
    assert provider_rows["provider"].tolist() == ["yfinance", "massive"]
    assert provider_rows["ticker_count"].tolist() == [14, 14]
    assert provider_rows["coverage_start"].tolist() == ["2020-01-01", "2020-01-01"]
    assert provider_rows.loc[1, "oos_sharpe_delta_vs_yfinance"] >= 0.0
    assert provider_rows.loc[1, "endpoint"] == "https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}"
    assert set(feature_rows["threshold"].dropna().astype(float).tolist()) == {1.0, 1.25, 1.5}
    assert set(feature_rows["promotion_label"].tolist()) == {"do not promote"}
    assert all(feature_rows["status"].str.contains("unavailable_no_historical_asof_snapshots"))
    assert calls == [
        {
            "tickers": run_backtest.REQUIRED_TICKERS,
            "period": "max",
            "provider": "yfinance",
            "use_cache": False,
        },
        {
            "tickers": run_backtest.REQUIRED_TICKERS,
            "period": "max",
            "provider": "massive",
            "use_cache": False,
        },
    ]


def test_build_massive_provider_validation_summary_reuses_precomputed_massive_row(monkeypatch):
    calls = []

    def fake_fetch_ohlcv_result(tickers, period, provider, use_cache=True):
        calls.append(provider)
        return SimpleNamespace(
            data={},
            provider=provider,
            fetched=(),
            fresh_cache_hits=(),
            stale_cache_hits=(),
            missing=tuple(tickers),
            warnings=(),
            used_stale_cache=False,
        )

    precomputed_massive = {
        "row_type": "provider_comparison",
        "variant": "Massive aggregate OHLCV",
        "provider": "massive",
        "endpoint": "https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}",
        "status": "available",
        "coverage_start": "2020-01-01",
        "coverage_end": "2020-04-21",
        "coverage_rows": 80,
        "ticker_count": 14,
        "missing_count": 0,
        "missing_tickers": "",
        "coverage_by_ticker": "XLK:2020-01-01->2020-04-21(80)",
        "cagr": 0.12,
        "sharpe": 1.1,
        "max_drawdown": -0.02,
        "annualized_turnover": 0.5,
        "oos_cagr": 0.10,
        "oos_sharpe": 0.9,
        "oos_max_drawdown": -0.02,
        "oos_annualized_turnover": 0.5,
        "promotion_label": "needs more testing",
        "notes": "reused main Massive validation run",
    }

    monkeypatch.setattr(run_backtest, "fetch_ohlcv_result", fake_fetch_ohlcv_result)

    summary = run_backtest._build_massive_provider_validation_summary(
        enabled=True,
        oos_start="2020-02-03",
        precomputed_provider_rows=[precomputed_massive],
    )

    provider_rows = summary[summary["row_type"] == "provider_comparison"].reset_index(drop=True)
    assert provider_rows["provider"].tolist() == ["yfinance", "massive"]
    assert str(provider_rows.loc[1, "notes"]).startswith("reused main Massive validation run")
    assert calls == ["yfinance"]


def test_massive_provider_flow_sweeps_replay_snapshots_as_of_rebalance(tmp_path, monkeypatch):
    db_path = tmp_path / "provider_snapshots.sqlite"
    provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-18",
        payload={
            "trades": [
                {"p": 100.0, "s": 100, "sip_timestamp": 1, "correction": 0},
                {"p": 99.0, "s": 3_000, "sip_timestamp": 2, "correction": 0},
            ]
        },
        captured_at_utc="2026-05-18T21:00:00Z",
    )
    provider_snapshots.upsert_provider_snapshot(
        db_path,
        provider="massive",
        dataset="stock_trades",
        ticker="XLK",
        as_of="2026-05-20",
        payload={
            "trades": [
                {"p": 100.0, "s": 100, "sip_timestamp": 1, "correction": 0},
                {"p": 101.0, "s": 3_000, "sip_timestamp": 2, "correction": 0},
            ]
        },
        captured_at_utc="2026-05-20T21:00:00Z",
    )
    prices = pd.DataFrame(
        {
            "XLK": [100.0, 101.0, 99.0, 103.0],
            "XLF": [100.0, 100.5, 100.2, 100.8],
        },
        index=pd.bdate_range("2026-05-19", periods=4),
    )
    target_weights = pd.DataFrame(
        {"XLK": [0.5, 0.5], "XLF": [0.5, 0.5]},
        index=pd.to_datetime(["2026-05-19", "2026-05-21"]),
    )

    def fail_provider_fetch(*args, **kwargs):
        raise AssertionError("provider-flow replay must not call live provider fetches")

    monkeypatch.setattr(run_backtest, "fetch_ohlcv_result", fail_provider_fetch)

    rows = run_backtest._build_massive_provider_flow_sweep_rows(
        snapshot_db_path=db_path,
        prices=prices,
        target_weights=target_weights,
        oos_start="2026-05-20",
    )

    row = next(item for item in rows if item["threshold"] == pytest.approx(1.25))
    assert row["row_type"] == "provider_feature_sweep"
    assert row["status"] == "replayed_snapshots"
    assert row["snapshot_rebalance_count"] == 2
    assert row["snapshot_required_decisions"] == 4
    assert row["snapshot_available_count"] == 2
    assert row["snapshot_missing_count"] == 2
    assert row["snapshot_neutral_missing_count"] == 2
    assert row["snapshot_below_threshold_count"] == 1
    assert row["snapshot_passing_count"] == 1
    assert row["snapshot_coverage_pct"] == pytest.approx(0.5)
    assert row["active_rebalances"] == 2
    assert row["active_oos_rebalances"] == 1
    assert row["coverage_start"] == "2026-05-18"
    assert row["coverage_end"] == "2026-05-20"
    assert row["promotion_label"] == "needs more testing"
    assert "missing snapshots were neutral" in row["notes"]


def test_massive_provider_flow_counts_active_oos_as_unique_rebalance_dates(tmp_path):
    db_path = tmp_path / "provider_snapshots.sqlite"
    for ticker in ("XLK", "XLF"):
        provider_snapshots.upsert_provider_snapshot(
            db_path,
            provider="massive",
            dataset="stock_trades",
            ticker=ticker,
            as_of="2026-05-20",
            payload={
                "trades": [
                    {"p": 100.0, "s": 100, "sip_timestamp": 1, "correction": 0},
                    {"p": 101.0, "s": 3_000, "sip_timestamp": 2, "correction": 0},
                ]
            },
            captured_at_utc="2026-05-20T21:00:00Z",
        )
    prices = pd.DataFrame(
        {
            "XLK": [100.0, 101.0, 102.0],
            "XLF": [100.0, 100.5, 101.0],
        },
        index=pd.bdate_range("2026-05-20", periods=3),
    )
    target_weights = pd.DataFrame(
        {"XLK": [0.5], "XLF": [0.5]},
        index=[pd.Timestamp("2026-05-21")],
    )

    rows = run_backtest._build_massive_provider_flow_sweep_rows(
        snapshot_db_path=db_path,
        prices=prices,
        target_weights=target_weights,
        oos_start="2026-05-20",
    )

    row = next(item for item in rows if item["threshold"] == pytest.approx(1.25))
    assert row["snapshot_available_count"] == 2
    assert row["active_rebalances"] == 1
    assert row["active_oos_rebalances"] == 1


def test_massive_provider_flow_reports_all_missing_snapshots_as_neutral(tmp_path):
    prices = pd.DataFrame(
        {
            "XLK": [100.0, 101.0, 102.0, 103.0],
            "XLF": [100.0, 100.5, 101.0, 101.5],
        },
        index=pd.bdate_range("2026-05-19", periods=4),
    )
    target_weights = pd.DataFrame(
        {"XLK": [0.5, 0.5], "XLF": [0.5, 0.5]},
        index=pd.to_datetime(["2026-05-19", "2026-05-21"]),
    )

    rows = run_backtest._build_massive_provider_flow_sweep_rows(
        snapshot_db_path=tmp_path / "missing_provider_snapshots.sqlite",
        prices=prices,
        target_weights=target_weights,
        oos_start="2026-05-20",
    )

    row = next(item for item in rows if item["threshold"] == pytest.approx(1.25))
    assert row["status"] == "unavailable_no_historical_asof_snapshots"
    assert row["snapshot_rebalance_count"] == 2
    assert row["snapshot_required_decisions"] == 4
    assert row["snapshot_available_count"] == 0
    assert row["snapshot_missing_count"] == 4
    assert row["snapshot_neutral_missing_count"] == 4
    assert row["missing_tickers"] == "XLF, XLK"
    assert row["snapshot_coverage_pct"] == pytest.approx(0.0)
    assert row["promotion_label"] == "do not promote"
    assert "missing snapshots were neutral" in row["notes"]


def test_massive_provider_report_includes_snapshot_coverage_and_sweep_metrics():
    prices = pd.DataFrame({"XLK": [100.0, 101.0]}, index=pd.bdate_range("2026-05-19", periods=2))
    target_weights = pd.DataFrame({"XLK": [1.0]}, index=[pd.Timestamp("2026-05-19")])
    summary = pd.DataFrame(
        [
            {
                "row_type": "provider_comparison",
                "variant": "Default/yfinance OHLCV baseline",
                "provider": "yfinance",
                "endpoint": "yfinance.download",
                "status": "available",
                "coverage_start": "2026-05-19",
                "coverage_end": "2026-05-20",
                "coverage_rows": 2,
                "ticker_count": 1,
                "promotion_label": "needs more testing",
            },
            {
                "row_type": "provider_feature_sweep",
                "variant": "Block-trade upside ratio >= 1.25",
                "provider": "massive",
                "endpoint": "https://api.massive.com/v3/trades/{ticker}",
                "status": "replayed_snapshots",
                "threshold": 1.25,
                "coverage_start": "2026-05-18",
                "coverage_end": "2026-05-20",
                "snapshot_rebalance_count": 2,
                "snapshot_required_decisions": 4,
                "snapshot_available_count": 2,
                "snapshot_missing_count": 2,
                "snapshot_neutral_missing_count": 2,
                "snapshot_coverage_pct": 0.5,
                "active_oos_rebalances": 1,
                "oos_cagr_delta_vs_yfinance": -0.01,
                "oos_sharpe_delta_vs_yfinance": -0.10,
                "oos_max_drawdown_delta_vs_yfinance": 0.00,
                "promotion_label": "needs more testing",
                "notes": "Replayed stored as-of snapshots; missing snapshots were neutral.",
            },
        ]
    )

    report = run_backtest._format_massive_provider_validation_report(
        massive_validation_summary=summary,
        prices=prices,
        target_weights=target_weights,
        requested_provider="auto",
        resolved_provider="massive",
        generated_at_utc="2026-05-22T12:00:00Z",
        oos_start="2026-05-20",
    )

    assert "Ticket: B-159/B-162" in report
    assert "## Provider-Flow Snapshot Replay Coverage" in report
    assert "Snapshot Coverage" in report
    assert "Missing Neutral" in report
    assert "Active OOS" in report
    assert "50.00%" in report
    assert "missing snapshots were neutral" in report


def test_run_backtest_builds_macro_variant_summary_only_when_enabled(monkeypatch):
    calls = []
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0]}, index=pd.bdate_range("2024-01-01", periods=3))
    target_weights = pd.DataFrame({"AAA": [1.0]}, index=[prices.index[0]])
    macro_summary = pd.DataFrame(
        [{"variant": "Curve falling defensive", "series_id": "T10Y2Y", "condition": "falling"}]
    )

    def fake_fetch_fred(start_date):
        calls.append(start_date)
        return {"T10Y2Y": pd.Series([1.0, 0.5], index=prices.index[:2])}

    def fake_evaluate_macro_condition_variants(
        prices_arg,
        target_weights_arg,
        macro_data,
        rules,
        transaction_cost_bps,
        oos_start,
    ):
        assert prices_arg is prices
        assert target_weights_arg is target_weights
        assert "T10Y2Y" in macro_data
        assert rules == run_backtest.MACRO_VARIANT_RULES
        assert transaction_cost_bps == pytest.approx(5.0)
        assert oos_start == "2015-01-01"
        return macro_summary

    monkeypatch.setattr(run_backtest, "fetch_fred", fake_fetch_fred)
    monkeypatch.setattr(
        run_backtest.backtest,
        "evaluate_macro_condition_variants",
        fake_evaluate_macro_condition_variants,
    )

    disabled = run_backtest._build_macro_variant_summary(
        enabled=False,
        prices=prices,
        target_weights=target_weights,
    )
    enabled = run_backtest._build_macro_variant_summary(
        enabled=True,
        prices=prices,
        target_weights=target_weights,
    )

    assert disabled.empty
    assert enabled.equals(macro_summary)
    assert calls == ["2003-01-01"]


def test_validation_split_falls_back_when_default_oos_is_before_data():
    rebalances = pd.bdate_range("2018-01-05", periods=100)

    split_date, method = run_backtest._resolve_validation_split(
        rebalances,
        preferred_oos_start="2015-01-01",
    )

    assert split_date == rebalances[70]
    assert "walk-forward fallback" in method


def test_run_backtest_writes_macro_variant_summary_to_metadata(monkeypatch, tmp_path, ohlcv_frame_factory):
    macro_summary = pd.DataFrame(
        [
            {
                "variant": "Curve falling defensive",
                "series_id": "T10Y2Y",
                "condition": "falling",
                "active_rebalances": 2,
                "total_return_delta": 0.04,
                "sharpe_delta": 0.20,
                "max_drawdown_delta": 0.03,
            }
        ]
    )

    def fake_fetch(tickers, period, provider):
        return {
            ticker: ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0005)
            for ticker in tickers
        }

    def fake_build_historical_methodology_targets(ohlcv, rebalance_dates, phase):
        del ohlcv, phase
        rebalance_dates = pd.DatetimeIndex(rebalance_dates)
        weights = pd.DataFrame({"XLK": [1.0] * len(rebalance_dates)}, index=rebalance_dates)
        return backtest.HistoricalSignalTargets(
            target_weights=weights,
            states=pd.DataFrame({"XLK": ["HOLD"] * len(rebalance_dates)}, index=rebalance_dates),
            snapshots={},
        )

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.setattr(run_backtest, "FRED_VALIDATION_REPORT_PATH", tmp_path / "fred_macro_validation_report.md")
    monkeypatch.setattr(run_backtest, "FRED_VALIDATION_SUMMARY_PATH", tmp_path / "fred_macro_validation_summary.csv")
    monkeypatch.setattr(run_backtest, "CALIBRATION_REPORT_PATH", tmp_path / "calibration_10y_report.md")
    monkeypatch.setattr(run_backtest, "CALIBRATION_SUMMARY_PATH", tmp_path / "calibration_10y_summary.csv")
    monkeypatch.setattr(run_backtest, "CALIBRATION_METADATA_PATH", tmp_path / "calibration_10y_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(
        run_backtest,
        "fetch_ohlcv_result",
        lambda tickers, period, provider, use_cache=True: SimpleNamespace(
            data=fake_fetch(tickers, period, provider),
            provider="massive",
            fetched=tuple(tickers),
            fresh_cache_hits=(),
            stale_cache_hits=(),
            missing=(),
            warnings=(),
            used_stale_cache=False,
        ),
    )
    monkeypatch.setattr(
        run_backtest.backtest,
        "build_historical_methodology_targets",
        fake_build_historical_methodology_targets,
    )
    monkeypatch.setattr(run_backtest, "_fetch_macro_data", lambda enabled: {"T10Y2Y": pd.Series([1.0, 0.5])})
    monkeypatch.setattr(run_backtest, "_build_macro_variant_summary", lambda **kwargs: macro_summary)

    assert run_backtest.main(["--macro-variants"]) == 0

    report = run_backtest.REPORT_PATH.read_text(encoding="utf-8")
    metadata = json.loads(run_backtest.METADATA_PATH.read_text(encoding="utf-8"))
    assert "## Macro Condition Variants" in report
    assert metadata["macro_variant_summary"][0]["variant"] == "Curve falling defensive"
    assert metadata["macro_variant_summary"][0]["total_return_delta"] == pytest.approx(0.04)


def test_run_backtest_writes_fred_validation_report_when_macro_variants_enabled(
    monkeypatch,
    tmp_path,
    ohlcv_frame_factory,
):
    macro_summary = pd.DataFrame(
        [
            {
                "variant": "Curve falling defensive",
                "series_id": "T10Y2Y",
                "condition": "falling",
                "active_rebalances": 24,
                "active_oos_rebalances": 12,
                "baseline_total_return": 0.40,
                "variant_total_return": 0.44,
                "total_return_delta": 0.04,
                "baseline_cagr": 0.08,
                "variant_cagr": 0.09,
                "cagr_delta": 0.01,
                "baseline_sharpe": 0.70,
                "variant_sharpe": 0.81,
                "sharpe_delta": 0.11,
                "baseline_max_drawdown": -0.20,
                "variant_max_drawdown": -0.18,
                "max_drawdown_delta": 0.02,
                "baseline_annualized_turnover": 1.2,
                "variant_annualized_turnover": 1.1,
                "annualized_turnover_delta": -0.1,
                "baseline_hit_rate": 0.51,
                "variant_hit_rate": 0.53,
                "hit_rate_delta": 0.02,
                "baseline_trade_count": 30,
                "variant_trade_count": 28,
                "trade_count_delta": -2,
                "oos_baseline_cagr": 0.07,
                "oos_variant_cagr": 0.08,
                "oos_cagr_delta": 0.01,
                "oos_baseline_sharpe": 0.65,
                "oos_variant_sharpe": 0.78,
                "oos_sharpe_delta": 0.13,
                "oos_baseline_max_drawdown": -0.19,
                "oos_variant_max_drawdown": -0.16,
                "oos_max_drawdown_delta": 0.03,
                "oos_baseline_annualized_turnover": 1.3,
                "oos_variant_annualized_turnover": 1.0,
                "oos_annualized_turnover_delta": -0.3,
                "promotion_label": "needs more testing",
            }
        ]
    )

    def fake_fetch(tickers, period, provider):
        return {
            ticker: ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0005)
            for ticker in tickers
        }

    def fake_build_historical_methodology_targets(ohlcv, rebalance_dates, phase):
        del ohlcv, phase
        rebalance_dates = pd.DatetimeIndex(rebalance_dates)
        weights = pd.DataFrame({"XLK": [1.0] * len(rebalance_dates)}, index=rebalance_dates)
        return backtest.HistoricalSignalTargets(
            target_weights=weights,
            states=pd.DataFrame({"XLK": ["HOLD"] * len(rebalance_dates)}, index=rebalance_dates),
            snapshots={},
        )

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.setattr(run_backtest, "FRED_VALIDATION_REPORT_PATH", tmp_path / "fred_macro_validation_report.md")
    monkeypatch.setattr(run_backtest, "FRED_VALIDATION_SUMMARY_PATH", tmp_path / "fred_macro_validation_summary.csv")
    monkeypatch.setattr(run_backtest, "CALIBRATION_REPORT_PATH", tmp_path / "calibration_10y_report.md")
    monkeypatch.setattr(run_backtest, "CALIBRATION_SUMMARY_PATH", tmp_path / "calibration_10y_summary.csv")
    monkeypatch.setattr(run_backtest, "CALIBRATION_METADATA_PATH", tmp_path / "calibration_10y_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(
        run_backtest,
        "fetch_ohlcv_result",
        lambda tickers, period, provider, use_cache=True: SimpleNamespace(
            data=fake_fetch(tickers, period, provider),
            provider="massive",
            fetched=tuple(tickers),
            fresh_cache_hits=(),
            stale_cache_hits=(),
            missing=(),
            warnings=(),
            used_stale_cache=False,
        ),
    )
    monkeypatch.setattr(run_backtest, "_resolved_provider", lambda provider: "massive")
    monkeypatch.setattr(run_backtest, "_fred_config_status", lambda macro_data: "configured")
    monkeypatch.setattr(
        run_backtest.backtest,
        "build_historical_methodology_targets",
        fake_build_historical_methodology_targets,
    )
    monkeypatch.setattr(run_backtest, "_fetch_macro_data", lambda enabled: {"T10Y2Y": pd.Series([1.0, 0.5])})
    monkeypatch.setattr(run_backtest, "_build_macro_variant_summary", lambda **kwargs: macro_summary)

    assert run_backtest.main(["--macro-variants"]) == 0

    validation_report = run_backtest.FRED_VALIDATION_REPORT_PATH.read_text(encoding="utf-8")
    validation_summary = pd.read_csv(run_backtest.FRED_VALIDATION_SUMMARY_PATH)
    metadata = json.loads(run_backtest.METADATA_PATH.read_text(encoding="utf-8"))
    assert "# FRED Macro Historical Validation Report" in validation_report
    assert "Requested OHLCV provider: auto" in validation_report
    assert "Resolved OHLCV provider: massive" in validation_report
    assert "FRED status: configured" in validation_report
    assert "Cache policy: bypassed for B-157 validation" in validation_report
    assert "Fetched tickers: 14" in validation_report
    assert "Curve falling defensive" in validation_report
    assert "needs more testing" in validation_report
    assert "No FRED macro rule is promoted into live scoring" in validation_report
    assert validation_summary.loc[0, "promotion_label"] == "needs more testing"
    assert metadata["fred_validation_report_sha256"] == run_backtest._sha256_bytes(
        run_backtest.FRED_VALIDATION_REPORT_PATH.read_bytes()
    )
    assert metadata["ohlcv_source"]["cache_policy"] == "bypassed"
    assert metadata["ohlcv_source"]["fetched_count"] == 14


def test_run_backtest_writes_massive_validation_report_when_massive_variants_enabled(
    monkeypatch,
    tmp_path,
    ohlcv_frame_factory,
):
    fetch_calls = []
    massive_summary = pd.DataFrame(
        [
            {
                "row_type": "provider_comparison",
                "variant": "Default/yfinance OHLCV baseline",
                "provider": "yfinance",
                "endpoint": "yfinance.download",
                "status": "available",
                "coverage_start": "2020-01-01",
                "coverage_end": "2020-02-25",
                "coverage_rows": 40,
                "ticker_count": 14,
                "missing_count": 0,
                "oos_cagr": 0.10,
                "oos_sharpe": 0.80,
                "oos_max_drawdown": -0.03,
                "oos_cagr_delta_vs_yfinance": 0.0,
                "oos_sharpe_delta_vs_yfinance": 0.0,
                "oos_max_drawdown_delta_vs_yfinance": 0.0,
                "promotion_label": "needs more testing",
                "notes": "baseline comparison row",
            },
            {
                "row_type": "provider_comparison",
                "variant": "Massive aggregate OHLCV",
                "provider": "massive",
                "endpoint": "https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}",
                "status": "available",
                "coverage_start": "2020-01-01",
                "coverage_end": "2020-02-25",
                "coverage_rows": 40,
                "ticker_count": 14,
                "missing_count": 0,
                "oos_cagr": 0.11,
                "oos_sharpe": 0.90,
                "oos_max_drawdown": -0.02,
                "oos_cagr_delta_vs_yfinance": 0.01,
                "oos_sharpe_delta_vs_yfinance": 0.10,
                "oos_max_drawdown_delta_vs_yfinance": 0.01,
                "promotion_label": "needs more testing",
                "notes": "provider source evidence only",
            },
            {
                "row_type": "provider_feature_sweep",
                "variant": "Block-trade upside ratio >= 1.25",
                "provider": "massive",
                "endpoint": "https://api.massive.com/v3/trades/{ticker}",
                "status": "unavailable_no_historical_asof_snapshots",
                "threshold": 1.25,
                "promotion_label": "do not promote",
                "notes": "current trade-tape endpoint is not a historical as-of signal source",
            },
        ]
    )

    def fake_fetch_result(tickers, period, provider, use_cache=True):
        fetch_calls.append(
            {
                "tickers": list(tickers),
                "period": period,
                "provider": provider,
                "use_cache": use_cache,
            }
        )
        return SimpleNamespace(
            data={
                ticker: ohlcv_frame_factory(days=40, start_price=100.0, daily_return=0.0005)
                for ticker in tickers
            },
            provider="massive",
            fetched=tuple(tickers),
            fresh_cache_hits=(),
            stale_cache_hits=(),
            missing=(),
            warnings=(),
            used_stale_cache=False,
        )

    def fake_build_historical_methodology_targets(ohlcv, rebalance_dates, phase):
        del ohlcv, phase
        rebalance_dates = pd.DatetimeIndex(rebalance_dates)
        weights = pd.DataFrame({"XLK": [1.0] * len(rebalance_dates)}, index=rebalance_dates)
        return backtest.HistoricalSignalTargets(
            target_weights=weights,
            states=pd.DataFrame({"XLK": ["HOLD"] * len(rebalance_dates)}, index=rebalance_dates),
            snapshots={},
        )

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.setattr(run_backtest, "MASSIVE_VALIDATION_REPORT_PATH", tmp_path / "massive_report.md")
    monkeypatch.setattr(run_backtest, "MASSIVE_VALIDATION_SUMMARY_PATH", tmp_path / "massive_summary.csv")
    monkeypatch.setattr(run_backtest, "CALIBRATION_REPORT_PATH", tmp_path / "calibration_10y_report.md")
    monkeypatch.setattr(run_backtest, "CALIBRATION_SUMMARY_PATH", tmp_path / "calibration_10y_summary.csv")
    monkeypatch.setattr(run_backtest, "CALIBRATION_METADATA_PATH", tmp_path / "calibration_10y_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv_result", fake_fetch_result)
    monkeypatch.setattr(run_backtest, "_resolved_provider", lambda provider: "massive")
    monkeypatch.setattr(
        run_backtest.backtest,
        "build_historical_methodology_targets",
        fake_build_historical_methodology_targets,
    )
    monkeypatch.setattr(run_backtest, "_build_massive_provider_validation_summary", lambda **kwargs: massive_summary)

    assert run_backtest.main(["--massive-variants"]) == 0

    validation_report = run_backtest.MASSIVE_VALIDATION_REPORT_PATH.read_text(encoding="utf-8")
    validation_summary = pd.read_csv(run_backtest.MASSIVE_VALIDATION_SUMMARY_PATH)
    metadata = json.loads(run_backtest.METADATA_PATH.read_text(encoding="utf-8"))
    assert "# Massive Historical Provider-Data Validation Report" in validation_report
    assert "Requested OHLCV provider: auto" in validation_report
    assert "Resolved OHLCV provider: massive" in validation_report
    assert "CAGR Delta" in validation_report
    assert "Drawdown Delta" in validation_report
    assert "OOS CAGR Delta" in validation_report
    assert "OOS Drawdown Delta" in validation_report
    assert "Block-trade upside ratio >= 1.25" in validation_report
    assert "No Massive-derived rule is promoted into live scoring" in validation_report
    assert "provider-flow behavior" in validation_report
    assert "broker behavior" in validation_report
    assert validation_summary.loc[1, "provider"] == "massive"
    assert validation_summary.loc[2, "promotion_label"] == "do not promote"
    assert metadata["massive_validation_report_sha256"] == run_backtest._sha256_bytes(
        run_backtest.MASSIVE_VALIDATION_REPORT_PATH.read_bytes()
    )
    assert metadata["massive_validation_summary"][1]["variant"] == "Massive aggregate OHLCV"
    assert metadata["ohlcv_source"]["cache_policy"] == "bypassed"
    assert fetch_calls[0] == {
        "tickers": run_backtest.REQUIRED_TICKERS,
        "period": "max",
        "provider": "auto",
        "use_cache": False,
    }


def test_run_backtest_returns_manual_data_error_when_required_prices_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", lambda tickers, period, provider: {})

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.METHODOLOGY_REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.STATES_PATH.exists()
    assert not run_backtest.METADATA_PATH.exists()


def test_run_backtest_returns_manual_data_error_when_fetch_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)

    def fail_fetch(tickers, period, provider):
        raise RuntimeError("download failed")

    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fail_fetch)

    assert run_backtest.main() == 2
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.METHODOLOGY_REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.STATES_PATH.exists()
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

    def fake_split_backtest_metrics(result, oos_start="2015-01-01"):
        split_calls.append((result, oos_start))
        return split_results[len(split_calls) - 1]

    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.setattr(run_backtest, "CALIBRATION_REPORT_PATH", tmp_path / "calibration_10y_report.md", raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_SUMMARY_PATH", tmp_path / "calibration_10y_summary.csv", raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_METADATA_PATH", tmp_path / "calibration_10y_metadata.json", raising=False)
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(run_backtest, "_build_macro_variant_summary", lambda **kwargs: pd.DataFrame())
    calibration_builder_calls = []

    def fake_build_calibration_baseline_artifacts(**kwargs):
        calibration_builder_calls.append(kwargs)
        return (
            pd.DataFrame(
                [
                    {
                        "scope": "overall",
                        "direction": "positive",
                        "horizon_weeks": 4,
                        "hit_rate": 1.0,
                    }
                ]
            ),
            "# Calibration Baseline Report\n",
            {
                "ticket": "B-163",
                "slice": "B-163.5",
                "research_only": True,
                "live_promotion_allowed": False,
            },
        )

    monkeypatch.setattr(
        run_backtest,
        "_build_calibration_baseline_artifacts",
        fake_build_calibration_baseline_artifacts,
        raising=False,
    )
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
    assert "## Macro Condition Variants" not in report
    assert run_backtest.METHODOLOGY_REPORT_PATH.exists()
    methodology_report = run_backtest.METHODOLOGY_REPORT_PATH.read_text(encoding="utf-8")
    assert "Historical Methodology Backtest Report" in methodology_report
    assert "research evidence, not investment advice" in methodology_report
    assert run_backtest.EQUITY_PATH.exists()
    equity = run_backtest.EQUITY_PATH.read_text(encoding="utf-8")
    assert "Methodology" in equity
    assert "60/40 SPY/AGG" in equity
    assert "Equal-weight sectors" in equity
    assert run_backtest.STATES_PATH.exists()
    states = pd.read_csv(run_backtest.STATES_PATH, index_col=0)
    assert list(states.columns) == ["XLK", "XLF"]
    assert "WARNING" in states["XLK"].tolist()
    assert run_backtest.METADATA_PATH.exists()
    metadata = json.loads(run_backtest.METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["report_sha256"] == run_backtest._sha256_bytes(run_backtest.REPORT_PATH.read_bytes())
    assert metadata["methodology_report_sha256"] == run_backtest._sha256_bytes(
        run_backtest.METHODOLOGY_REPORT_PATH.read_bytes()
    )
    assert metadata["equity_sha256"] == run_backtest._sha256_bytes(run_backtest.EQUITY_PATH.read_bytes())
    assert metadata["states_sha256"] == run_backtest._sha256_bytes(run_backtest.STATES_PATH.read_bytes())
    assert metadata["required_tickers"] == expected_tickers
    assert metadata["simulation_summary"]["state_transition_count"] == 2
    assert metadata["simulation_summary"]["state_transitions_per_ticker_year"] > 0.0
    assert metadata["macro_variant_summary"] == []
    assert "Methodology" in metadata["equity_columns"]
    assert metadata["states_columns"] == ["XLK", "XLF"]
    assert metadata["baseline_config"]["ticket"] == "B-163"
    assert metadata["baseline_config"]["universe"] == expected_tickers
    assert metadata["baseline_config"]["provider_flags"]["ohlcv_provider"] == "auto"
    assert metadata["baseline_config_sha256"] == backtest.baseline_config_hash(
        metadata["baseline_config"]
    )
    baseline_config_path = run_backtest._calibration_baseline_config_path()
    assert baseline_config_path.exists()
    assert json.loads(baseline_config_path.read_text(encoding="utf-8")) == metadata[
        "baseline_config"
    ]
    assert metadata["calibration_split_summary"]["status"] == "insufficient_history"
    assert metadata["calibration_split_summary"]["requested_years"] == 10
    assert calibration_builder_calls
    assert calibration_builder_calls[0]["baseline_config"]["ticket"] == "B-163"
    assert run_backtest.CALIBRATION_REPORT_PATH.read_text(encoding="utf-8").startswith(
        "# Calibration Baseline Report"
    )
    calibration_summary = pd.read_csv(run_backtest.CALIBRATION_SUMMARY_PATH)
    assert calibration_summary.loc[0, "scope"] == "overall"
    calibration_metadata = json.loads(run_backtest.CALIBRATION_METADATA_PATH.read_text(encoding="utf-8"))
    assert calibration_metadata["slice"] == "B-163.5"
    assert calibration_metadata["summary_sha256"] == run_backtest._sha256_bytes(
        run_backtest.CALIBRATION_SUMMARY_PATH.read_bytes()
    )
    assert metadata["calibration_10y_summary_sha256"] == calibration_metadata["summary_sha256"]


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
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
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
    assert not run_backtest.METHODOLOGY_REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.STATES_PATH.exists()
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
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.delenv("OHLCV_PROVIDER", raising=False)
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 2
    assert calls == [(expected_tickers, "max", "auto")]
    assert not run_backtest.REPORT_PATH.exists()
    assert not run_backtest.METHODOLOGY_REPORT_PATH.exists()
    assert not run_backtest.EQUITY_PATH.exists()
    assert not run_backtest.STATES_PATH.exists()
    assert not run_backtest.METADATA_PATH.exists()


def test_run_backtest_honors_configured_ohlcv_provider(monkeypatch, tmp_path):
    calls = []

    def fake_fetch(tickers, period, provider):
        calls.append(provider)
        return {}

    monkeypatch.setenv("OHLCV_PROVIDER", "massive")
    monkeypatch.setattr(run_backtest, "REPORT_PATH", tmp_path / "backtest_report.md")
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", tmp_path / "backtest_methodology_report.md")
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", tmp_path / "backtest_equity.csv")
    monkeypatch.setattr(run_backtest, "STATES_PATH", tmp_path / "backtest_states.csv")
    monkeypatch.setattr(run_backtest, "METADATA_PATH", tmp_path / "backtest_metadata.json")
    monkeypatch.setattr(run_backtest, "fetch_ohlcv", fake_fetch)

    assert run_backtest.main() == 2
    assert calls == ["massive"]


def test_write_artifacts_does_not_replace_existing_files_when_stage_fails(monkeypatch, tmp_path):
    report_path = tmp_path / "backtest_report.md"
    methodology_path = tmp_path / "backtest_methodology_report.md"
    equity_path = tmp_path / "backtest_equity.csv"
    states_path = tmp_path / "backtest_states.csv"
    metadata_path = tmp_path / "backtest_metadata.json"
    report_path.write_text("old report", encoding="utf-8")
    methodology_path.write_text("old methodology", encoding="utf-8")
    equity_path.write_text("old equity", encoding="utf-8")
    states_path.write_text("old states", encoding="utf-8")
    metadata_path.write_text("old metadata", encoding="utf-8")
    monkeypatch.setattr(run_backtest, "REPORT_PATH", report_path)
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", methodology_path)
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", equity_path)
    monkeypatch.setattr(run_backtest, "STATES_PATH", states_path)
    monkeypatch.setattr(run_backtest, "METADATA_PATH", metadata_path)

    original_write_bytes = run_backtest.Path.write_bytes

    def fail_methodology_tmp(path, payload):
        if path.name == "backtest_methodology_report.md.tmp":
            raise OSError("disk full")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(run_backtest.Path, "write_bytes", fail_methodology_tmp)

    with pytest.raises(OSError, match="disk full"):
        run_backtest._write_artifacts(
            "new report",
            "new methodology",
            pd.DataFrame({"Methodology": [1.0]}, index=pd.Index(["2024-01-01"], name="date")),
            pd.DataFrame({"XLK": ["HOLD"]}, index=pd.Index(["2024-01-01"], name="date")),
            ["XLK"],
            simulation_summary={"state_transitions_per_ticker_year": 1.0},
        )

    assert report_path.read_text(encoding="utf-8") == "old report"
    assert methodology_path.read_text(encoding="utf-8") == "old methodology"
    assert equity_path.read_text(encoding="utf-8") == "old equity"
    assert states_path.read_text(encoding="utf-8") == "old states"
    assert metadata_path.read_text(encoding="utf-8") == "old metadata"


def test_write_artifacts_persists_calibration_artifacts_and_metadata(monkeypatch, tmp_path):
    report_path = tmp_path / "backtest_report.md"
    methodology_path = tmp_path / "backtest_methodology_report.md"
    equity_path = tmp_path / "backtest_equity.csv"
    states_path = tmp_path / "backtest_states.csv"
    metadata_path = tmp_path / "backtest_metadata.json"
    calibration_report_path = tmp_path / "calibration_10y_report.md"
    calibration_summary_path = tmp_path / "calibration_10y_summary.csv"
    calibration_metadata_path = tmp_path / "calibration_10y_metadata.json"

    monkeypatch.setattr(run_backtest, "REPORT_PATH", report_path)
    monkeypatch.setattr(run_backtest, "METHODOLOGY_REPORT_PATH", methodology_path)
    monkeypatch.setattr(run_backtest, "EQUITY_PATH", equity_path)
    monkeypatch.setattr(run_backtest, "STATES_PATH", states_path)
    monkeypatch.setattr(run_backtest, "METADATA_PATH", metadata_path)
    monkeypatch.setattr(run_backtest, "CALIBRATION_REPORT_PATH", calibration_report_path, raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_SUMMARY_PATH", calibration_summary_path, raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_METADATA_PATH", calibration_metadata_path, raising=False)

    calibration_summary = pd.DataFrame(
        [
            {
                "scope": "overall",
                "direction": "positive",
                "horizon_weeks": 4,
                "hit_rate": 0.75,
            }
        ]
    )

    run_backtest._write_artifacts(
        "report",
        "methodology",
        pd.DataFrame({"Methodology": [1.0]}, index=pd.to_datetime(["2020-01-03"])),
        pd.DataFrame({"XLK": ["HOLD"]}, index=pd.to_datetime(["2020-01-03"])),
        ["XLK"],
        calibration_report="# Calibration Baseline Report\n",
        calibration_summary=calibration_summary,
        calibration_metadata={
            "ticket": "B-163",
            "slice": "B-163.5",
            "research_only": True,
            "live_promotion_allowed": False,
        },
    )

    assert calibration_report_path.read_text(encoding="utf-8").startswith("# Calibration")
    assert pd.read_csv(calibration_summary_path).loc[0, "hit_rate"] == pytest.approx(0.75)
    calibration_metadata = json.loads(calibration_metadata_path.read_text(encoding="utf-8"))
    backtest_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert calibration_metadata["summary_sha256"] == run_backtest._sha256_bytes(
        calibration_summary_path.read_bytes()
    )
    assert calibration_metadata["report_sha256"] == run_backtest._sha256_bytes(
        calibration_report_path.read_bytes()
    )
    assert backtest_metadata["calibration_10y_summary_sha256"] == calibration_metadata[
        "summary_sha256"
    ]
    assert backtest_metadata["calibration_10y_report_sha256"] == calibration_metadata[
        "report_sha256"
    ]
