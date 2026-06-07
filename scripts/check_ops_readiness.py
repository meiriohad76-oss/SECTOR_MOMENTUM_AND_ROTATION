"""Report production and optional integration readiness without printing secrets."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.broker_config import broker_config_status  # noqa: E402
from src.config_resolver import resolve_config_value  # noqa: E402
from src.pwa_push import load_push_subscriptions  # noqa: E402
from src.provider_flow_cache import DEFAULT_CACHE_DB_PATH as DEFAULT_PROVIDER_FLOW_CACHE_PATH  # noqa: E402
from src.provider_flow_cache import provider_flow_cache_coverage, provider_flow_cache_status  # noqa: E402
from src.provider_snapshots import DEFAULT_SNAPSHOT_DB_PATH  # noqa: E402
from src.run_journal import DEFAULT_JOURNAL_PATH  # noqa: E402
from src.scoring import STATE_FILE, _transition_journal_path  # noqa: E402
from src.universe import US_SECTORS  # noqa: E402


REQUIRED_PROVIDER_FLOW_CACHE_LANES = (
    "massive_block_trades",
    "finra_ats_dark_pool",
    "finra_short_interest",
)


def _label(value: str | None) -> str:
    return "configured" if value else "missing"


def _flag_value(name: str, default: bool) -> tuple[bool, str]:
    raw = resolve_config_value(name)
    if raw is None:
        return default, "default"
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True, "configured"
    if normalized in {"0", "false", "no", "off"}:
        return False, "configured"
    return default, "invalid"


def _sqlite_count(path: Path, table: str) -> int | None:
    if not path.exists() or path.stat().st_size <= 0:
        return None
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else None


def _systemctl_user(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    output = (completed.stdout or completed.stderr or "").strip()
    return output or None


def _file_status(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def _parse_utc_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_state_status(path: Path, journal_path: Path) -> dict[str, object]:
    by_ticker_count = 0
    snapshot_transition_count = 0
    state_updated = ""
    if path.exists() and path.stat().st_size > 0:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            by_ticker_count = len(payload.get("by_ticker", {}) or {})
            snapshot_transition_count = len(payload.get("transitions", []) or [])
            state_updated = str(payload.get("updated", "") or "")
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    journal_transition_count = 0
    if journal_path.exists() and journal_path.stat().st_size > 0:
        try:
            journal_transition_count = sum(
                1 for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()
            )
        except OSError:
            journal_transition_count = 0

    parsed_state_updated = _parse_utc_timestamp(state_updated)
    state_updated_age_seconds = None
    if parsed_state_updated is not None:
        state_updated_age_seconds = int((datetime.now(timezone.utc) - parsed_state_updated).total_seconds())

    if not state_updated:
        freshness_state = "missing"
    elif state_updated_age_seconds is not None and state_updated_age_seconds > 84 * 60 * 60:
        freshness_state = "stale"
    else:
        freshness_state = "fresh"

    state_file = _file_status(path)
    transition_journal = _file_status(journal_path)
    return {
        "state_file": state_file,
        "transition_journal": transition_journal,
        "state_updated": state_updated,
        "state_updated_age_seconds": state_updated_age_seconds,
        "freshness_state": freshness_state,
        "by_ticker_count": by_ticker_count,
        "snapshot_transition_count": snapshot_transition_count,
        "journal_transition_count": journal_transition_count,
        "state": "ready" if state_file["exists"] and by_ticker_count > 0 else "missing_or_empty",
        "transitions": "ready" if transition_journal["exists"] else "missing",
    }


def _ohlcv_provider_status() -> dict[str, object]:
    selected = (resolve_config_value("OHLCV_PROVIDER") or "yfinance").strip().lower()
    massive_key = resolve_config_value("MASSIVE_API_KEY")
    ssl_raw = resolve_config_value("MASSIVE_VERIFY_SSL")
    ssl_status = "missing_default_true"
    if ssl_raw is not None:
        ssl_status = "configured_true" if ssl_raw.strip().lower() in {"1", "true", "yes", "on"} else "warning"

    if selected in {"massive", "polygon"} and not massive_key:
        provider_state = "missing_config"
    elif selected == "auto" and not massive_key:
        provider_state = "fallback_yfinance"
    else:
        provider_state = "configured"

    return {
        "provider": "massive" if selected == "polygon" else selected,
        "state": provider_state,
        "massive_api_key": _label(massive_key),
        "massive_verify_ssl": ssl_status,
    }


def _provider_lane_status(flag_name: str, required_config: list[str] | None = None) -> dict[str, object]:
    stubbed, source = _flag_value(flag_name, True)
    if source == "invalid":
        return {"state": "warning", "mode": "stubbed", "flag": "invalid"}
    if stubbed:
        return {"state": "stubbed", "mode": "neutral", "flag": source}
    required = required_config or []
    missing = [name for name in required if not resolve_config_value(name)]
    if missing:
        return {"state": "missing_config", "mode": "live_requested", "missing": missing}
    return {"state": "live_configured", "mode": "live_requested"}


def _provider_flow_status() -> dict[str, object]:
    return {
        "etf_primary_flow": _provider_lane_status("FLOW_STUB_MODE", ["MASSIVE_API_KEY"]),
        "massive_block_trades": _provider_lane_status("MASSIVE_TRADES_STUB_MODE", ["MASSIVE_API_KEY"]),
        "finra_ats_dark_pool": _provider_lane_status("FINRA_ATS_STUB_MODE"),
        "finra_short_interest": _provider_lane_status("FINRA_SHORT_INTEREST_STUB_MODE"),
        "sec_13f": _provider_lane_status("SEC_13F_STUB_MODE", ["SEC_13F_DATA_URL", "SEC_USER_AGENT"]),
    }


def _browser_qa_fixture_guard() -> dict[str, str]:
    allow_fixtures, source = _flag_value("BROWSER_QA_ALLOW_FIXTURES", False)
    return {
        "state": "unsafe_enabled" if allow_fixtures else "safe",
        "flag": source,
    }


def _user_timer_status(unit_dir: Path, *, service: str, timer: str) -> dict[str, object]:
    service_path = unit_dir / service
    timer_path = unit_dir / timer
    enabled = _systemctl_user(["is-enabled", timer])
    active = _systemctl_user(["is-active", timer])
    service_result = _systemctl_user(["show", service, "-p", "Result", "--value"])
    service_exit_status = _systemctl_user(["show", service, "-p", "ExecMainStatus", "--value"])
    installed = service_path.exists() and timer_path.exists()
    systemctl_available = enabled is not None or active is not None
    ready = installed and enabled in {"enabled", "enabled-runtime"} and active == "active"
    if ready:
        state = "ready"
    elif installed and not systemctl_available:
        state = "installed_not_verified"
    elif installed:
        state = "installed_not_active"
    else:
        state = "missing"
    return {
        "state": state,
        "service": service,
        "timer": timer,
        "service_installed": service_path.exists(),
        "timer_installed": timer_path.exists(),
        "timer_enabled": enabled or "unknown",
        "timer_active": active or "unknown",
        "last_service_result": service_result or "unknown",
        "last_service_exit_status": service_exit_status or "unknown",
    }


def _ready_or_missing(paths: list[Path]) -> str:
    return "ready" if all(path.exists() and path.stat().st_size > 0 for path in paths) else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscriptions-path", default=str(ROOT / "data" / "pwa_push_subscriptions.json"))
    parser.add_argument("--feed-dir", default=str(ROOT / "data" / "feeds"))
    parser.add_argument("--public-feed-dir", default=str(ROOT / "public" / "feeds"))
    parser.add_argument("--state-file", default=str(STATE_FILE))
    parser.add_argument("--state-transition-journal", default=str(_transition_journal_path()))
    parser.add_argument("--run-journal-path", default=str(DEFAULT_JOURNAL_PATH))
    parser.add_argument("--provider-snapshot-db", default=str(DEFAULT_SNAPSHOT_DB_PATH))
    parser.add_argument("--provider-flow-cache-db", default=str(DEFAULT_PROVIDER_FLOW_CACHE_PATH))
    parser.add_argument("--ohlcv-cache-path", default=str(ROOT / "data_cache" / "ohlcv.duckdb"))
    parser.add_argument("--user-systemd-dir", default=str(Path.home() / ".config" / "systemd" / "user"))
    parser.add_argument(
        "--strict-production",
        action="store_true",
        help="Exit non-zero when critical production readiness checks are not ready.",
    )
    return parser.parse_args(argv)


def _broker_status() -> dict:
    provider = resolve_config_value("BROKER_PROVIDER") or "none"
    status = broker_config_status(provider, resolver=resolve_config_value)
    return {
        "provider": status.provider,
        "broker_config": status.state,
        "configured": status.configured,
        "missing": status.missing,
        "live_connectivity": status.live_connectivity,
    }


def _require(
    failures: list[dict[str, str]],
    condition: bool,
    check_id: str,
    detail: str,
) -> None:
    if not condition:
        failures.append({"id": check_id, "detail": detail})


def _strict_production_failures(payload: dict[str, object]) -> list[dict[str, str]]:
    production = dict(payload.get("production", {}) or {})
    failures: list[dict[str, str]] = []

    ohlcv = dict(production.get("ohlcv_provider", {}) or {})
    _require(
        failures,
        ohlcv.get("state") == "configured",
        "ohlcv_provider",
        f"OHLCV provider state is {ohlcv.get('state')}",
    )
    _require(
        failures,
        ohlcv.get("massive_verify_ssl") == "configured_true",
        "massive_verify_ssl",
        f"Massive SSL state is {ohlcv.get('massive_verify_ssl')}",
    )

    fred = dict(production.get("fred", {}) or {})
    _require(failures, fred.get("api_key") == "configured", "fred", "FRED API key is not configured")

    provider_flow = dict(production.get("provider_flow", {}) or {})
    for lane in ("massive_block_trades", "finra_ats_dark_pool", "finra_short_interest"):
        lane_status = dict(provider_flow.get(lane, {}) or {})
        _require(
            failures,
            lane_status.get("state") == "live_configured",
            f"provider_flow.{lane}",
            f"{lane} state is {lane_status.get('state')}",
        )

    state = dict(production.get("state_persistence", {}) or {})
    _require(
        failures,
        state.get("state") == "ready",
        "state_persistence",
        f"state persistence is {state.get('state')}",
    )
    _require(
        failures,
        state.get("freshness_state") == "fresh",
        "state_freshness",
        f"state freshness is {state.get('freshness_state')}",
    )
    _require(
        failures,
        state.get("transitions") == "ready",
        "transition_journal",
        f"transition journal state is {state.get('transitions')}",
    )
    state_timer = dict(state.get("refresh_timer", {}) or {})
    _require(
        failures,
        state_timer.get("state") == "ready",
        "state_refresh_timer",
        f"state refresh timer is {state_timer.get('state')}",
    )

    run_journal = dict(production.get("run_journal", {}) or {})
    _require(
        failures,
        run_journal.get("state") == "ready",
        "run_journal",
        f"run journal state is {run_journal.get('state')}",
    )

    snapshots = dict(production.get("provider_snapshots", {}) or {})
    _require(
        failures,
        snapshots.get("state") == "ready",
        "provider_snapshots",
        f"provider snapshots state is {snapshots.get('state')}",
    )
    snapshot_timer = dict(snapshots.get("capture_timer", {}) or {})
    _require(
        failures,
        snapshot_timer.get("state") == "ready",
        "provider_snapshot_timer",
        f"provider snapshot timer is {snapshot_timer.get('state')}",
    )

    flow_cache = dict(production.get("provider_flow_cache", {}) or {})
    _require(
        failures,
        flow_cache.get("state") == "ready",
        "provider_flow_cache",
        f"provider-flow cache state is {flow_cache.get('state')}",
    )
    us_sector_coverage = dict(flow_cache.get("us_sector_coverage", {}) or {})
    _require(
        failures,
        us_sector_coverage.get("state") == "ready",
        "provider_flow_cache.us_sector_coverage",
        (
            "US-sector provider-flow cache coverage is "
            f"{us_sector_coverage.get('covered_pair_count')}/"
            f"{us_sector_coverage.get('expected_pair_count')} with "
            f"{us_sector_coverage.get('missing_pair_count')} missing pairs"
        ),
    )
    warmup_timer = dict(flow_cache.get("warmup_timer", {}) or {})
    _require(
        failures,
        warmup_timer.get("state") == "ready",
        "provider_flow_cache_timer",
        f"provider-flow cache warmup timer is {warmup_timer.get('state')}",
    )

    ohlcv_cache = dict(production.get("ohlcv_cache", {}) or {})
    _require(
        failures,
        ohlcv_cache.get("state") == "ready",
        "ohlcv_cache",
        f"OHLCV cache state is {ohlcv_cache.get('state')}",
    )

    browser_guard = dict(production.get("browser_qa_fixture_guard", {}) or {})
    _require(
        failures,
        browser_guard.get("state") == "safe",
        "browser_qa_fixture_guard",
        f"browser QA fixture guard is {browser_guard.get('state')}",
    )
    return failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    subscriptions = load_push_subscriptions(args.subscriptions_path)
    feed_dir = Path(args.feed_dir)
    public_feed_dir = Path(args.public_feed_dir)
    run_journal_path = Path(args.run_journal_path)
    provider_snapshot_db = Path(args.provider_snapshot_db)
    provider_flow_cache_db = Path(args.provider_flow_cache_db)
    ohlcv_cache_path = Path(args.ohlcv_cache_path)
    user_systemd_dir = Path(args.user_systemd_dir)
    run_count = _sqlite_count(run_journal_path, "runs")
    snapshot_count = _sqlite_count(provider_snapshot_db, "provider_snapshots")

    payload = {
        "production": {
            "ohlcv_provider": _ohlcv_provider_status(),
            "fred": {"api_key": _label(resolve_config_value("FRED_API_KEY"))},
            "provider_flow": _provider_flow_status(),
            "state_persistence": {
                **_json_state_status(Path(args.state_file), Path(args.state_transition_journal)),
                "refresh_timer": _user_timer_status(
                    user_systemd_dir,
                    service="sector-dashboard-state-refresh.service",
                    timer="sector-dashboard-state-refresh.timer",
                ),
            },
            "run_journal": {
                **_file_status(run_journal_path),
                "runs": run_count,
                "state": "ready" if run_count and run_count > 0 else "missing_or_empty",
            },
            "provider_snapshots": {
                **_file_status(provider_snapshot_db),
                "snapshots": snapshot_count,
                "state": "ready" if snapshot_count and snapshot_count > 0 else "missing_or_empty",
                "capture_timer": _user_timer_status(
                    user_systemd_dir,
                    service="sector-massive-provider-snapshots.service",
                    timer="sector-massive-provider-snapshots.timer",
                ),
            },
            "provider_flow_cache": {
                **provider_flow_cache_status(provider_flow_cache_db),
                "us_sector_coverage": provider_flow_cache_coverage(
                    tickers=US_SECTORS,
                    lanes=REQUIRED_PROVIDER_FLOW_CACHE_LANES,
                    path=provider_flow_cache_db,
                ),
                "warmup_timer": _user_timer_status(
                    user_systemd_dir,
                    service="sector-provider-flow-cache.service",
                    timer="sector-provider-flow-cache.timer",
                ),
            },
            "ohlcv_cache": {
                **_file_status(ohlcv_cache_path),
                "state": "ready" if ohlcv_cache_path.exists() and ohlcv_cache_path.stat().st_size > 0 else "missing",
            },
            "browser_qa_fixture_guard": _browser_qa_fixture_guard(),
        },
        "B-021": {
            "telegram": "configured"
            if resolve_config_value("TELEGRAM_BOT_TOKEN") and resolve_config_value("TELEGRAM_CHAT_ID")
            else "missing",
            "slack": _label(resolve_config_value("SLACK_WEBHOOK_URL")),
        },
        "B-120": {
            "smtp_delivery": "configured"
            if resolve_config_value("SMTP_HOST") and resolve_config_value("EMAIL_DIGEST_TO")
            else "missing",
            "smtp_host": _label(resolve_config_value("SMTP_HOST")),
            "email_digest_to": _label(resolve_config_value("EMAIL_DIGEST_TO")),
        },
        "B-121": {
            "vapid_private_key": _label(resolve_config_value("VAPID_PRIVATE_KEY")),
            "vapid_public_key": _label(resolve_config_value("VAPID_PUBLIC_KEY")),
            "vapid_claim_email": _label(resolve_config_value("VAPID_CLAIM_EMAIL")),
            "subscriptions": len(subscriptions),
            "pywebpush": "available" if importlib.util.find_spec("pywebpush") else "missing",
        },
        "B-122": {
            "feed_artifacts": _ready_or_missing([feed_dir / "transitions.rss", feed_dir / "transitions.ics"]),
            "public_feed_artifacts": _ready_or_missing(
                [public_feed_dir / "transitions.rss", public_feed_dir / "transitions.ics"]
            ),
        },
        "B-123": {
            "discord": _label(resolve_config_value("DISCORD_WEBHOOK_URL")),
            "mattermost": _label(resolve_config_value("MATTERMOST_WEBHOOK_URL")),
        },
        "B-131": _broker_status(),
    }
    failures = _strict_production_failures(payload)
    payload["strict_production"] = {
        "ok": not failures,
        "failures": failures,
        "enforced": bool(args.strict_production),
    }
    print(json.dumps(payload, sort_keys=True))
    return 2 if args.strict_production and failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
