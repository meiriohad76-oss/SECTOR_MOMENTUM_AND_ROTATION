from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_dashboard_scoring_into_run_journal():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "APP_VERSION =" in app_source
    assert "append_dashboard_run" in app_source
    assert "dashboard_run_fingerprint" in app_source
    assert "DEFAULT_JOURNAL_PATH" in app_source
    assert (
        "def _record_dashboard_run(scored_df, bluf_payload, regime_obj, transitions_rows, "
        "ohlcv_payload, ohlcv_result_obj, fred_snapshot)"
    ) in app_source
    assert "fred_macro_snapshot(_fred_data)" in app_source
    assert "_record_dashboard_run(scored, bluf, regime, transitions, ohlcv, ohlcv_result, fred_macro_snapshot(_fred_data))" in app_source
    assert '"fred_macro_snapshot": fred_snapshot' in app_source
    assert '"ohlcv_provider": provider' in app_source
    assert '"fresh_cache_hit_count": len(getattr(ohlcv_result_obj, "fresh_cache_hits", ()) or ())' in app_source
    assert '"stale_cache_hit_count": len(getattr(ohlcv_result_obj, "stale_cache_hits", ()) or ())' in app_source
    assert '"cache_refresh_forced": bool(getattr(ohlcv_result_obj, "cache_refresh_forced", False))' in app_source
    assert "run_journal_last_fingerprint" in app_source
    assert app_source.index('st.session_state.get("run_journal_last_fingerprint")') < app_source.index(
        "append_dashboard_run("
    )
    assert "st.session_state.run_journal_last_fingerprint = fingerprint" in app_source
    assert "dedupe_content=True" in app_source
    assert "result.skipped_duplicate" in app_source
    assert app_source.index("bluf = _build_bluf(scored)") < app_source.index(
        "_record_dashboard_run(scored, bluf, regime, transitions, ohlcv, ohlcv_result, fred_macro_snapshot(_fred_data))"
    )
