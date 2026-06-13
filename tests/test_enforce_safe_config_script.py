from __future__ import annotations

import json

from scripts import enforce_safe_config


def test_enforce_safe_config_updates_ssl_and_enables_cached_provider_flow_flags(tmp_path, capsys):
    secrets_path = tmp_path / ".streamlit" / "secrets.toml"
    secrets_path.parent.mkdir()
    secrets_path.write_text(
        '\n'.join(
            [
                'MASSIVE_API_KEY = "SECRET_VALUE"',
                'OHLCV_PROVIDER = "massive"',
                'MASSIVE_VERIFY_SSL = "false"',
                'MASSIVE_TRADES_STUB_MODE = "true"',
                'FINRA_ATS_STUB_MODE = "true"',
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
    assert payload["enabled_provider_flow_lanes"] == [
        "massive_block_trades",
        "finra_ats_dark_pool",
        "finra_short_interest",
    ]
    assert 'MASSIVE_API_KEY = "SECRET_VALUE"' in text
    assert 'FRED_API_KEY = "FRED_SECRET"' in text
    assert 'MASSIVE_VERIFY_SSL = "true"' in text
    assert 'MASSIVE_TRADES_STUB_MODE = "false"' in text
    assert 'FINRA_ATS_STUB_MODE = "false"' in text
    assert 'FINRA_SHORT_INTEREST_STUB_MODE = "false"' in text
    assert 'SEC_13F_STUB_MODE = "false"' not in text
    assert "SECRET_VALUE" not in output
    assert "FRED_SECRET" not in output


def test_enforce_safe_config_adds_safe_flags_when_missing(tmp_path):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('MASSIVE_API_KEY = "SECRET_VALUE"\n', encoding="utf-8")

    result = enforce_safe_config.enforce_safe_config(secrets_path)

    text = secrets_path.read_text(encoding="utf-8")
    assert result["action"] == "added"
    assert 'MASSIVE_API_KEY = "SECRET_VALUE"' in text
    assert 'MASSIVE_VERIFY_SSL = "true"' in text
    assert 'MASSIVE_TRADES_STUB_MODE = "false"' in text
    assert 'FINRA_ATS_STUB_MODE = "false"' in text
    assert 'FINRA_SHORT_INTEREST_STUB_MODE = "false"' in text


def test_enforce_safe_config_creates_missing_file(tmp_path):
    secrets_path = tmp_path / ".streamlit" / "secrets.toml"

    result = enforce_safe_config.enforce_safe_config(secrets_path)

    assert result["exists_before"] is False
    assert result["action"] == "added"
    assert secrets_path.read_text(encoding="utf-8") == (
        'MASSIVE_VERIFY_SSL = "true"\n'
        'MASSIVE_TRADES_STUB_MODE = "false"\n'
        'FINRA_ATS_STUB_MODE = "false"\n'
        'FINRA_SHORT_INTEREST_STUB_MODE = "false"\n'
    )


def test_enforce_safe_config_is_idempotent(tmp_path):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text(
        'MASSIVE_VERIFY_SSL = "true"\n'
        'MASSIVE_TRADES_STUB_MODE = "false"\n'
        'FINRA_ATS_STUB_MODE = "false"\n'
        'FINRA_SHORT_INTEREST_STUB_MODE = "false"\n',
        encoding="utf-8",
    )

    result = enforce_safe_config.enforce_safe_config(secrets_path)

    assert result["action"] == "already_safe"
    assert all(value == "already_safe" for value in result["flag_actions"].values())


def test_legacy_enforce_massive_verify_ssl_wrapper_uses_full_safe_config(tmp_path):
    secrets_path = tmp_path / "secrets.toml"

    result = enforce_safe_config.enforce_massive_verify_ssl(secrets_path)

    assert result["action"] == "added"
    assert 'FINRA_ATS_STUB_MODE = "false"' in secrets_path.read_text(encoding="utf-8")
