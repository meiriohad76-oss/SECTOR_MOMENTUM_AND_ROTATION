"""Structured JSON logging with optional HTTP shipping."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
from threading import Thread
from typing import Any, Mapping

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = ROOT / "data" / "logs" / "app.jsonl"
DEFAULT_LOGGER_NAME = "sector_momentum"
SUPPORTED_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _resolve_secret(name: str) -> str | None:
    if name in os.environ:
        return os.environ.get(name, "").strip()
    try:
        import streamlit as st  # type: ignore
        from streamlit.errors import StreamlitSecretNotFoundError  # type: ignore

        if hasattr(st, "secrets"):
            try:
                secret = st.secrets.get(name)
                if secret is not None:
                    text = str(secret).strip()
                    if text:
                        return text
            except (KeyError, StreamlitSecretNotFoundError):
                pass
    except ImportError:
        pass
    return None


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if bool(value != value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): cleaned for key, item in value.items() if (cleaned := _clean_value(item)) is not None}
    if isinstance(value, (list, tuple)):
        return [cleaned for item in value if (cleaned := _clean_value(item)) is not None]
    return value


def _clean_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): cleaned for key, value in fields.items() if (cleaned := _clean_value(value)) is not None}


class JsonLineFormatter(logging.Formatter):
    """Format LogRecords as one compact JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_clean_fields(getattr(record, "structured_fields", {}) or {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class HttpJsonLogHandler(logging.Handler):
    """Best-effort JSON log shipper for generic HTTP ingestion endpoints."""

    _structured_logging_handler = True

    def __init__(self, url: str, token: str | None = None, timeout: int = 2, async_mode: bool = True):
        super().__init__()
        self.url = url
        self.token = token
        self.timeout = timeout
        self.async_mode = async_mode

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.loads(self.format(record))
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            if self.async_mode:
                Thread(target=self._post_payload, args=(payload, headers), daemon=True).start()
            else:
                self._post_payload(payload, headers)
        except Exception:
            self.handleError(record)

    def _post_payload(self, payload: dict[str, Any], headers: dict[str, str]) -> None:
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except Exception:
            return


def _level_number(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    normalized = str(level or _resolve_secret("LOG_LEVEL") or "INFO").strip().upper()
    if normalized not in SUPPORTED_LEVELS:
        raise ValueError(f"Unsupported log level: {level}")
    return SUPPORTED_LEVELS[normalized]


def _configured_log_path(log_path: str | Path | None) -> Path:
    configured = log_path or _resolve_secret("STRUCTURED_LOG_PATH") or DEFAULT_LOG_PATH
    return Path(configured)


def configure_structured_logging(
    logger_name: str = DEFAULT_LOGGER_NAME,
    *,
    log_path: str | Path | None = None,
    ship_url: str | None = None,
    ship_token: str | None = None,
    level: str | int | None = None,
) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(_level_number(level))
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_structured_logging_handler", False):
            logger.removeHandler(handler)
            handler.close()

    formatter = JsonLineFormatter()
    path = _configured_log_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler._structured_logging_handler = True
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logger.level)
    logger.addHandler(file_handler)

    url = _resolve_secret("LOG_SHIP_URL") if ship_url is None else ship_url
    if url:
        token = _resolve_secret("LOG_SHIP_TOKEN") if ship_token is None else ship_token
        http_handler = HttpJsonLogHandler(str(url), token=token)
        http_handler.setFormatter(formatter)
        http_handler.setLevel(logger.level)
        logger.addHandler(http_handler)

    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: str | int = "INFO",
    message: str | None = None,
    **fields: Any,
) -> None:
    levelno = _level_number(level)
    structured_fields = {"event": event, **fields}
    logger.log(levelno, message or event, extra={"structured_fields": structured_fields})
