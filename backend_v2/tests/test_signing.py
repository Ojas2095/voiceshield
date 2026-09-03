"""
Tests for the Ed25519 evidence signatures (the non-repudiation half of PROVE).
Pure crypto + hash-chain — no torch/DB needed.
"""
import uuid
from datetime import datetime, timezone

from app.hash_chain import GENESIS_HASH, build_payload, compute_hash, verify_chain
from app.signing import public_key_hex, sign_hash, verify_signature

CALL = uuid.uuid4()
NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)


def _entry(det_id: int, prev: str, p: float = 0.8) -> dict:
    payload = build_payload(CALL, det_id, (det_id - 1) * 500, det_id * 500, p, p, p >= 0.6, "test-v0", NOW)
    h = compute_hash(prev, payload)
    return {"prev_hash": prev, "entry_hash": h, "payload": payload, "signature": sign_hash(h)}


def _chain(n: int = 3) -> list[dict]:
    out, prev = [], GENESIS_HASH
    for i in range(1, n + 1):
        e = _entry(i, prev)
        out.append(e)
        prev = e["entry_hash"]
    return out


def test_sign_and_verify_roundtrip():
    h = "a" * 64
    assert verify_signature(h, sign_hash(h)) is True


def test_tampered_message_rejected():
    h = "a" * 64
    sig = sign_hash(h)
    assert verify_signature("b" * 64, sig) is False


def test_wrong_signature_rejected():
    assert verify_signature("a" * 64, sign_hash("c" * 64)) is False


def test_public_key_is_hex_32_bytes():
    pk = public_key_hex()
    assert len(pk) == 64
    bytes.fromhex(pk)  # valid hex


def test_every_chain_entry_signature_valid():
    chain = _chain()
    assert all(verify_signature(e["entry_hash"], e["signature"]) for e in chain)


def test_chain_hash_integrity_plus_signatures():
    chain = _chain()
    # hash-chain intact
    assert verify_chain(chain) is True
    # ...and if a payload is tampered, the chain breaks
    tampered = [dict(x) for x in chain]
    tampered[1] = dict(tampered[1], payload=dict(tampered[1]["payload"], fused_risk_score=0.01))
    assert verify_chain(tampered) is False
