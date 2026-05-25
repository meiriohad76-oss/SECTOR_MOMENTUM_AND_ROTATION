from __future__ import annotations

import json

from scripts import generate_vapid_keys


def test_generate_vapid_keys_writes_private_key_file_and_sanitized_json(tmp_path, capsys):
    private_key_path = tmp_path / "vapid_private_key.pem"

    exit_code = generate_vapid_keys.main(
        [
            "--private-key-path",
            str(private_key_path),
            "--claim-email",
            "ops@example.test",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    private_key_text = private_key_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["vapid_private_key"] == str(private_key_path)
    assert payload["vapid_claim_email"] == "ops@example.test"
    assert payload["vapid_public_key"]
    assert private_key_text.startswith("-----BEGIN PRIVATE KEY-----")
    assert private_key_text not in json.dumps(payload)


def test_generate_vapid_docs_reference_public_key_subscription_flow():
    root = generate_vapid_keys.ROOT
    readme = (root / "README.md").read_text(encoding="utf-8")
    secrets_example = (root / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

    assert "scripts/generate_vapid_keys.py" in readme
    assert "VAPID_PUBLIC_KEY" in secrets_example
    assert "vapid_public_key=PUBLIC_KEY" in readme
