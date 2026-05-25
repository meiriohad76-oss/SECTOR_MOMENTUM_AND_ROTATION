"""Broker configuration diagnostics for the read-only B-131 P&L tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


ConfigResolver = Callable[[str], str | None]

BROKER_REQUIRED_FIELDS = {
    "alpaca": ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"),
    "ibkr": ("IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID"),
}

BROKER_OPTIONAL_FIELDS = {
    "alpaca": ("ALPACA_BASE_URL",),
    "ibkr": (),
}


@dataclass(frozen=True)
class BrokerConfigStatus:
    provider: str
    state: str
    configured: list[str]
    missing: list[str]
    optional_configured: list[str]
    live_connectivity: str = "not_attempted"


def broker_config_status(
    provider: str | None,
    *,
    resolver: ConfigResolver | None = None,
) -> BrokerConfigStatus:
    normalized = str(provider or "none").strip().lower()
    if normalized in {"", "none", "disabled", "off"}:
        return BrokerConfigStatus(
            provider="none",
            state="disabled",
            configured=[],
            missing=[],
            optional_configured=[],
        )
    if normalized not in BROKER_REQUIRED_FIELDS:
        return BrokerConfigStatus(
            provider=normalized,
            state="unsupported",
            configured=[],
            missing=[],
            optional_configured=[],
        )

    resolve = resolver or (lambda _name: None)
    required = BROKER_REQUIRED_FIELDS[normalized]
    optional = BROKER_OPTIONAL_FIELDS.get(normalized, ())
    configured = [name for name in required if _has_value(resolve(name))]
    missing = [name for name in required if name not in configured]
    optional_configured = [name for name in optional if _has_value(resolve(name))]
    return BrokerConfigStatus(
        provider=normalized,
        state="ready" if not missing else "missing",
        configured=[*configured, *optional_configured],
        missing=missing,
        optional_configured=optional_configured,
    )


def _has_value(value: str | None) -> bool:
    return bool(str(value).strip()) if value is not None else False
