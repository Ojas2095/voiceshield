"""
Ed25519 digital signatures for the evidence chain.

The SHA-256 hash-chain makes the log *tamper-evident* (any edit breaks the
chain). Signing each entry_hash with a server-held Ed25519 private key adds
*non-repudiation*: only the holder of the private key could have produced the
entry, so a court can verify the evidence was created by VoiceShield and not
forged after the fact. Together they satisfy the "unalterable custody" bar of
Bharatiya Sakshya Adhiniyam (BSA) 2023, §63.

Key handling
------------
- Private key lives at `backend_v2/keys/evidence_ed25519.pem` (git-ignored).
- Generated automatically on first use if absent (and locked to 0600).
- In production this key belongs in a KMS/HSM — the file store is the demo path.
- The PUBLIC key is exposed via the evidence API so anyone can independently
  verify signatures without trusting the server.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)


def _key_path() -> Path:
    """Where the signing key lives (overridable via settings.evidence_key_path)."""
    try:
        from app.config import get_settings
        configured = getattr(get_settings(), "evidence_key_path", None)
    except Exception:
        configured = None
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "keys" / "evidence_ed25519.pem"


@lru_cache(maxsize=1)
def _private_key() -> Ed25519PrivateKey:
    path = _key_path()
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        logger.info("Loaded evidence signing key from %s", path)
        return key  # type: ignore[return-value]

    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows / restricted FS — best effort
    logger.warning(
        "Generated a NEW evidence signing key at %s — back it up and keep it "
        "private; losing it invalidates future signature verification.", path
    )
    return key


def sign_hash(entry_hash_hex: str) -> str:
    """Sign a hex-encoded entry hash. Returns a hex signature."""
    return _private_key().sign(bytes.fromhex(entry_hash_hex)).hex()


def public_key_hex() -> str:
    """Raw Ed25519 public key as hex — publish this so anyone can verify."""
    raw = _private_key().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return raw.hex()


def verify_signature(entry_hash_hex: str, signature_hex: str, public_key_hex_str: str | None = None) -> bool:
    """Verify a signature over an entry hash. Uses the server key unless a
    specific public key (hex) is supplied. Returns False on any error."""
    try:
        if public_key_hex_str:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex_str))
        else:
            pub = _private_key().public_key()
        pub.verify(bytes.fromhex(signature_hex), bytes.fromhex(entry_hash_hex))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Self-test — no server needed.
    h = "a" * 64
    s = sign_hash(h)
    print("public key:", public_key_hex())
    print("signature :", s[:32], "...")
    print("verify ok :", verify_signature(h, s))
    print("verify bad:", verify_signature("b" * 64, s))
