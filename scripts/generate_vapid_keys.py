"""Generate a local VAPID key pair for B-121 Web Push alerts."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


ROOT = Path(__file__).resolve().parents[1]


def _urlsafe_no_padding(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _public_key_for_browser(private_key: ec.EllipticCurvePrivateKey) -> str:
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return _urlsafe_no_padding(public_bytes)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-key-path",
        default=str(ROOT / "data" / "vapid_private_key.pem"),
        help="where to write the private key PEM; keep this path ignored by git",
    )
    parser.add_argument("--claim-email", default="", help="contact email for VAPID_CLAIM_EMAIL")
    parser.add_argument("--force", action="store_true", help="overwrite an existing private key file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    private_key_path = Path(args.private_key_path)
    if private_key_path.exists() and not args.force:
        print(
            json.dumps(
                {
                    "vapid_keys": "exists",
                    "vapid_private_key": str(private_key_path),
                    "hint": "use --force to overwrite",
                },
                sort_keys=True,
            )
        )
        return 2

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key_path.write_bytes(pem)
    try:
        private_key_path.chmod(0o600)
    except OSError:
        pass

    print(
        json.dumps(
            {
                "vapid_keys": "generated",
                "vapid_private_key": str(private_key_path),
                "vapid_public_key": _public_key_for_browser(private_key),
                "vapid_claim_email": args.claim_email,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
