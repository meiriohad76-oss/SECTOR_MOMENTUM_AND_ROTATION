"""PWA high-severity notification helpers for B-121.

The module is intentionally provider-light. It builds deterministic push
payloads from state transitions, writes a static notification feed for the PWA
shell, and exposes a best-effort Web Push sender seam that can be enabled once
VAPID keys and browser subscriptions are configured.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit

from .alerts import HIGH_SEVERITY_STATES, format_transition_alert


WebPushFn = Callable[..., object]


@dataclass(frozen=True)
class PushSendSummary:
    attempted: int
    sent: int
    failed: int
    skipped: int


def build_push_notifications(
    transitions: Iterable[dict],
    *,
    dashboard_url: str = "/",
    max_items: int = 25,
) -> list[dict]:
    """Return browser-notification payloads for HIGH severity transitions."""
    notifications: list[dict] = []
    for transition in transitions:
        to_state = str(transition.get("to", "")).upper()
        if to_state not in HIGH_SEVERITY_STATES:
            continue
        ticker = str(transition.get("ticker", "UNKNOWN")).upper()
        date = str(transition.get("date") or "undated")
        notifications.append(
            {
                "ticker": ticker,
                "severity": "HIGH",
                "state": to_state,
                "title": f"{ticker} {to_state.replace('_', ' ')}",
                "body": format_transition_alert(transition),
                "tag": f"sector-momentum-{ticker}-{date}-{to_state}",
                "url": _ticker_url(dashboard_url, ticker),
            }
        )
        if len(notifications) >= max_items:
            break
    return notifications


def load_push_subscriptions(path: str | Path) -> list[dict]:
    """Load browser Push API subscriptions from a local JSON file."""
    subscription_path = Path(path)
    if not subscription_path.exists():
        return []
    try:
        payload = json.loads(subscription_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("subscriptions", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [row for row in rows if _valid_subscription(row)]


def write_notification_feed(
    transitions: Iterable[dict],
    path: str | Path,
    *,
    dashboard_url: str = "/",
) -> int:
    """Write the static PWA feed and return the notification count."""
    notifications = build_push_notifications(transitions, dashboard_url=dashboard_url)
    payload = {"version": 1, "notifications": notifications}
    feed_path = Path(path)
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    feed_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(notifications)


def send_web_push_notifications(
    transitions: Iterable[dict],
    subscriptions: Iterable[dict],
    *,
    webpush_fn: WebPushFn | None = None,
    vapid_private_key: str | None = None,
    vapid_claims: dict | None = None,
    dashboard_url: str = "/",
    timeout: int = 10,
) -> PushSendSummary:
    """Send HIGH severity browser push notifications with best-effort failure handling."""
    notifications = build_push_notifications(transitions, dashboard_url=dashboard_url)
    subscription_rows = [row for row in subscriptions if _valid_subscription(row)]
    if not notifications or not subscription_rows or not vapid_private_key or not vapid_claims:
        skipped = max(1, len(notifications)) * max(1, len(subscription_rows))
        return PushSendSummary(attempted=0, sent=0, failed=0, skipped=skipped)

    sender = webpush_fn or _import_webpush()
    if sender is None:
        return PushSendSummary(
            attempted=0,
            sent=0,
            failed=0,
            skipped=len(notifications) * len(subscription_rows),
        )

    attempted = sent = failed = 0
    for notification in notifications:
        data = json.dumps(notification, sort_keys=True)
        for subscription in subscription_rows:
            attempted += 1
            try:
                sender(
                    subscription,
                    data=data,
                    vapid_private_key=vapid_private_key,
                    vapid_claims=vapid_claims,
                    timeout=timeout,
                )
                sent += 1
            except Exception:
                failed += 1
    return PushSendSummary(attempted=attempted, sent=sent, failed=failed, skipped=0)


def _valid_subscription(value) -> bool:
    if not isinstance(value, dict):
        return False
    keys = value.get("keys")
    return bool(
        value.get("endpoint")
        and isinstance(keys, dict)
        and keys.get("p256dh")
        and keys.get("auth")
    )


def _ticker_url(dashboard_url: str, ticker: str) -> str:
    base = (dashboard_url or "/").rstrip("/")
    if not base:
        base = "/"
    parts = urlsplit(base)
    if parts.scheme and parts.netloc and not parts.path:
        base = f"{base}/"
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}ticker={ticker}"


def _import_webpush() -> WebPushFn | None:
    try:
        from pywebpush import webpush  # type: ignore
    except Exception:
        return None
    return webpush
