from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest
import requests

from src import flow
from src.alerts import (
    discord_mattermost_webhook_status,
    send_discord_mattermost_test_alert,
    send_telegram_slack_test_alert,
    telegram_slack_alert_status,
)
from src.data import _fetch_massive_ohlcv, _resolve_secret


LIVE_FLAG = "RUN_LIVE_INTEGRATION_SMOKE"
ROOT = Path(__file__).resolve().parent.parent


def _skip_unless_live_enabled():
    if os.environ.get(LIVE_FLAG, "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip(f"set {LIVE_FLAG}=1 to run live provider smoke tests")


def _configured_secret(name: str) -> str | None:
    value = _resolve_secret(name)
    if value:
        return value
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None
    try:
        parsed = tomllib.loads(secrets_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    raw = parsed.get(name)
    text = str(raw).strip() if raw is not None else ""
    return text or None


def test_live_massive_ohlcv_smoke_fetches_recent_bars_without_printing_key():
    _skip_unless_live_enabled()
    key = _configured_secret("MASSIVE_API_KEY")
    if not key:
        pytest.skip("MASSIVE_API_KEY is not configured")

    os.environ["MASSIVE_API_KEY"] = key
    os.environ["MASSIVE_VERIFY_SSL"] = _configured_secret("MASSIVE_VERIFY_SSL") or "true"
    result = _fetch_massive_ohlcv(["SPY"], period="2mo")

    assert "SPY" in result.data
    assert len(result.data["SPY"]) > 30


def test_live_finra_public_flow_smoke_returns_records_or_empty_lists():
    _skip_unless_live_enabled()

    ats = flow._fetch_finra_ats_weekly_summary("SPY", limit=5, timeout=20)
    short_interest = flow._fetch_finra_short_interest("SPY", limit=2, timeout=20)

    assert isinstance(ats, list)
    assert isinstance(short_interest, list)


def test_live_cloudflare_route_smoke_reaches_protected_dashboard():
    _skip_unless_live_enabled()
    url = os.environ.get(
        "CLOUDFLARE_DASHBOARD_URL",
        "https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK",
    )

    response = requests.get(url, timeout=20, allow_redirects=False)

    assert response.status_code in {200, 302, 401, 403}


def test_live_alert_smoke_is_dry_run_unless_explicit_send_enabled():
    _skip_unless_live_enabled()

    telegram_slack = telegram_slack_alert_status()
    discord_mattermost = discord_mattermost_webhook_status()
    assert set(telegram_slack) >= {"telegram", "slack"}
    assert set(discord_mattermost) >= {"discord", "mattermost"}

    if os.environ.get("LIVE_ALERT_SEND", "").strip().lower() in {"1", "true", "yes", "on"}:
        message = os.environ.get("LIVE_ALERT_MESSAGE", "Sector dashboard live integration smoke")
        sent_a = send_telegram_slack_test_alert(message, timeout=10)
        sent_b = send_discord_mattermost_test_alert(message, timeout=10)
        assert set(sent_a) == {"telegram", "slack"}
        assert set(sent_b) == {"discord", "mattermost"}
