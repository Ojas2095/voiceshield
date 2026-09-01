"""
SHA-256 Hash-Chain — the backbone of the PROVE pillar.

Chain invariant:
  entry_hash = SHA-256( prev_hash_bytes || canonical_json(payload) )

Where:
  - prev_hash for the first entry of a call is GENESIS_HASH ("0" * 64)
  - canonical_json sorts keys and strips whitespace so hash is dict-order-independent
  - payload contains every field a court needs to reconstruct what was detected and when

Verification:
  verify_chain(entries) re-derives every hash from scratch and returns False
  the moment any entry's stored hash doesn't match the recomputed value.
  This is what the "Verify Integrity" button calls.

Reference: §6 of the VoiceShield Round 2 brief.
Legal basis: Bharatiya Sakshya Adhiniyam (BSA) 2023, §63 — the direct successor to
the old Indian Evidence Act §65B for electronic-evidence admissibility.
Use "BSA 2023 §63" in all pitch materials, evidence exports, and PDFs.
Do NOT say "IT Act §65B" — that is a different statute entirely and will be
caught by a judge who knows Indian evidence law.
"""
import hashlib
import json
import uuid
from datetime import datetime

GENESIS_HASH = "0" * 64


def canonical(payload: dict) -> bytes:
    """
    Deterministic JSON serialisation — sort_keys + no whitespace ensures the
    hash is independent of dict insertion order.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def compute_hash(prev_hash: str, payload: dict) -> str:
    """SHA-256(prev_hash_utf8 || canonical_payload)"""
    data = prev_hash.encode("utf-8") + canonical(payload)
    return hashlib.sha256(data).hexdigest()


def build_payload(
    call_id: uuid.UUID,
    detection_id: int,
    window_start_ms: int,
    window_end_ms: int,
    spoof_probability: float,
    fused_risk_score: float,
    is_flagged: bool,
    model_version: str,
    server_timestamp: datetime,
) -> dict:
    """
    Constructs the canonical payload dict.
    Only these fields are hashed — nothing extraneous.
    The server_timestamp is included so the chain is time-ordered.
    """
    return {
        "call_id": str(call_id),
        "detection_id": detection_id,
        "fused_risk_score": round(float(fused_risk_score), 6),
        "is_flagged": bool(is_flagged),
        "model_version": str(model_version),
        "server_timestamp": server_timestamp.isoformat(),
        "spoof_probability": round(float(spoof_probability), 6),
        "window_end_ms": int(window_end_ms),
        "window_start_ms": int(window_start_ms),
    }


def verify_chain(entries: list[dict]) -> bool:
    """
    Verifies the integrity of an evidence chain.

    Args:
        entries: list of dicts, each with keys:
                 'prev_hash', 'entry_hash', 'payload'
                 Ordered chronologically (ascending entry_id).

    Returns:
        True if every hash is correct and the chain is unbroken.
        False immediately on first inconsistency.
    """
    if not entries:
        return True  # empty chain is trivially valid

    prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        stored_prev = entry.get("prev_hash", "")
        stored_hash = entry.get("entry_hash", "")
        payload = entry.get("payload", {})

        # 1. The entry's prev_hash must equal the previous entry's hash
        if stored_prev != prev:
            return False

        # 2. Re-derive the hash and compare
        expected = compute_hash(prev, payload)
        if expected != stored_hash:
            return False

        prev = stored_hash

    return True
