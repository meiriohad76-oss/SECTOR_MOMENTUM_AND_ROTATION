"""Optional transition alert channels."""
from __future__ import annotations

import os
from typing import Optional

import requests


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


def send_transition_alerts(transitions: list[dict], timeout: int = 5) -> None:
    if not transitions:
        return

    text = _alert_text(transitions)
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
            pass

    if slack_webhook_url:
        try:
            response = requests.post(
                slack_webhook_url,
                json={"text": text},
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException:
            pass
