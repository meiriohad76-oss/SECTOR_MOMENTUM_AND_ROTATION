from __future__ import annotations

import builtins
from types import SimpleNamespace

from src import tls


def test_ensure_system_trust_store_returns_false_when_missing(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "truststore":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(tls, "_INJECTED", False)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert tls.ensure_system_trust_store() is False


def test_ensure_system_trust_store_injects_once(monkeypatch):
    calls = []
    fake_truststore = SimpleNamespace(inject_into_ssl=lambda: calls.append("inject"))
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "truststore":
            return fake_truststore
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(tls, "_INJECTED", False)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert tls.ensure_system_trust_store() is True
    assert tls.ensure_system_trust_store() is True
    assert calls == ["inject"]
