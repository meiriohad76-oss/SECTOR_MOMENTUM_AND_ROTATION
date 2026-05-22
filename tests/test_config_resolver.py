from __future__ import annotations

from src.config_resolver import resolve_config_value


def test_resolve_config_value_prefers_environment(monkeypatch, tmp_path):
    root = tmp_path
    secrets_dir = root / ".streamlit"
    secrets_dir.mkdir()
    (secrets_dir / "secrets.toml").write_text('TOKEN = "from-file"\n', encoding="utf-8")
    monkeypatch.setenv("TOKEN", "from-env")

    assert resolve_config_value("TOKEN", root=root) == "from-env"


def test_resolve_config_value_reads_streamlit_secrets_without_streamlit(monkeypatch, tmp_path):
    root = tmp_path
    secrets_dir = root / ".streamlit"
    secrets_dir.mkdir()
    (secrets_dir / "secrets.toml").write_text('TOKEN = " from-file "\n', encoding="utf-8")
    monkeypatch.delenv("TOKEN", raising=False)

    assert resolve_config_value("TOKEN", root=root) == "from-file"


def test_resolve_config_value_ignores_missing_or_malformed_file(monkeypatch, tmp_path):
    monkeypatch.delenv("TOKEN", raising=False)
    assert resolve_config_value("TOKEN", root=tmp_path) is None

    secrets_dir = tmp_path / ".streamlit"
    secrets_dir.mkdir()
    (secrets_dir / "secrets.toml").write_text("TOKEN = [", encoding="utf-8")
    assert resolve_config_value("TOKEN", root=tmp_path) is None
