from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from src.fred_data import FRED_SERIES
from src.data_health import (
    dashboard_health_summary,
    data_health_rows,
    format_age_label,
)


def _ohlcv_frame(end: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [100.0, 101.0], "adj_close": [100.0, 101.0]},
        index=pd.to_datetime(["2026-05-20", end]),
    )


def test_format_age_label_uses_observation_age():
    assert format_age_label(pd.Timestamp("2026-05-21"), now=pd.Timestamp("2026-05-26")) == "5d old"
    assert format_age_label(None, now=pd.Timestamp("2026-05-26")) == "missing"


def test_data_health_rows_show_ohlcv_and_fred_staleness():
    provider_result = SimpleNamespace(
        provider="massive",
        used_stale_cache=False,
        stale_cache_hits=(),
        missing=(),
        warnings=(),
    )
    fred_data = {
        "DGS10": pd.Series([4.5], index=pd.to_datetime(["2026-05-21"])),
        "DCOILWTICO": pd.Series([112.25], index=pd.to_datetime(["2026-05-10"])),
        "STLFSI4": pd.Series([-0.74], index=pd.to_datetime(["2026-05-09"])),
    }

    rows = data_health_rows(
        ohlcv={"SPY": _ohlcv_frame("2026-05-22"), "XLK": _ohlcv_frame("2026-05-22")},
        expected_symbols=("SPY", "XLK"),
        ohlcv_result=provider_result,
        fred_data=fred_data,
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T08:00:00Z"),
        provider_flow_stubbed=True,
        provider_flow_statuses=[
            {
                "id": "massive_block_trades",
                "label": "Massive block trades",
                "provider": "Massive",
                "status": "info",
                "mode": "stubbed neutral",
                "detail": "block_up_ratio neutral",
            },
            {
                "id": "finra_ats_dark_pool",
                "label": "FINRA ATS dark pool",
                "provider": "FINRA",
                "status": "healthy",
                "mode": "enabled",
                "detail": "dark_pool_pct live",
            },
        ],
    )

    by_source = {row["source"]: row for row in rows}

    assert by_source["Market OHLCV"]["lane_id"] == "market_ohlcv"
    assert by_source["Market OHLCV"]["refresh_label"] == "Refresh market OHLCV"
    assert by_source["Market OHLCV"]["refresh_key"] == "data_health_refresh_market_ohlcv"
    assert by_source["Market OHLCV"]["sla"] == "fresh <=5d; stale >10d"
    assert by_source["Market OHLCV"]["severity_symbol"] == "OK"
    assert by_source["Market OHLCV"]["status"] == "healthy"
    assert by_source["Market OHLCV"]["freshness"] == "4d old"
    assert "2/2 symbols loaded" in by_source["Market OHLCV"]["detail"]
    assert by_source["Market OHLCV"]["role"] == "Critical: price, volume, trend, momentum, and market proxies"
    assert by_source["FRED macro/regime"]["lane_id"] == "fred_macro"
    assert by_source["FRED macro/regime"]["refresh_label"] == "Refresh FRED macro"
    assert by_source["FRED macro/regime"]["refresh_key"] == "data_health_refresh_fred_macro"
    assert by_source["FRED macro/regime"]["sla"] == "series cadence adjusted"
    assert by_source["FRED macro/regime"]["severity_symbol"] == "WARN"
    assert by_source["FRED macro/regime"]["status"] == "warning"
    assert by_source["FRED macro/regime"]["freshness"] == "latest available: 5d old"
    assert by_source["FRED macro/regime"]["coverage"] == "2 stale series"
    assert "2 stale" in by_source["FRED macro/regime"]["detail"]
    assert "DCOILWTICO 16d old" in by_source["FRED macro/regime"]["detail"]
    assert "cadence/release-lag adjusted" in by_source["FRED macro/regime"]["detail"]
    assert by_source["FRED macro/regime"]["role"] == "Critical when configured: business-cycle tilt and macro context"
    assert by_source["Provider-flow feeds"]["lane_id"] == "provider_flow"
    assert by_source["Provider-flow feeds"]["refresh_label"] == "Recompute flow signals"
    assert by_source["Provider-flow feeds"]["refresh_key"] == "data_health_refresh_provider_flow"
    assert by_source["Provider-flow feeds"]["severity_symbol"] == "INFO"
    assert by_source["Provider-flow feeds"]["status"] == "info"
    assert by_source["Provider-flow feeds"]["sla"] == "recomputes from current OHLCV"
    assert by_source["Provider-flow feeds"]["freshness"] == "derived from market lane"
    assert by_source["Provider-flow feeds"]["providers"][0]["label"] == "Massive block trades"
    assert "Massive block trades: stubbed neutral" in by_source["Provider-flow feeds"]["detail"]
    assert "FINRA ATS dark pool: enabled" in by_source["Provider-flow feeds"]["detail"]
    assert "neutral/stub" in by_source["Provider-flow feeds"]["detail"]


