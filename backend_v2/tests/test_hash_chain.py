"""
Tests for the SHA-256 hash-chain module.
These tests must pass 100% — the chain integrity is the legal PROVE claim.
"""
import pytest

from app.hash_chain import (
    GENESIS_HASH,
    build_payload,
    canonical,
    compute_hash,
    verify_chain,
)
from datetime import datetime, timezone
import uuid


CALL_ID = uuid.uuid4()
NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)


def make_entry(
    detection_id: int,
    prev_hash: str,
    spoof_prob: float = 0.8,
) -> dict:
    payload = build_payload(
        call_id=CALL_ID,
        detection_id=detection_id,
        window_start_ms=(detection_id - 1) * 500,
        window_end_ms=detection_id * 500,
        spoof_probability=spoof_prob,
        fused_risk_score=spoof_prob,
        is_flagged=spoof_prob >= 0.6,
        model_version="dummy-v0",
        server_timestamp=NOW,
    )
    entry_hash = compute_hash(prev_hash, payload)
    return {"prev_hash": prev_hash, "entry_hash": entry_hash, "payload": payload}


class TestCanonical:
    def test_dict_order_independent(self):
        """canonical() must produce the same bytes regardless of key insertion order."""
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert canonical(d1) == canonical(d2)

    def test_no_whitespace(self):
        raw = canonical({"key": "value"})
        assert b" " not in raw
        assert b"\n" not in raw


class TestComputeHash:
    def test_genesis_hash_length(self):
        assert len(GENESIS_HASH) == 64
        assert all(c == "0" for c in GENESIS_HASH)

    def test_hash_is_64_hex(self):
        payload = build_payload(
            call_id=CALL_ID, detection_id=1,
            window_start_ms=0, window_end_ms=500,
            spoof_probability=0.5, fused_risk_score=0.5,
            is_flagged=False, model_version="dummy-v0",
            server_timestamp=NOW,
        )
        h = compute_hash(GENESIS_HASH, payload)
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_hash_is_deterministic(self):
        payload = build_payload(
            call_id=CALL_ID, detection_id=1,
            window_start_ms=0, window_end_ms=500,
            spoof_probability=0.75, fused_risk_score=0.75,
            is_flagged=True, model_version="dummy-v0",
            server_timestamp=NOW,
        )
        h1 = compute_hash(GENESIS_HASH, payload)
        h2 = compute_hash(GENESIS_HASH, payload)
        assert h1 == h2

    def test_different_payloads_different_hashes(self):
        p1 = build_payload(CALL_ID, 1, 0, 500, 0.5, 0.5, False, "v0", NOW)
        p2 = build_payload(CALL_ID, 2, 500, 1000, 0.9, 0.9, True, "v0", NOW)
        assert compute_hash(GENESIS_HASH, p1) != compute_hash(GENESIS_HASH, p2)


class TestVerifyChain:
    def test_empty_chain_is_valid(self):
        assert verify_chain([]) is True

    def test_single_entry_valid_chain(self):
        entry = make_entry(1, GENESIS_HASH)
        assert verify_chain([entry]) is True

    def test_multi_entry_valid_chain(self):
        e1 = make_entry(1, GENESIS_HASH)
        e2 = make_entry(2, e1["entry_hash"])
        e3 = make_entry(3, e2["entry_hash"])
        assert verify_chain([e1, e2, e3]) is True

    def test_tampered_payload_breaks_chain(self):
        e1 = make_entry(1, GENESIS_HASH)
        e2 = make_entry(2, e1["entry_hash"])
        # Tamper: change spoof_probability in e1's payload
        e1_tampered = dict(e1)
        e1_tampered["payload"] = dict(e1["payload"])
        e1_tampered["payload"]["spoof_probability"] = 0.01   # was 0.8
        assert verify_chain([e1_tampered, e2]) is False

    def test_tampered_prev_hash_breaks_chain(self):
        e1 = make_entry(1, GENESIS_HASH)
        e2 = make_entry(2, e1["entry_hash"])
        e2_tampered = dict(e2)
        e2_tampered["prev_hash"] = "a" * 64  # wrong
        assert verify_chain([e1, e2_tampered]) is False

    def test_tampered_entry_hash_breaks_chain(self):
        e1 = make_entry(1, GENESIS_HASH)
        e1_tampered = dict(e1)
        e1_tampered["entry_hash"] = "b" * 64  # forged
        assert verify_chain([e1_tampered]) is False

    def test_wrong_genesis_breaks_chain(self):
        """First entry must reference GENESIS_HASH as prev_hash."""
        wrong_genesis = "f" * 64
        e1 = make_entry(1, wrong_genesis)   # starts from wrong genesis
        # verify_chain expects the first prev_hash to be GENESIS_HASH
        assert verify_chain([e1]) is False
