from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from src import fred_data
from src.macro_tiles import FRED_CONTEXT_GROUPS


def test_resolve_api_key_prefers_environment(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "env-secret")
    monkeypatch.setitem(
        sys.modules,
        "streamlit",
        SimpleNamespace(secrets={"FRED_API_KEY": "streamlit-secret"}),
    )

    assert fred_data._resolve_api_key() == "env-secret"


def test_fred_series_cover_expanded_macro_context():
    context_series = {
        item["id"]
        for group in FRED_CONTEXT_GROUPS
        for item in group["series"]
    }

    assert context_series.issubset(fred_data.FRED_SERIES)


def test_fetch_fred_uses_injected_client_and_skips_bad_series(monkeypatch):
    calls = []

    class FakeFred:
        def __init__(self, api_key):
            self.api_key = api_key

        def get_series(self, series_id, observation_start):
            calls.append((self.api_key, series_id, observation_start))
            if series_id == "T10Y3M":
                raise RuntimeError("temporary provider error")
            return pd.Series([1.0, None, 3.0], index=pd.date_range("2026-01-01", periods=3))

    monkeypatch.setenv("FRED_API_KEY", "fred-secret")

    out = fred_data.fetch_fred(start_date="2020-01-01", client_factory=FakeFred)

    assert "T10Y2Y" in out
    assert "T10Y3M" not in out
    assert out["T10Y2Y"].tolist() == [1.0, 3.0]
    assert calls[0] == ("fred-secret", "T10Y2Y", "2020-01-01")


def test_fetch_fred_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(fred_data, "_resolve_api_key", lambda: None)

    def fail_factory(api_key):
        raise AssertionError("missing key should not build a FRED client")

    assert fred_data.fetch_fred(client_factory=fail_factory) == {}
