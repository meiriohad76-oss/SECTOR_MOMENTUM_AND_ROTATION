from __future__ import annotations

import json
import io
import zipfile

import pandas as pd
import pytest

from src import flow

_REAL_FETCH_PRIMARY_FLOW_PAYLOAD = flow._fetch_primary_flow_payload


@pytest.fixture(autouse=True)
def neutral_primary_flow_provider(monkeypatch):
    # Keep this suite hermetic even when the host environment enables live flow.
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", True)

    def blocked_fetch(ticker):
        raise AssertionError("tests must opt in before fetching primary-flow payloads")

    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", blocked_fetch)


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


def test_compute_flow_signals_blocks_unexpected_primary_flow_fetch(
    monkeypatch,
    ohlcv_frame_factory,
):
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)

    with pytest.raises(AssertionError, match="tests must opt in"):
        flow.compute_flow_signals({"XLK": ohlcv_frame_factory(days=80)})


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


def test_etf_primary_flow_returns_neutral_when_live_mode_has_no_source(monkeypatch):
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)
    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", _REAL_FETCH_PRIMARY_FLOW_PAYLOAD)
    monkeypatch.setattr(flow, "_primary_flow_source_url", lambda ticker: None)

    def fail_fetch(source_url):
        raise AssertionError("missing source URL should not call Massive")

    monkeypatch.setattr(flow, "_fetch_massive_browser_content", fail_fetch)

    assert flow.etf_primary_flow_5d_pct("XLK") == 0.0


def test_etf_primary_flow_does_not_fetch_when_stub_mode_enabled(monkeypatch):
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", True)

    def fail_fetch(ticker):
        raise AssertionError("stub mode should not fetch primary-flow payloads")

    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", fail_fetch)

    assert flow.etf_primary_flow_5d_pct("XLK") == 0.0


def test_etf_primary_flow_uses_provider_payload_when_configured(monkeypatch):
    payload = {
        "records": [
            {"as_of": "2026-05-12", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-13", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-14", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-15", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-18", "shares_outstanding": 101_000_000, "nav": 50.0, "aum": 5_050_000_000},
            {"as_of": "2026-05-19", "shares_outstanding": 102_000_000, "nav": 50.0, "aum": 5_100_000_000},
        ]
    }
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)
    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", lambda ticker: json.dumps(payload))

    assert flow.etf_primary_flow_5d_pct("XLK") == pytest.approx(1.9607843137)


def test_compute_flow_signals_keeps_unwired_stubs_neutral_when_etf_flow_live(
    monkeypatch,
    ohlcv_frame_factory,
):
    payload = {
        "records": [
            {"as_of": "2026-05-12", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-13", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-14", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-15", "shares_outstanding": 100_000_000, "nav": 50.0, "aum": 5_000_000_000},
            {"as_of": "2026-05-18", "shares_outstanding": 101_000_000, "nav": 50.0, "aum": 5_050_000_000},
            {"as_of": "2026-05-19", "shares_outstanding": 102_000_000, "nav": 50.0, "aum": 5_100_000_000},
        ]
    }
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)
    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", lambda ticker: json.dumps(payload))

    out = flow.compute_flow_signals({"XLK": ohlcv_frame_factory(days=80)})

    assert out.loc["XLK", "etf_flow_5d_pct"] == pytest.approx(1.9607843137)
    assert out.loc["XLK", "block_up_ratio"] == 1.0
    assert out.loc["XLK", "dark_pool_pct"] == 0.40
    assert out.loc["XLK", "si_delta_15d"] == 0.0
    assert out.loc["XLK", "thirteen_f_q"] == 0.0


def test_remaining_provider_flags_are_independent_from_legacy_stub_mode(
    monkeypatch,
    ohlcv_frame_factory,
):
    monkeypatch.setattr(flow, "STUB_MODE", False)
    monkeypatch.setattr(flow, "MASSIVE_TRADES_STUB_MODE", True, raising=False)
    monkeypatch.setattr(flow, "FINRA_ATS_STUB_MODE", True, raising=False)
    monkeypatch.setattr(flow, "FINRA_SHORT_INTEREST_STUB_MODE", True, raising=False)
    monkeypatch.setattr(flow, "SEC_13F_STUB_MODE", True, raising=False)

    out = flow.compute_flow_signals({"XLK": ohlcv_frame_factory(days=80)})

    assert out.loc["XLK", "block_up_ratio"] == 1.0
    assert out.loc["XLK", "dark_pool_pct"] == 0.40
    assert out.loc["XLK", "si_delta_15d"] == 0.0
    assert out.loc["XLK", "thirteen_f_q"] == 0.0


