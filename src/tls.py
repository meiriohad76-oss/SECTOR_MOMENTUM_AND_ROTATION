"""TLS trust-store helpers for provider integrations."""
from __future__ import annotations

_INJECTED = False


def ensure_system_trust_store() -> bool:
    """Use the operating-system trust store when the optional dependency exists."""
    global _INJECTED
    if _INJECTED:
        return True
    try:
        import truststore
    except ImportError:
        return False
    truststore.inject_into_ssl()
    _INJECTED = True
    return True
