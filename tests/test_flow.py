from __future__ import annotations

import pandas as pd
import pytest

from src import flow


def test_chaikin_money_flow_is_positive_when_closes_near_high():
    idx = pd.bdate_range("2024-01-01", periods=30)
    df = pd.DataFrame(
        {
            "high": [10.0] * 30,
            "low": [0.0] * 30,
            "close": [9.0] * 30,
            "volume": [1000] * 30,
        },
        index=idx,
    )

    assert flow.chaikin_money_flow(df, period=21) == pytest.approx(0.8)


def test_relative_volume_compares_last_volume_to_previous_average():
    idx = pd.bdate_range("2024-01-01", periods=21)
    df = pd.DataFrame(
        {
            "high": [10.0] * 21,
            "low": [9.0] * 21,
            "close": [9.5] * 21,
            "volume": [100.0] * 20 + [250.0],
        },
        index=idx,
    )

    assert flow.relative_volume(df, lookback=20) == pytest.approx(2.5)


def test_compute_flow_signals_excludes_index_tickers_and_uses_stub_values(
    ohlcv_frame_factory,
):
    out = flow.compute_flow_signals(
        {
            "XLK": ohlcv_frame_factory(days=80),
            "^TNX": ohlcv_frame_factory(days=80),
        }
    )

    assert list(out.index) == ["XLK"]
    assert out.loc["XLK", "etf_flow_5d_pct"] == 0.0
    assert out.loc["XLK", "block_up_ratio"] == 1.0
    assert out.loc["XLK", "dark_pool_pct"] == 0.40
    assert out.loc["XLK", "si_delta_15d"] == 0.0
    assert out.loc["XLK", "thirteen_f_q"] == 0.0


def test_flow_composite_z_handles_constant_inputs_without_nan():
    flow_df = pd.DataFrame(
        {
            "cmf21": [0.1, 0.1],
            "obv_slope": [0.0, 0.0],
            "etf_flow_5d_pct": [0.0, 0.0],
            "block_up_ratio": [1.0, 1.0],
            "rvol": [1.0, 1.0],
            "si_delta_15d": [0.0, 0.0],
        },
        index=["XLK", "XLF"],
    )

    out = flow.flow_composite_z(flow_df)

    assert out.name == "F"
    assert list(out.index) == ["XLK", "XLF"]
    assert not out.isna().any()
    assert out.tolist() == [0.0, 0.0]


def test_parse_primary_flow_snapshots_accepts_json_records():
    payload = """
    {
      "records": [
        {"as_of": "2026-05-12", "shares_outstanding": "100,000,000", "nav": "$50.00", "aum": "$5,000,000,000"},
        {"as_of": "2026-05-19", "shares_outstanding": "102,000,000", "nav": "$50.00", "aum": "$5,100,000,000"}
      ]
    }
    """

    snapshots = flow.parse_primary_flow_snapshots(payload)

    assert len(snapshots) == 2
    assert snapshots[0].as_of == "2026-05-12"
    assert snapshots[0].shares_outstanding == 100_000_000
    assert snapshots[1].aum == 5_100_000_000


def test_primary_flow_5d_pct_uses_share_change_nav_over_latest_aum():
    snapshots = [
        flow.PrimaryFlowSnapshot("2026-05-12", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-13", 100_000_000, 51.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-14", 100_000_000, 52.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-15", 100_000_000, 53.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-18", 101_000_000, 50.0, 5_050_000_000),
        flow.PrimaryFlowSnapshot("2026-05-19", 102_000_000, 55.0, 5_100_000_000),
    ]

    result = flow.primary_flow_5d_pct_from_snapshots(snapshots)

    assert result == pytest.approx(2.0588235294)


def test_primary_flow_5d_pct_sorts_common_us_date_strings_chronologically():
    snapshots = [
        flow.PrimaryFlowSnapshot("5/9/2026", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("5/13/2026", 101_000_000, 50.0, 5_050_000_000),
        flow.PrimaryFlowSnapshot("5/11/2026", 101_000_000, 50.0, 5_050_000_000),
        flow.PrimaryFlowSnapshot("5/14/2026", 102_000_000, 50.0, 5_100_000_000),
        flow.PrimaryFlowSnapshot("5/10/2026", 101_000_000, 50.0, 5_050_000_000),
        flow.PrimaryFlowSnapshot("5/12/2026", 101_000_000, 50.0, 5_050_000_000),
    ]

    result = flow.primary_flow_5d_pct_from_snapshots(snapshots)

    assert result == pytest.approx(1.9607843137)


def test_parse_primary_flow_snapshots_tolerates_unparseable_dates():
    payload = """
    as_of,shares_outstanding,nav,aum
    not-a-date,100000000,50,5000000000
    2026-05-19,101000000,50,5050000000
    """

    snapshots = flow.parse_primary_flow_snapshots(payload)

    assert [snapshot.as_of for snapshot in snapshots] == ["2026-05-19", "not-a-date"]


def test_primary_flow_5d_pct_ignores_unparseable_dates():
    snapshots = [
        flow.PrimaryFlowSnapshot("not-a-date", 999_000_000, 50.0, 49_950_000_000),
        flow.PrimaryFlowSnapshot("2026-05-12", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-13", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-14", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-15", 100_000_000, 50.0, 5_000_000_000),
        flow.PrimaryFlowSnapshot("2026-05-18", 101_000_000, 50.0, 5_050_000_000),
        flow.PrimaryFlowSnapshot("2026-05-19", 102_000_000, 50.0, 5_100_000_000),
    ]

    result = flow.primary_flow_5d_pct_from_snapshots(snapshots)

    assert result == pytest.approx(1.9607843137)


def test_parse_float_accepts_scientific_notation_strings():
    assert flow._parse_float("1e8") == 100_000_000