def test_provider_seams_fail_closed_to_neutral_values(monkeypatch):
    monkeypatch.setattr(flow, "MASSIVE_TRADES_STUB_MODE", False, raising=False)
    monkeypatch.setattr(flow, "FINRA_ATS_STUB_MODE", False, raising=False)
    monkeypatch.setattr(flow, "FINRA_SHORT_INTEREST_STUB_MODE", False, raising=False)
    monkeypatch.setattr(flow, "SEC_13F_STUB_MODE", False, raising=False)

    monkeypatch.setattr(flow, "_provider_block_trade_upside_ratio", lambda ticker: None)
    monkeypatch.setattr(flow, "_provider_dark_pool_pct", lambda ticker: None)
    monkeypatch.setattr(
        flow,
        "_provider_short_interest_delta_15d",
        lambda ticker: (_ for _ in ()).throw(flow.requests.Timeout("finra timed out")),
    )
    monkeypatch.setattr(flow, "_provider_thirteen_f_net_buys_q", lambda ticker: None)

    assert flow.block_trade_upside_ratio("XLK") == 1.0
    assert flow.dark_pool_pct("XLK") == 0.40
    assert flow.short_interest_delta_15d("XLK") == 0.0
    assert flow.thirteen_f_net_buys_q("XLK") == 0.0


def test_block_trade_upside_ratio_from_massive_trades_uses_block_notional():
    trades = [
        {"p": 100.0, "s": 100, "sip_timestamp": 1, "correction": 0},
        {"p": 101.0, "s": 3_000, "sip_timestamp": 2, "correction": 0},
        {"p": 102.0, "s": 500, "sip_timestamp": 3, "correction": 0},
        {"p": 99.0, "s": 4_000, "sip_timestamp": 4, "correction": 0},
        {"p": 98.0, "s": 20_000, "sip_timestamp": 5, "correction": 1},
        {"p": 100.0, "s": 10_000, "sip_timestamp": 6, "correction": 0},
    ]

    ratio = flow.block_trade_upside_ratio_from_massive_trades(trades)

    assert ratio == pytest.approx((101.0 * 3_000 + 100.0 * 10_000) / (99.0 * 4_000))


def test_fetch_massive_stock_trades_uses_key_and_trade_endpoint(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"p": 100.0, "s": 100}]}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(flow, "_resolve_secret", lambda name: "secret" if name == "MASSIVE_API_KEY" else None)
    monkeypatch.setattr(flow.requests, "get", fake_get)

    trades = flow._fetch_massive_stock_trades("xlk", start_date="2026-05-19", limit=50, timeout=7)

    assert trades == [{"p": 100.0, "s": 100}]
    assert calls[0][0] == "https://api.massive.com/v3/trades/XLK"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"
    assert calls[0][1]["params"]["timestamp.gte"] == "2026-05-19"
    assert calls[0][1]["params"]["limit"] == 50
    assert calls[0][1]["params"]["sort"] == "timestamp"
    assert calls[0][1]["params"]["order"] == "desc"
    assert calls[0][1]["timeout"] == 7


def test_block_trade_upside_ratio_uses_massive_provider_when_enabled(monkeypatch):
    monkeypatch.setattr(flow, "MASSIVE_TRADES_STUB_MODE", False, raising=False)
    monkeypatch.setattr(
        flow,
        "_fetch_massive_stock_trades",
        lambda ticker: [
            {"p": 100.0, "s": 100, "sip_timestamp": 1},
            {"p": 101.0, "s": 3_000, "sip_timestamp": 2},
            {"p": 99.0, "s": 4_000, "sip_timestamp": 3},
        ],
    )

    assert flow.block_trade_upside_ratio("XLK") == pytest.approx((101.0 * 3_000) / (99.0 * 4_000))


def test_short_interest_delta_from_finra_records_prefers_reported_change_percent():
    records = [
        {"symbolCode": "XLK", "settlementDate": "2026-05-15", "changePercent": "12.5"},
        {"symbolCode": "XLK", "settlementDate": "2026-04-30", "changePercent": "-3.0"},
    ]

    assert flow.short_interest_delta_from_finra_records(records) == pytest.approx(12.5)


