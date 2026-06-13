from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src import flow
from src import scoring
from src.ad_hoc_analysis import score_ad_hoc_tickers


@pytest.fixture(autouse=True)
def _stub_provider_flow(monkeypatch):
    monkeypatch.setattr(flow, "ETF_PRIMARY_FLOW_STUB_MODE", True)
    monkeypatch.setattr(flow, "MASSIVE_TRADES_STUB_MODE", True)
    monkeypatch.setattr(flow, "FINRA_ATS_STUB_MODE", True)
    monkeypatch.setattr(flow, "FINRA_SHORT_INTEREST_STUB_MODE", True)
    monkeypatch.setattr(flow, "SEC_13F_STUB_MODE", True)
    flow.reset_provider_flow_runtime_health()


def test_score_ad_hoc_tickers_builds_read_only_snapshot_without_state_write(
    ohlcv_frame_factory,
    tmp_path,
    monkeypatch,
):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(scoring, "STATE_FILE", state_path)
    ohlcv = {
        "ORCL": ohlcv_frame_factory(start_price=95, daily_return=0.0013),
        "SPY": ohlcv_frame_factory(start_price=100, daily_return=0.0010),
        "BIL": ohlcv_frame_factory(start_price=90, daily_return=0.0001),
    }

    result = score_ad_hoc_tickers(["orcl"], ohlcv, phase="MID")

    assert result.missing_tickers == []
    assert result.scored.index.tolist() == ["ORCL"]
    row = result.scored.loc["ORCL"]
    assert row["class"] == "Ad Hoc Stock"
    assert row["state"] in scoring.STATES
    assert row["selected"] is False
    assert pd.notna(row["stage"])
    assert pd.notna(row["cmf21"])
    assert not state_path.exists()


def test_score_ad_hoc_tickers_uses_peer_context_for_composite_scores(
    ohlcv_frame_factory,
):
    ohlcv = {
        "DRAM": ohlcv_frame_factory(start_price=95, daily_return=0.0012),
        "XLK": ohlcv_frame_factory(start_price=110, daily_return=0.0015),
        "XLF": ohlcv_frame_factory(start_price=75, daily_return=0.0004),
        "XLE": ohlcv_frame_factory(start_price=60, daily_return=-0.0002),
        "SPY": ohlcv_frame_factory(start_price=100, daily_return=0.0010),
        "BIL": ohlcv_frame_factory(start_price=90, daily_return=0.0001),
    }

    result = score_ad_hoc_tickers(["dram"], ohlcv, phase="MID")

    assert result.peer_count >= 4
    row = result.scored.loc["DRAM"]
    assert row["analysis_scope"] == "ad_hoc_peer_relative"
    assert pd.notna(row["S_score"])
    assert pd.notna(row["S_score_after_veto"])
    assert pd.notna(row["rank_in_class"])


def test_score_ad_hoc_tickers_reports_missing_market_data(ohlcv_frame_factory):
    ohlcv = {
        "SPY": ohlcv_frame_factory(start_price=100, daily_return=0.0010),
        "BIL": ohlcv_frame_factory(start_price=90, daily_return=0.0001),
    }

    result = score_ad_hoc_tickers(["ORCL"], ohlcv, phase="MID")

    assert result.scored.empty
    assert result.missing_tickers == ["ORCL"]
    assert result.warnings == ["Missing OHLCV for ad hoc ticker: ORCL"]


def test_app_wires_ad_hoc_scoring_for_ticker_and_portfolio_analyzers():
    app_source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")

    assert "from src.ad_hoc_analysis import score_ad_hoc_tickers" in app_source
    assert "def _analysis_scored_frame_for_result(result):" in app_source
    assert "score_ad_hoc_tickers(" in app_source
    assert "_analysis_scored_frame_for_result(result)" in app_source
    assert "Ad hoc methodology snapshot" in app_source