def test_data_health_rows_include_refreshable_compute_lane_metadata():
    rows = data_health_rows(
        ohlcv={"SPY": _ohlcv_frame("2026-05-26")},
        expected_symbols=("SPY",),
        ohlcv_result=SimpleNamespace(provider="massive", missing=(), stale_cache_hits=(), warnings=()),
        fred_data={},
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T16:00:00Z"),
        provider_flow_stubbed=True,
    )

    compute_row = next(row for row in rows if row["source"] == "Dashboard compute")

    assert compute_row["lane_id"] == "dashboard_compute"
    assert compute_row["refresh_label"] == "Recompute dashboard"
    assert compute_row["refresh_key"] == "data_health_refresh_dashboard_compute"
    assert compute_row["sla"] == "snapshot <=60m"
    assert compute_row["severity_symbol"] in {"OK", "WARN"}


def test_ohlcv_health_headline_uses_latest_bar_age_and_details_oldest_loaded_bar():
    rows = data_health_rows(
        ohlcv={
            "SPY": _ohlcv_frame("2026-05-26"),
            "XLK": _ohlcv_frame("2026-05-21"),
        },
        expected_symbols=("SPY", "XLK"),
        ohlcv_result=SimpleNamespace(provider="massive", missing=(), stale_cache_hits=(), warnings=()),
        fred_data={},
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T16:00:00Z"),
        provider_flow_stubbed=True,
    )

    market_row = next(row for row in rows if row["source"] == "Market OHLCV")

    assert market_row["status"] == "healthy"
    assert market_row["latest"] == "2026-05-26"
    assert market_row["freshness"] == "today"
    assert market_row["coverage"] == "oldest 2026-05-21 (5d old)"
    assert "oldest loaded bar 2026-05-21 (5d old)" in market_row["detail"]


def test_ohlcv_health_uses_oldest_loaded_symbol_not_only_latest_symbol():
    rows = data_health_rows(
        ohlcv={
            "SPY": _ohlcv_frame("2026-05-25"),
            "XLK": pd.DataFrame(
                {"close": [100.0, 101.0], "adj_close": [100.0, 101.0]},
                index=pd.to_datetime(["2026-05-09", "2026-05-10"]),
            ),
        },
        expected_symbols=("SPY", "XLK"),
        ohlcv_result=SimpleNamespace(provider="yfinance", missing=(), stale_cache_hits=(), warnings=()),
        fred_data={},
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T08:00:00Z"),
        provider_flow_stubbed=True,
    )

    market_row = next(row for row in rows if row["source"] == "Market OHLCV")

    assert market_row["status"] == "stale"
    assert market_row["freshness"] == "1d old"
    assert market_row["coverage"] == "oldest 2026-05-10 (16d old)"
    assert "oldest loaded bar 2026-05-10" in market_row["detail"]