def test_short_interest_delta_from_finra_records_can_compute_from_positions():
    records = [
        {"symbolCode": "XLK", "settlementDate": "2026-05-15", "currentShortPositionQuantity": "1,250,000"},
        {"symbolCode": "XLK", "settlementDate": "2026-04-30", "currentShortPositionQuantity": "1,000,000"},
    ]

    assert flow.short_interest_delta_from_finra_records(records) == pytest.approx(25.0)


def test_fetch_finra_short_interest_posts_symbol_filter(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"symbolCode": "XLK", "changePercent": "5.0"}]

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(flow.requests, "post", fake_post)

    records = flow._fetch_finra_short_interest("xlk", limit=2, timeout=7)

    assert records == [{"symbolCode": "XLK", "changePercent": "5.0"}]
    assert calls[0][0] == "https://api.finra.org/data/group/otcmarket/name/consolidatedShortInterest"
    assert calls[0][1]["json"]["limit"] == 2
    assert calls[0][1]["json"]["compareFilters"][0]["fieldName"] == "symbolCode"
    assert calls[0][1]["json"]["compareFilters"][0]["fieldValue"] == "XLK"
    assert "settlementDate" in calls[0][1]["json"]["fields"]
    assert calls[0][1]["timeout"] == 7


def test_short_interest_delta_uses_finra_provider_when_enabled(monkeypatch):
    monkeypatch.setattr(flow, "FINRA_SHORT_INTEREST_STUB_MODE", False, raising=False)
    monkeypatch.setattr(
        flow,
        "_fetch_finra_short_interest",
        lambda ticker: [
            {"symbolCode": "XLK", "settlementDate": "2026-05-15", "changePercent": "-8.25"},
        ],
    )

    assert flow.short_interest_delta_15d("XLK") == pytest.approx(-8.25)


def test_dark_pool_pct_from_finra_ats_records_uses_latest_week():
    records = [
        {
            "issueSymbolIdentifier": "XLK",
            "weekStartDate": "2026-05-04",
            "summaryTypeCode": "ATS_W_SMBL",
            "totalWeeklyShareQuantity": "100",
        },
        {
            "issueSymbolIdentifier": "XLK",
            "weekStartDate": "2026-05-11",
            "summaryTypeCode": "ATS_W_SMBL",
            "totalWeeklyShareQuantity": "400",
        },
        {
            "issueSymbolIdentifier": "XLK",
            "weekStartDate": "2026-05-11",
            "summaryTypeCode": "OTC_W_SMBL",
            "totalWeeklyShareQuantity": "600",
        },
    ]

    assert flow.dark_pool_pct_from_finra_ats_records(records) == pytest.approx(0.40)


def test_fetch_finra_ats_weekly_summary_posts_symbol_filter(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"issueSymbolIdentifier": "XLK"}]

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(flow.requests, "post", fake_post)

    records = flow._fetch_finra_ats_weekly_summary("xlk", limit=20, timeout=7)

    assert records == [{"issueSymbolIdentifier": "XLK"}]
    assert calls[0][0] == "https://api.finra.org/data/group/otcMarket/name/weeklySummary"
    assert calls[0][1]["json"]["limit"] == 20
    assert calls[0][1]["json"]["compareFilters"][0]["fieldName"] == "issueSymbolIdentifier"
    assert calls[0][1]["json"]["compareFilters"][0]["fieldValue"] == "XLK"
    assert "summaryTypeCode" in calls[0][1]["json"]["fields"]
    assert calls[0][1]["timeout"] == 7


def test_dark_pool_pct_uses_finra_provider_when_enabled(monkeypatch):
    monkeypatch.setattr(flow, "FINRA_ATS_STUB_MODE", False, raising=False)
    monkeypatch.setattr(
        flow,
        "_fetch_finra_ats_weekly_summary",
        lambda ticker: [
            {
                "issueSymbolIdentifier": "XLK",
                "weekStartDate": "2026-05-11",
                "summaryTypeCode": "ATS_W_SMBL",
                "totalWeeklyShareQuantity": "250",
            },
            {
                "issueSymbolIdentifier": "XLK",
                "weekStartDate": "2026-05-11",
                "summaryTypeCode": "OTC_W_SMBL",
                "totalWeeklyShareQuantity": "750",
            },
        ],
    )

    assert flow.dark_pool_pct("XLK") == pytest.approx(0.25)


