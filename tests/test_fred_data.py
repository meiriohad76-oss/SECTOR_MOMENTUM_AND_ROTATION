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
            return pd.Series(
                [3.0, 1.0, 4.0, None],
                index=pd.to_datetime(["2026-01-03", "2026-01-01", "2026-01-03", "2026-01-02"]),
            )

    monkeypatch.setenv("FRED_API_KEY", "fred-secret")

    out = fred_data.fetch_fred(start_date="2020-01-01", client_factory=FakeFred)

    assert "T10Y2Y" in out
    assert "T10Y3M" not in out
    assert out["T10Y2Y"].index.tolist() == list(pd.to_datetime(["2026-01-01", "2026-01-03"]))
    assert out["T10Y2Y"].tolist() == [1.0, 4.0]
    assert calls[0] == ("fred-secret", "T10Y2Y", "2020-01-01")
    diagnostics = fred_data.fred_fetch_diagnostics()
    assert diagnostics["status"] == "partial"
    assert diagnostics["configured"] is True
    assert diagnostics["series_loaded"] == len(fred_data.FRED_SERIES) - 1
    assert diagnostics["series_failed"] == 1
    assert diagnostics["errors"] == ["T10Y3M: RuntimeError"]


def test_fetch_fred_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(fred_data, "_resolve_api_key", lambda: None)

    def fail_factory(api_key):
        raise AssertionError("missing key should not build a FRED client")

    assert fred_data.fetch_fred(client_factory=fail_factory) == {}
    assert fred_data.fred_fetch_diagnostics()["status"] == "missing_key"


def test_fetch_fred_records_client_error_without_leaking_key(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "fred-secret")

    def fail_factory(api_key):
        raise RuntimeError(f"bad secret {api_key}")

    assert fred_data.fetch_fred(client_factory=fail_factory) == {}
    diagnostics = fred_data.fred_fetch_diagnostics()

    assert diagnostics["status"] == "client_error"
    assert diagnostics["configured"] is True
    assert diagnostics["errors"] == ["client: RuntimeError"]
    assert "fred-secret" not in str(diagnostics)
