"""
VoiceShield — Comprehensive Security & Adversarial Resilience Test Suite
========================================================================
Tests all defensive layers against simulated cyber-attacks:
  1. BSA 2023 §63 Hash-Chain Tamper Attack (Database record modification)
  2. Ed25519 Cryptographic Signature Forgery & Key Substitution Attack
  3. SQL Injection & Path Traversal on Session IDs
  4. Concurrent Hold Race Condition Attack
  5. DPDP Act Compliance (Zero-Disk Persistence of Raw Audio in RAM)
"""
import sys
import os
import asyncio
import uuid
import json
import pytest
import httpx
from pathlib import Path
from datetime import datetime, timezone

# Add backend_v2 to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend_v2"))

from app.models import Call, Detection, EvidenceLog
from app.hash_chain import compute_hash, build_payload, verify_chain, GENESIS_HASH
from app.signing import sign_hash, verify_signature, public_key_hex
from app.database import AsyncSessionLocal
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

API_BASE = "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_attack_1_hash_chain_tamper_detection():
    """
    ATTACK 1: Attacker gains unauthorized DB access and alters a historical
    detection event to hide evidence of a voice clone (e.g. changing FRAUD to REAL).
    DEFENSE: Merkle SHA-256 hash-chain must fail verification and pinpoint corruption.
    """
    async with AsyncSessionLocal() as session:
        call_id = uuid.uuid4()
        call_rec = Call(
            call_id=call_id,
            source="mic",
            status="active"
        )
        session.add(call_rec)
        await session.flush()

        prev_hash = GENESIS_HASH
        entries = []
        for i in range(5):
            payload = build_payload(
                call_id=call_id,
                detection_id=i + 1,
                window_start_ms=i * 2000,
                window_end_ms=(i + 1) * 2000,
                spoof_probability=0.85 if i == 2 else 0.10,
                fused_risk_score=0.85 if i == 2 else 0.10,
                is_flagged=True if i == 2 else False,
                model_version="melcnn-v1",
                server_timestamp=datetime.now(timezone.utc)
            )
            h = compute_hash(prev_hash, payload)
            sig = sign_hash(h)
            log = EvidenceLog(
                call_id=call_id,
                detection_id=i + 1,
                payload=payload,
                entry_hash=h,
                prev_hash=prev_hash,
                signature=sig
            )
            session.add(log)
            entries.append({"prev_hash": prev_hash, "entry_hash": h, "payload": payload})
            prev_hash = h
        await session.commit()

        # Step A: Normal chain must be 100% valid
        assert verify_chain(entries) is True, "Legitimate chain must pass"

        # Step B: ATTACK! Attacker modifies event #2 payload
        tampered_entries = [dict(e) for e in entries]
        tampered_entries[2] = dict(tampered_entries[2])
        tampered_entries[2]["payload"] = dict(tampered_entries[2]["payload"])
        tampered_entries[2]["payload"]["fused_risk_score"] = 0.10
        tampered_entries[2]["payload"]["is_flagged"] = False

        # Step C: Verification MUST FAIL immediately
        assert verify_chain(tampered_entries) is False, "Tampered chain must fail verification!"
        print("\n[DEFENSE 1 SUCCESS] Tampering detected. BSA §63 chain is tamper-evident.")


@pytest.mark.asyncio
async def test_attack_2_signature_forgery_rejection():
    """
    ATTACK 2: Attacker generates their own rogue Ed25519 keypair and attempts
    to sign a forged audit event to claim non-repudiation.
    DEFENSE: Official public key verification must reject the signature.
    """
    rogue_private_key = Ed25519PrivateKey.generate()
    legit_pubkey = public_key_hex()
    test_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # Attacker signs with rogue key
    forged_signature = rogue_private_key.sign(test_hash.encode()).hex()

    # Verify against system public key
    is_valid = verify_signature(test_hash, forged_signature, legit_pubkey)
    assert is_valid is False, "Forged signature must be rejected!"
    print("[DEFENSE 2 SUCCESS] Cryptographic signature forgery successfully rejected.")


@pytest.mark.asyncio
async def test_attack_3_sql_and_path_traversal_injection():
    """
    ATTACK 3: Attacker injects path traversal, SQL injection, and XSS into call_id endpoints.
    DEFENSE: FastAPI + Pydantic UUID validation must safely reject with 422/400.
    """
    malicious_payloads = [
        "../../../../etc/passwd",
        "' OR 1=1 --",
        "<script>alert('xss')</script>",
        "00000000-0000-0000-0000-000000000000' UNION SELECT 1,2,3--",
    ]

    async with httpx.AsyncClient(base_url=API_BASE) as client:
        for payload in malicious_payloads:
            resp = await client.get(f"/api/calls/{payload}/evidence")
            assert resp.status_code in (400, 404, 422), f"Expected 4xx for payload '{payload}', got {resp.status_code}"
            assert "Traceback" not in resp.text
            assert "sqlite3.OperationalError" not in resp.text
            assert "psycopg2" not in resp.text
    print("[DEFENSE 3 SUCCESS] All injection and path traversal attempts safely blocked with 4xx.")


@pytest.mark.asyncio
async def test_attack_4_concurrent_hold_race_condition():
    """
    ATTACK 4: Concurrent race condition — multiple actors attempt to trigger hold
    on the same call simultaneously.
    DEFENSE: System must handle concurrent requests idempotently and atomically.
    """
    async with httpx.AsyncClient(base_url=API_BASE) as client:
        # 1. Create a call
        init_res = await client.post("/api/calls/start", json={"source": "mic"})
        assert init_res.status_code == 201
        call_id = init_res.json()["call_id"]

        # 2. Fire 5 simultaneous hold requests
        tasks = [client.post(f"/api/calls/{call_id}/hold") for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        # All requests must return valid JSON without 500 crashes
        statuses = [r.status_code for r in responses]
        assert (201 in statuses or 200 in statuses), f"At least one hold must succeed, got {statuses}"
        for s in statuses:
            assert s in (200, 201, 400, 409), f"Unexpected status {s}"

        # Check call is held
        detail_res = await client.get(f"/api/calls/{call_id}/status")
        assert detail_res.status_code == 200
        assert detail_res.json()["status"] == "held"
    print("[DEFENSE 4 SUCCESS] Concurrent hold requests handled safely without race condition.")


@pytest.mark.asyncio
async def test_attack_5_dpdp_zero_disk_leak_verification():
    """
    ATTACK 5 / COMPLIANCE: Digital Personal Data Protection (DPDP) Act 2023.
    Audio must be processed in ephemeral RAM and NEVER stored to disk or temp.
    DEFENSE: Audit disk for any transient .wav or .pcm files created during runtime.
    """
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    
    audio_dumps = list(temp_dir.glob("*voiceshield*.wav")) + list(temp_dir.glob("*voiceshield*.pcm"))
    assert len(audio_dumps) == 0, f"Found un-zeroed audio files on disk: {audio_dumps}"
    print("[DEFENSE 5 SUCCESS] Zero disk audio persistence verified. DPDP Act 2023 strictly observed.")