def test_thirteen_f_net_buys_from_sec_records_uses_cusip_mapping():
    records = [
        {"CUSIP": "81369Y100", "REPORTCALENDARORQUARTER": "2025-06-30", "SSHPRNAMT": "1,000"},
        {"CUSIP": "81369Y100", "REPORTCALENDARORQUARTER": "2025-09-30", "SSHPRNAMT": "1,500"},
        {"CUSIP": "999999999", "REPORTCALENDARORQUARTER": "2025-09-30", "SSHPRNAMT": "9,999"},
    ]

    assert flow.thirteen_f_net_buys_from_sec_records(records, ["81369Y100"]) == pytest.approx(50.0)


def test_fetch_sec_13f_records_reads_configured_zip(monkeypatch):
    calls = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "INFOTABLE.tsv",
            "ACCESSION_NUMBER\tCUSIP\tREPORTCALENDARORQUARTER\tSSHPRNAMT\n"
            "0001\t81369Y100\t2025-09-30\t1500\n",
        )

    class FakeResponse:
        content = buffer.getvalue()

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(flow.requests, "get", fake_get)

    records = flow._fetch_sec_13f_records(
        data_url="https://www.sec.gov/files/structureddata/data/form-13f-data-sets/example.zip",
        user_agent="sector-dashboard test@example.com",
        timeout=7,
    )

    assert records == [
        {
            "ACCESSION_NUMBER": "0001",
            "CUSIP": "81369Y100",
            "REPORTCALENDARORQUARTER": "2025-09-30",
            "SSHPRNAMT": "1500",
        }
    ]
    assert calls[0][1]["headers"]["User-Agent"] == "sector-dashboard test@example.com"
    assert calls[0][1]["timeout"] == 7


def test_thirteen_f_net_buys_uses_sec_provider_when_enabled(monkeypatch):
    monkeypatch.setattr(flow, "SEC_13F_STUB_MODE", False, raising=False)

    def fake_secret(name):
        values = {
            "SEC_13F_CUSIP_XLK": "81369Y100",
            "SEC_13F_DATA_URL": "https://example.test/form13f.zip",
            "SEC_USER_AGENT": "sector-dashboard test@example.com",
        }
        return values.get(name)

    monkeypatch.setattr(flow, "_resolve_secret", fake_secret)
    monkeypatch.setattr(
        flow,
        "_fetch_sec_13f_records",
        lambda data_url=None, user_agent=None, timeout=20: [
            {"CUSIP": "81369Y100", "REPORTCALENDARORQUARTER": "2025-06-30", "SSHPRNAMT": "1,000"},
            {"CUSIP": "81369Y100", "REPORTCALENDARORQUARTER": "2025-09-30", "SSHPRNAMT": "1,250"},
        ],
    )

    assert flow.thirteen_f_net_buys_q("XLK") == pytest.approx(25.0)


def test_etf_primary_flow_returns_neutral_on_provider_request_error(monkeypatch):
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)
    monkeypatch.setattr(
        flow,
        "_fetch_primary_flow_payload",
        lambda ticker: (_ for _ in ()).throw(flow.requests.Timeout("provider timed out")),
    )

    assert flow.etf_primary_flow_5d_pct("XLK") == 0.0


def test_etf_primary_flow_does_not_hide_unexpected_parser_errors(monkeypatch):
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", False)
    monkeypatch.setattr(flow, "_fetch_primary_flow_payload", lambda ticker: '{"records": []}')

    def broken_parser(payload):
        raise RuntimeError("programming bug")

    monkeypatch.setattr(flow, "parse_primary_flow_snapshots", broken_parser)

    with pytest.raises(RuntimeError, match="programming bug"):
        flow.etf_primary_flow_5d_pct("XLK")


def test_fetch_massive_browser_content_sends_bearer_token_and_browser_params(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200
        text = "content"

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(flow.requests, "get", fake_get)

    content = flow._fetch_massive_browser_content(
        "https://issuer.example/flow.csv",
        api_key="secret",
        timeout=7,
    )

    assert content == "content"
    assert calls[0][0] == flow.MASSIVE_BROWSER_URL
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"
    assert calls[0][1]["params"]["url"] == "https://issuer.example/flow.csv"
    assert calls[0][1]["params"]["format"] == "raw"
    assert calls[0][1]["params"]["expiration"] == 0
    assert calls[0][1]["timeout"] == 7
