from __future__ import annotations

import importlib


def _broker_config():
    return importlib.import_module("src.broker_config")


def test_broker_config_status_reports_missing_alpaca_fields_without_secret_values():
    broker_config = _broker_config()

    def resolver(name):
        values = {
            "ALPACA_API_KEY_ID": "alpaca-key",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        }
        return values.get(name)

    status = broker_config.broker_config_status("alpaca", resolver=resolver)

    assert status.provider == "alpaca"
    assert status.state == "missing"
    assert status.configured == ["ALPACA_API_KEY_ID", "ALPACA_BASE_URL"]
    assert status.missing == ["ALPACA_API_SECRET_KEY"]
    assert "alpaca-key" not in repr(status)


def test_broker_config_status_marks_ibkr_ready_when_required_fields_exist():
    broker_config = _broker_config()

    def resolver(name):
        values = {
            "IBKR_HOST": "127.0.0.1",
            "IBKR_PORT": "7497",
            "IBKR_CLIENT_ID": "7",
        }
        return values.get(name)

    status = broker_config.broker_config_status("ibkr", resolver=resolver)

    assert status.provider == "ibkr"
    assert status.state == "ready"
    assert status.missing == []
    assert status.live_connectivity == "not_attempted"


def test_broker_config_status_disables_unknown_or_empty_provider():
    broker_config = _broker_config()

    assert broker_config.broker_config_status("").state == "disabled"
    assert broker_config.broker_config_status("none").state == "disabled"
    assert broker_config.broker_config_status("robinhood").state == "unsupported"