def test_fred_health_allows_normal_monthly_observation_date_lag():
    monthly_release_lag_dates = {
        "UNRATE": "2026-04-01",
        "M2SL": "2026-04-01",
        "CFNAI": "2026-04-01",
        "UMCSENT": "2026-04-01",
        "RECPROUSM156N": "2026-03-01",
        "PCEPILFE": "2026-03-01",
    }
    fred_data = {
        series_id: pd.Series([1.0], index=pd.to_datetime([monthly_release_lag_dates.get(series_id, "2026-05-22")]))
        for series_id in FRED_SERIES
    }

    rows = data_health_rows(
        ohlcv={"SPY": _ohlcv_frame("2026-05-26")},
        expected_symbols=("SPY",),
        ohlcv_result=SimpleNamespace(provider="massive", missing=(), stale_cache_hits=(), warnings=()),
        fred_data=fred_data,
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T16:00:00Z"),
        provider_flow_stubbed=False,
    )

    fred_row = next(row for row in rows if row["source"] == "FRED macro/regime")

    assert fred_row["status"] == "healthy"
    assert fred_row["freshness"] == "latest available: 4d old"
    assert fred_row["coverage"] == ""
    for series_id in monthly_release_lag_dates:
        assert series_id not in fred_row["detail"]


def test_fred_health_uses_latest_available_date_even_when_series_is_unsorted():
    fred_data = {
        series_id: pd.Series([1.0], index=pd.to_datetime(["2026-05-22"]))
        for series_id in FRED_SERIES
    }
    fred_data["DGS10"] = pd.Series(
        [4.1, 4.4, 4.2],
        index=pd.to_datetime(["2026-05-19", "2026-05-23", "2026-05-20"]),
    )

    rows = data_health_rows(
        ohlcv={"SPY": _ohlcv_frame("2026-05-26")},
        expected_symbols=("SPY",),
        ohlcv_result=SimpleNamespace(provider="massive", missing=(), stale_cache_hits=(), warnings=()),
        fred_data=fred_data,
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T16:00:00Z"),
        provider_flow_stubbed=False,
    )

    fred_row = next(row for row in rows if row["source"] == "FRED macro/regime")

    assert fred_row["latest"] == "2026-05-23"
    assert fred_row["freshness"] == "latest available: 3d old"


def test_fred_health_covers_regime_classifier_series_not_only_visible_tiles():
    rows = data_health_rows(
        ohlcv={"SPY": _ohlcv_frame("2026-05-22")},
        expected_symbols=("SPY",),
        ohlcv_result=SimpleNamespace(provider="massive", missing=(), stale_cache_hits=(), warnings=()),
        fred_data={
            "INDPRO": pd.Series([100.0], index=pd.to_datetime(["2026-04-01"])),
            "UNRATE": pd.Series([4.1], index=pd.to_datetime(["2026-05-01"])),
            "NFCI": pd.Series([-0.2], index=pd.to_datetime(["2026-05-22"])),
            "RECPROUSM156N": pd.Series([1.0], index=pd.to_datetime(["2026-04-01"])),
            "T10Y3M": pd.Series([0.25], index=pd.to_datetime(["2026-05-22"])),
        },
        compute_created_at=1_779_760_000.0,
        now=pd.Timestamp("2026-05-26T08:00:00Z"),
        provider_flow_stubbed=False,
    )

    fred_row = next(row for row in rows if row["source"] == "FRED macro/regime")

    assert "INDPRO" not in fred_row["detail"]
    assert f"5/{len(FRED_SERIES)} series loaded" in fred_row["detail"]
    assert "business-cycle tilt" in fred_row["role"]


def test_dashboard_health_summary_escalates_to_stale_when_sources_are_stale():
    rows = [
        {"status": "healthy"},
        {"status": "warning"},
        {"status": "stale"},
    ]

    summary = dashboard_health_summary(rows)

    assert summary["status"] == "stale"
    assert summary["label"] == "Data stale"
