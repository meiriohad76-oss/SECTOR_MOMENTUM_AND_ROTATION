from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_wires_pnl_tracker_and_personal_trade_backtest_sections():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.pl_tracker import" in app_source
    assert "from src.personal_trades import" in app_source
    assert "def render_personal_trade_backtest():" in app_source
    assert "Personal trade backtest" in app_source
    assert 'with st.expander("Personal trade backtest", expanded=False):' in app_source
    assert "Historical provider-flow mode:" in app_source
    assert "neutral_stub" in app_source
    assert "Massive/FINRA/SEC flow did not" in app_source
    assert 'with st.expander("P&L tracker", expanded=False):' in app_source
    assert "latest_prices_from_ohlcv(ohlcv)" in app_source
    assert "evaluate_trade_history(" in app_source


def test_public_pwa_assets_are_static_and_do_not_expose_live_dashboard_state():
    public_dir = ROOT / "public"
    manifest = (public_dir / "manifest.webmanifest").read_text(encoding="utf-8")
    service_worker = (public_dir / "pwa-sw.js").read_text(encoding="utf-8")
    pwa_page = (public_dir / "pwa.html").read_text(encoding="utf-8")
    feed = (public_dir / "notification-feed.json").read_text(encoding="utf-8")

    assert '"name": "Sector Momentum Alerts"' in manifest
    assert "self.addEventListener('push'" in service_worker
    assert "notification-feed.json" in pwa_page
    assert "pushManager.subscribe" in pwa_page
    assert "vapid_public_key" in pwa_page
    assert "subscription-output" in pwa_page
    assert '"notifications": []' in feed
    combined = "\n".join([manifest, service_worker, pwa_page, feed]).lower()
    assert "api_key" not in combined
    assert "state.json" not in combined
    assert "run_journal" not in combined


def test_backlog_no_longer_has_pending_push_deploy_section():
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "## Pending push / deploy" not in backlog
    assert "B-001" in backlog
    assert "B-121" in backlog and "IMPLEMENTED" in backlog
    assert "B-131" in backlog and "IMPLEMENTED" in backlog
    assert "B-132" in backlog and "IMPLEMENTED" in backlog
