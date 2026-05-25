from __future__ import annotations

import json
import logging
import sys
from types import SimpleNamespace

import pytest

from src import structured_logging


def test_configured_logger_writes_json_lines_with_context(tmp_path):
    log_path = tmp_path / "app.jsonl"
    logger = structured_logging.configure_structured_logging(
        logger_name="test-json-lines",
        log_path=log_path,
        ship_url="",
    )

    structured_logging.log_event(
        logger,
        "dashboard_run_recorded",
        run_id="run-1",
        ticker_count=12,
        provider="yfinance",
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test-json-lines"
    assert payload["event"] == "dashboard_run_recorded"
    assert payload["message"] == "dashboard_run_recorded"
    assert payload["run_id"] == "run-1"
    assert payload["ticker_count"] == 12
    assert payload["provider"] == "yfinance"
    assert "timestamp" in payload


def test_configure_structured_logging_is_idempotent(tmp_path):
    log_path = tmp_path / "app.jsonl"

    first = structured_logging.configure_structured_logging(
        logger_name="test-idempotent",
        log_path=log_path,
        ship_url="",
    )
    second = structured_logging.configure_structured_logging(
        logger_name="test-idempotent",
        log_path=log_path,
        ship_url="",
    )

    assert first is second
    assert len([handler for handler in second.handlers if getattr(handler, "_structured_logging_handler", False)]) == 1

    structured_logging.log_event(second, "single_line")

    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_http_log_shipping_posts_json_and_ignores_errors(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(
        structured_logging,
        "requests",
        SimpleNamespace(post=fake_post, RequestException=RuntimeError),
        raising=False,
    )
    handler = structured_logging.HttpJsonLogHandler(
        "https://logs.example.test/ingest",
        token="secret",
        timeout=3,
        async_mode=False,
    )
    handler.setFormatter(structured_logging.JsonLineFormatter())

    record = logging.LogRecord(
        name="shipper",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="cache_write_failed",
        args=(),
        exc_info=None,
    )
    record.structured_fields = {"event": "cache_write_failed", "error": "locked"}

    handler.emit(record)

    assert calls == [
        {
            "url": "https://logs.example.test/ingest",
            "json": {
                "timestamp": calls[0]["json"]["timestamp"],
                "level": "WARNING",
                "logger": "shipper",
                "message": "cache_write_failed",
                "event": "cache_write_failed",
                "error": "locked",
            },
            "headers": {"Authorization": "Bearer secret", "Content-Type": "application/json"},
            "timeout": 3,
        }
    ]

    def fail_post(url, json, headers, timeout):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        structured_logging,
        "requests",
        SimpleNamespace(post=fail_post, RequestException=RuntimeError),
        raising=False,
    )

    handler.emit(record)


def test_http_log_shipping_emit_uses_background_thread(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append(self)

    monkeypatch.setattr(structured_logging, "Thread", FakeThread)

    handler = structured_logging.HttpJsonLogHandler("https://logs.example.test/ingest")
    handler.setFormatter(structured_logging.JsonLineFormatter())
    record = logging.LogRecord(
        name="shipper",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="dashboard_run_recorded",
        args=(),
        exc_info=None,
    )
    record.structured_fields = {"event": "dashboard_run_recorded"}

    handler.emit(record)

    assert len(started) == 1
    assert started[0].daemon is True
    assert started[0].target == handler._post_payload


def test_blank_env_value_disables_ship_url_even_when_streamlit_secret_exists(monkeypatch, tmp_path):
    fake_streamlit = SimpleNamespace(secrets={"LOG_SHIP_URL": "https://logs.example.test/ingest"})
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setitem(
        sys.modules,
        "streamlit.errors",
        SimpleNamespace(StreamlitSecretNotFoundError=KeyError),
    )
    monkeypatch.setenv("LOG_SHIP_URL", "")

    logger = structured_logging.configure_structured_logging(
        logger_name="test-blank-env",
        log_path=tmp_path / "app.jsonl",
        ship_url=None,
    )

    assert not any(isinstance(handler, structured_logging.HttpJsonLogHandler) for handler in logger.handlers)


def test_log_event_rejects_unknown_level(tmp_path):
    logger = structured_logging.configure_structured_logging(
        logger_name="test-level",
        log_path=tmp_path / "app.jsonl",
        ship_url="",
    )

    with pytest.raises(ValueError, match="Unsupported log level"):
        structured_logging.log_event(logger, "bad", level="LOUD")
