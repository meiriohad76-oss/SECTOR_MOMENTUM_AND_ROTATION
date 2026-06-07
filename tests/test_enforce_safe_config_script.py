from __future__ import annotations

import json

from scripts import enforce_safe_config


def test_enforce_safe_config_updates_only_massive_ssl_flag(tmp_path, capsys):
    secrets_path = tmp_path / ".streamlit" / "secrets.toml"
    secrets_path.parent.mkdir()
    secrets_path.write_text(
        '\n'.join(
            [
                'MASSIVE_API_KEY = "SECRET_VALUE"',
                'OHLCV_PROVIDER = "massive"',
                'MASSIVE_VERIFY_SSL = "false"',
                'FRED_API_KEY = "FRED_SECRET"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = enforce_safe_config.main(["--secrets-path", str(secrets_path)])

    output = capsys.readouterr().out
    payload = json.loads(output)
    text = secrets_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["action"] == "updated"
    assert payload["massive_verify_ssl"] == "true"
    assert 'MASSIVE_API_KEY = "SECRET_VALUE"' in text
    assert 'FRED_API_KEY = "FRED_SECRET"' in text
    assert 'MASSIVE_VERIFY_SSL = "true"' in text
    assert "SECRET_VALUE" not in output
    assert "FRED_SECRET" not in output


def test_enforce_safe_config_adds_ssl_flag_when_missing(tmp_path):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('MASSIVE_API_KEY = "SECRET_VALUE"\n', encoding="utf-8")

    result = enforce_safe_config.enforce_massive_verify_ssl(secrets_path)

    text = secrets_path.read_text(encoding="utf-8")
    assert result["action"] == "added"
    assert 'MASSIVE_API_KEY = "SECRET_VALUE"' in text
    assert 'MASSIVE_VERIFY_SSL = "true"' in text


def test_enforce_safe_config_creates_missing_file(tmp_path):
    secrets_path = tmp_path / ".streamlit" / "secrets.toml"

    result = enforce_safe_config.enforce_massive_verify_ssl(secrets_path)

    assert result["exists_before"] is False
    assert result["action"] == "added"
    assert secrets_path.read_text(encoding="utf-8") == 'MASSIVE_VERIFY_SSL = "true"\n'


def test_enforce_safe_config_is_idempotent(tmp_path):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('MASSIVE_VERIFY_SSL = "true"\n', encoding="utf-8")

    result = enforce_safe_config.enforce_massive_verify_ssl(secrets_path)

    assert result["action"] == "already_safe"
    assert secrets_path.read_text(encoding="utf-8") == 'MASSIVE_VERIFY_SSL = "true"\n'
