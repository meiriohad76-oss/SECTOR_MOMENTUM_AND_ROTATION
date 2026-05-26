from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import scoring
from src.ad_hoc_analysis import score_ad_hoc_tickers


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
