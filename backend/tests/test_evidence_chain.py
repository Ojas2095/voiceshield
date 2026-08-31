import copy
import uuid
import pytest

from backend.app.services.evidence_chain import (
    GENESIS_HASH,
    canonical,
    next_hash,
    verify_chain,
)


def test_01_valid_evidence_chain_verification():
    """
    Test that a cryptographically linked sequence of evidence entries passes verification.
    """
    call_id = str(uuid.uuid4())
    entries = []
    prev_hash = GENESIS_HASH

    for i in range(1, 4):
        payload = {
            "call_id": call_id,
            "detection_id": i,
            "window_start_ms": (i - 1) * 500,
            "window_end_ms": (i - 1) * 500 + 2000,
            "spoof_probability": 0.85 if i == 2 else 0.12,
            "fused_risk_score": 0.72 if i >= 2 else 0.15,
            "is_flagged": True if i >= 2 else False,
            "model_version": "v0.1-dummy",
            "timestamp": f"2026-08-31T22:00:0{i}Z",
        }
        current_hash = next_hash(prev_hash, payload)
        entries.append({
            "entry_id": i,
            "call_id": call_id,
            "detection_id": i,
            "payload": payload,
            "entry_hash": current_hash,
            "prev_hash": prev_hash,
        })
        prev_hash = current_hash

    # Verify the intact chain
    assert verify_chain(entries) is True, "Valid hash-chain must verify as True."


def test_02_tampered_payload_verification():
    """
    Test that tampering with an intermediate payload breaks verification.
    """
    call_id = str(uuid.uuid4())
    entries = []
    prev_hash = GENESIS_HASH

    for i in range(1, 4):
        payload = {
            "call_id": call_id,
            "detection_id": i,
            "window_start_ms": (i - 1) * 500,
            "window_end_ms": (i - 1) * 500 + 2000,
            "spoof_probability": 0.90 if i == 2 else 0.10,
            "fused_risk_score": 0.80 if i >= 2 else 0.10,
            "is_flagged": True if i >= 2 else False,
            "model_version": "v0.1-dummy",
            "timestamp": f"2026-08-31T22:00:0{i}Z",
        }
        current_hash = next_hash(prev_hash, payload)
        entries.append({
            "entry_id": i,
            "call_id": call_id,
            "detection_id": i,
            "payload": payload,
            "entry_hash": current_hash,
            "prev_hash": prev_hash,
        })
        prev_hash = current_hash

    # Tamper payload of entry 2 (e.g. malicious attacker modifying spoof_probability)
    tampered_entries = copy.deepcopy(entries)
    tampered_entries[1]["payload"]["spoof_probability"] = 0.05
    tampered_entries[1]["payload"]["is_flagged"] = False

    assert verify_chain(tampered_entries) is False, "Tampered payload must cause verify_chain to return False."


def test_03_broken_prev_hash_linkage():
    """
    Test that modifying a prev_hash pointer breaks verification.
    """
    call_id = str(uuid.uuid4())
    entries = []
    prev_hash = GENESIS_HASH

    for i in range(1, 3):
        payload = {
            "call_id": call_id,
            "detection_id": i,
            "window_start_ms": 0,
            "window_end_ms": 2000,
            "spoof_probability": 0.2,
            "fused_risk_score": 0.2,
            "is_flagged": False,
            "model_version": "v0.1-dummy",
            "timestamp": f"2026-08-31T22:00:0{i}Z",
        }
        current_hash = next_hash(prev_hash, payload)
        entries.append({
            "entry_id": i,
            "call_id": call_id,
            "detection_id": i,
            "payload": payload,
            "entry_hash": current_hash,
            "prev_hash": prev_hash,
        })
        prev_hash = current_hash

    # Break prev_hash pointer on entry 2
    broken_entries = copy.deepcopy(entries)
    broken_entries[1]["prev_hash"] = "f" * 64

    assert verify_chain(broken_entries) is False, "Broken prev_hash linkage must cause verify_chain to return False."
