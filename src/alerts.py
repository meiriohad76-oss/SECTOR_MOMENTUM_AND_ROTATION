"""Optional transition alert channels."""
from __future__ import annotations

from datetime import datetime, timedelta
from email.message import EmailMessage
import os
import smtplib
from typing import Optional
from zoneinfo import ZoneInfo

import requests

HIGH_SEVERITY_STATES = {"EXIT", "BEARISH_STAGE_4"}
EASTERN_TZ = ZoneInfo("America/New_York")
DISCORD_MATTERMOST_WEBHOOKS = {
    "discord": ("DISCORD_WEBHOOK_URL", "content"),
    "mattermost": ("MATTERMOST_WEBHOOK_URL", "text"),
}


def _resolve_secret(name: str) -> Optional[str]:
    try:
        import streamlit as st  # type: ignore
        from streamlit.errors import StreamlitSecretNotFoundError  # type: ignore

        if hasattr(st, "secrets"):
            try:
                value = st.secrets.get(name)
                if value:
                    return str(value).strip()
            except (KeyError, StreamlitSecretNotFoundError):
                pass
    except ImportError:
        pass
    value = os.environ.get(name)
    return value.strip() if value else None


def format_transition_alert(transition: dict) -> str:
    ticker = str(transition.get("ticker", "UNKNOWN")).upper()
    from_state = str(transition.get("from", "UNKNOWN"))
    to_state = str(transition.get("to", "UNKNOWN"))
    date = transition.get("date")
    suffix = f" on {date}" if date else ""
    return f"{ticker} transitioned {from_state} -> {to_state}{suffix}"


def _alert_text(transitions: list[dict]) -> str:
    lines = [format_transition_alert(transition) for transition in transitions]
    return "\n".join(lines)


def _split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _secret_bool(name: str, default: bool = True) -> bool:
    value = _resolve_secret(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _secret_int(name: str, default: int) -> int:
    value = _resolve_secret(name)
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def digest_date_for_now(now: datetime | None = None) -> str:
    current = now or datetime.now(EASTERN_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=EASTERN_TZ)
    current_et = current.astimezone(EASTERN_TZ)
    return (current_et.date() - timedelta(days=1)).isoformat()


def low_severity_digest_transitions(
    transitions: list[dict],
    *,
    now: datetime | None = None,
    digest_date: str | None = None,
) -> list[dict]:
    target_date = digest_date or digest_date_for_now(now)
    digest_rows = []
    for transition in transitions:
        to_state = str(transition.get("to", "")).upper()
        if transition.get("date") != target_date:
            continue
        if to_state in HIGH_SEVERITY_STATES:
            continue
        digest_rows.append(dict(transition))
    return digest_rows


def format_email_digest(transitions: list[dict], *, digest_date: str) -> dict[str, str]:
    subject = f"Sector Momentum LOW transition digest - {digest_date}"
    lines = [format_transition_alert(transition) for transition in transitions]
    body = "\n".join(
        [
            f"LOW severity transitions for {digest_date}",
            "",
            *(f"- {line}" for line in lines),
            "",
            "High severity EXIT and BEARISH_STAGE_4 transitions are routed through immediate alert channels.",
        ]
    )
    return {"subject": subject, "body": body}


def send_low_severity_email_digest(
    transitions: list[dict],
    *,
    now: datetime | None = None,
    timeout: int = 10,
) -> bool:
    digest_date = digest_date_for_now(now)
    digest_rows = low_severity_digest_transitions(transitions, digest_date=digest_date)
    if not digest_rows:
        return False

    host = _resolve_secret("SMTP_HOST")
    recipients = _split_recipients(_resolve_secret("EMAIL_DIGEST_TO"))
    username = _resolve_secret("SMTP_USERNAME")
    password = _resolve_secret("SMTP_PASSWORD")
    sender = _resolve_secret("EMAIL_DIGEST_FROM") or username
    if not host or not sender or not recipients:
        return False

    digest = format_email_digest(digest_rows, digest_date=digest_date)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = digest["subject"]
    message.set_content(digest["body"])

    try:
        with smtplib.SMTP(host, _secret_int("SMTP_PORT", 587), timeout=timeout) as smtp:
            if _secret_bool("SMTP_STARTTLS", True):
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        return False
    return True


def telegram_slack_alert_status() -> dict[str, bool]:
    telegram_token = _resolve_secret("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = _resolve_secret("TELEGRAM_CHAT_ID")
    slack_webhook_url = _resolve_secret("SLACK_WEBHOOK_URL")
    return {"telegram": bool(telegram_token and telegram_chat_id), "slack": bool(slack_webhook_url)}


def send_telegram_slack_test_alert(text: str, timeout: int = 5) -> dict[str, str]:
    results: dict[str, str] = {}
    telegram_token = _resolve_secret("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = _resolve_secret("TELEGRAM_CHAT_ID")
    slack_webhook_url = _resolve_secret("SLACK_WEBHOOK_URL")

    if telegram_token and telegram_chat_id:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": telegram_chat_id, "text": text},
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException:
            results["telegram"] = "failed"
        else:
            results["telegram"] = "sent"
    else:
        results["telegram"] = "skipped"

    if slack_webhook_url:
        try:
            response = requests.post(slack_webhook_url, json={"text": text}, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            results["slack"] = "failed"
        else:
            results["slack"] = "sent"
    else:
        results["slack"] = "skipped"

    return results


def discord_mattermost_webhook_status() -> dict[str, bool]:
    return {
        name: bool(_resolve_secret(secret_name))
        for name, (secret_name, _payload_key) in DISCORD_MATTERMOST_WEBHOOKS.items()
    }


def send_discord_mattermost_test_alert(text: str, timeout: int = 5) -> dict[str, str]:
    results: dict[str, str] = {}
    for name, (secret_name, payload_key) in DISCORD_MATTERMOST_WEBHOOKS.items():
        webhook_url = _resolve_secret(secret_name)
        if not webhook_url:
            results[name] = "skipped"
            continue
        try:
            response = requests.post(webhook_url, json={payload_key: text}, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            results[name] = "failed"
        else:
            results[name] = "sent"
    return results


def send_transition_alerts(transitions: list[dict], timeout: int = 5) -> None:
    if not transitions:
        return

    text = _alert_text(transitions)
    send_telegram_slack_test_alert(text, timeout=timeout)
    send_discord_mattermost_test_alert(text, timeout=timeout)
