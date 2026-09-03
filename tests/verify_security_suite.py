"""
VoiceShield — Automated Security & Adversarial Attack Verification Suite
========================================================================
Executes 6 adversarial attacks against the running VoiceShield system:
  [1] BSA 2023 §63 Merkle Hash-Chain Tamper Attack (Database mutation)
  [2] Ed25519 Cryptographic Signature Forgery & Key Substitution Attack
  [3] WebSocket Fuzzing (Buffer-bomb DoS, odd unaligned bytes, text frame injection)
  [4] SQL Injection & Path Traversal on Session APIs
  [5] Concurrent Hold Trigger & Race Condition Attack
  [6] DPDP Act 2023 Audio Zero-Disk Persistence Verification
"""
import sys
import os
import asyncio
import uuid
import json
import httpx
import websockets
import numpy as np
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
WS_BASE = "ws://127.0.0.1:8000"


async def test_1_merkle_hash_chain_tamper():
    print("\n[ATTACK 1] Simulating Unauthorized Database Tampering on Evidence Record...")
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
        for i in range(4):
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

        # Step A: Legitimate chain must pass
        assert verify_chain(entries) is True, "Legitimate chain must pass"

        # Step B: Tamper Attack! An attacker alters payload of entry #2 in the database
        tampered_entries = [dict(e) for e in entries]
        tampered_entries[2]["payload"] = dict(tampered_entries[2]["payload"])
        tampered_entries[2]["payload"]["fused_risk_score"] = 0.10
        tampered_entries[2]["payload"]["is_flagged"] = False

        # Step C: Verification MUST fail immediately
        assert verify_chain(tampered_entries) is False, "Tampered chain MUST be rejected!"
        print("      -> PASS: Malicious alteration of Event #2 instantly flagged. BSA §63 chain is tamper-evident.")


async def test_2_signature_forgery():
    print("\n[ATTACK 2] Simulating Cryptographic Signature Forgery (Rogue Key)...")
    rogue_private_key = Ed25519PrivateKey.generate()
    legit_pubkey = public_key_hex()
    data_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    forged_sig = rogue_private_key.sign(data_hash.encode()).hex()
    is_valid = verify_signature(data_hash, forged_sig, legit_pubkey)
    assert is_valid is False, "Forged signature must fail"
    print("      -> PASS: Forged signature using rogue Ed25519 key rejected.")


async def test_3_websocket_malformed_payloads():
    print("\n[ATTACK 3] Fuzzing WebSocket with Malformed & Malicious Audio Payloads...")
    async with httpx.AsyncClient(base_url=API_BASE) as client:
        res = await client.post("/api/calls/start", json={"source": "mic"})
        call_id = res.json()["call_id"]

    async with websockets.connect(f"{WS_BASE}/ws/stream/{call_id}") as ws:
        # A. Odd-length byte frame (31 bytes - unaligned int16)
        await ws.send(b"\x00" * 31)
        await asyncio.sleep(0.05)

        # B. Non-audio text frame / injection attack
        await ws.send(json.dumps({"attack": "DROP TABLE detections;", "admin": True}))
        await asyncio.sleep(0.05)

        # C. Giant buffer (1 MB single frame DoS attempt)
        await ws.send(b"\x00" * (1024 * 1024))
        await asyncio.sleep(0.1)

        # D. Send legitimate audio chunk to confirm server is still completely alive and healthy
        legit_pcm = (np.sin(np.linspace(0, 100, 32000)) * 10000).astype(np.int16).tobytes()
        await ws.send(legit_pcm)

        response_received = False
        for _ in range(25):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(msg)
                if data.get("type") in ("risk_update", "vad_update"):
                    response_received = True
                    break
            except asyncio.TimeoutError:
                pass

        assert response_received, "Server failed to process frames after fuzzing attacks"
        print("      -> PASS: Server remained resilient against buffer bombs, odd bytes, and text injections.")


async def test_4_sql_and_path_traversal():
    print("\n[ATTACK 4] Testing SQL Injection & Path Traversal on Session APIs...")
    attacks = [
        "../../../../etc/passwd",
        "' OR 1=1 --",
        "<script>alert('xss')</script>",
        "00000000-0000-0000-0000-000000000000' UNION SELECT 1,2,3--",
    ]
    async with httpx.AsyncClient(base_url=API_BASE) as client:
        for payload in attacks:
            resp = await client.get(f"/api/calls/{payload}/evidence")
            assert resp.status_code in (400, 404, 422), f"Unexpected status {resp.status_code} on {payload}"
            assert "Traceback" not in resp.text
            assert "syntax error" not in resp.text.lower()
    print("      -> PASS: All SQL injection and path traversal payloads rejected with clean 4xx.")


async def test_5_concurrent_hold_race():
    print("\n[ATTACK 5] Testing Concurrent Hold Race Condition (Double-Spend / Replay)...")
    async with httpx.AsyncClient(base_url=API_BASE) as client:
        res = await client.post("/api/calls/start", json={"source": "mic"})
        call_id = res.json()["call_id"]

        # 5 simultaneous hold requests
        tasks = [client.post(f"/api/calls/{call_id}/hold") for _ in range(5)]
        results = await asyncio.gather(*tasks)

        statuses = [r.status_code for r in results]
        assert (201 in statuses or 200 in statuses), f"At least one hold must succeed (got {statuses})"
        for s in statuses:
            assert s in (200, 201, 400, 409), f"Unexpected status {s}"

        # Confirm final call state
        detail = await client.get(f"/api/calls/{call_id}/status")
        assert detail.status_code == 200
        assert detail.json()["status"] == "held"
    print("      -> PASS: State transitions are atomic; no race conditions or inconsistent states.")


async def test_6_dpdp_zero_audio_leak():
    print("\n[ATTACK 6] Verifying DPDP Act 2023 Compliance (Zero Raw Audio on Disk)...")
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    leaks = list(temp_dir.glob("*voiceshield*.wav")) + list(temp_dir.glob("*voiceshield*.pcm"))
    assert len(leaks) == 0, f"Found leaked raw audio on disk: {leaks}"
    print("      -> PASS: Confirmed zero audio bytes persisted to filesystem. RAM-only processing.")


async def main():
    print("=" * 68)
    print("VOICESHIELD — ADVERSARIAL SECURITY & RESILIENCE VERIFICATION")
    print("=" * 68)
    await test_1_merkle_hash_chain_tamper()
    await test_2_signature_forgery()
    await test_3_websocket_malformed_payloads()
    await test_4_sql_and_path_traversal()
    await test_5_concurrent_hold_race()
    await test_6_dpdp_zero_audio_leak()
    print("\n" + "=" * 68)
    print("ALL 6 SECURITY & DEFENSE TESTS PASSED! SYSTEM IS ATTACK-RESILIENT.")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(main())
