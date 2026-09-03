"""
Full End-to-End Live Verification Test (Task 5)
================================================
Simulates the exact frontend flow:
1. Health check -> verifies VoiceShieldClassifier is loaded (not dummy)
2. Starts Call Session -> POST /api/calls/start
3. Streams Cloned Audio -> ws://localhost:8000/ws/stream/{call_id}
   - Verifies risk rises to FRAUD
   - Verifies hold_triggered message arrives
4. Verifies Cryptographic Evidence -> GET /api/evidence/{call_id}/verify
   - Verifies chain_valid: True
   - Verifies signatures_valid: True (Ed25519)
5. Starts Second Call -> Streams Real Audio
   - Verifies risk stays LOW (REAL)
"""
import asyncio
import json
import urllib.request
import numpy as np
import scipy.io.wavfile as wavfile
import websockets
from pathlib import Path

API_BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"

async def test_full_live_flow():
    print("=" * 65)
    print("VOICESHIELD — FULL END-TO-END LIVE FLOW VERIFICATION")
    print("=" * 65)

    # 1. Health Check
    print("\n[1/5] Checking Backend Health & Classifier...")
    with urllib.request.urlopen(f"{API_BASE}/health") as resp:
        health_data = json.loads(resp.read().decode())
        print(f"      Backend Status: {health_data['status']}")
        print(f"      Loaded Classifier: {health_data['classifier']} ({health_data['model_version']})")
        assert health_data["status"] == "ok"
        assert health_data["classifier"] == "VoiceShieldClassifier", "Expected VoiceShieldClassifier, not dummy!"
        print("      [PASS] Real AI Model loaded on GPU/CPU.")

    # 2. Test Cloned Audio Call Session
    print("\n[2/5] Starting Call Session for CLONED Audio Demo...")
    req = urllib.request.Request(
        f"{API_BASE}/api/calls/start",
        data=json.dumps({"source": "replay"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        call_data = json.loads(resp.read().decode())
        call_id = call_data["call_id"]
        print(f"      Call Created: {call_id} (status: {call_data['status']})")

    # 3. Stream Cloned Audio over WebSocket
    print("\n[3/5] Streaming 'cloned_en.wav' over WebSocket...")
    demo_wav_path = Path("frontend/public/demo/cloned_en.wav")
    assert demo_wav_path.exists(), "cloned_en.wav not found!"
    sr, audio_data = wavfile.read(str(demo_wav_path))
    assert sr == 16000, f"Expected 16kHz audio, got {sr}"

    # Convert to bytes
    pcm_bytes = audio_data.tobytes()
    # Stream in 500ms chunks (16000 * 2 bytes * 0.5s = 16000 bytes)
    chunk_size = 16000

    hold_received = False
    max_risk = 0.0
    final_verdict = "UNKNOWN"

    async with websockets.connect(f"{WS_BASE}/ws/stream/{call_id}") as ws:
        # Loop audio twice (9 seconds) to ensure multiple 2-second VAD windows are processed
        full_stream = pcm_bytes * 2
        for i in range(0, len(full_stream), chunk_size):
            chunk = full_stream[i:i + chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.1)

            # Check for incoming messages
            while True:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=0.05)
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "risk_update":
                        score = msg.get("fused_risk_score", 0)
                        max_risk = max(max_risk, score)
                        final_verdict = msg.get("verdict", final_verdict)
                        print(f"      -> Risk Update: score={score:.4f}, verdict={msg.get('verdict')}")
                    elif msg.get("type") == "hold_triggered":
                        hold_received = True
                        print(f"      -> Hold Triggered! Ref: {msg.get('mock_reference')}")
                except asyncio.TimeoutError:
                    break

        # Await any remaining in-flight inference responses
        for _ in range(15):
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=0.3)
                msg = json.loads(raw_msg)
                if msg.get("type") == "risk_update":
                    score = msg.get("fused_risk_score", 0)
                    max_risk = max(max_risk, score)
                    final_verdict = msg.get("verdict", final_verdict)
                    print(f"      -> Risk Update: score={score:.4f}, verdict={msg.get('verdict')}")
                elif msg.get("type") == "hold_triggered":
                    hold_received = True
                    print(f"      -> Hold Triggered! Ref: {msg.get('mock_reference')}")
            except asyncio.TimeoutError:
                pass

    print(f"      Peak Fused Risk: {max_risk:.4f} | Verdict: {final_verdict}")
    assert max_risk >= 0.70, f"Cloned audio risk too low: {max_risk}"
    assert hold_received, "Expected Transaction Hold to trigger on cloned audio!"
    print("      [PASS] Cloned audio correctly triggered HIGH RISK + Transaction Hold.")

    # 4. Verify Cryptographic Evidence Chain (BSA 2023 §63)
    print("\n[4/5] Verifying Ed25519 & SHA-256 Evidence Chain...")
    with urllib.request.urlopen(f"{API_BASE}/api/calls/{call_id}/evidence") as resp:
        verify_data = json.loads(resp.read().decode())
        print(f"      Entries Recorded: {verify_data['entry_count']}")
        print(f"      SHA-256 Hash Chain Valid: {verify_data['chain_valid']}")
        print(f"      Ed25519 Signatures Valid: {verify_data['signatures_valid']}")
        assert verify_data["chain_valid"] is True, "Hash chain invalid!"
        assert verify_data["signatures_valid"] is True, "Ed25519 signatures invalid!"
        print("      [PASS] CHAIN VALID & SIGNATURES VALID (Court-admissible non-repudiation).")

    # 5. Test Real Audio Call Session
    print("\n[5/5] Testing REAL Human Speech Session ('real_en.wav')...")
    req2 = urllib.request.Request(
        f"{API_BASE}/api/calls/start",
        data=json.dumps({"source": "replay"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req2) as resp:
        call_id2 = json.loads(resp.read().decode())["call_id"]

    real_wav_path = Path("frontend/public/demo/real_en.wav")
    sr2, audio_data2 = wavfile.read(str(real_wav_path))
    pcm_bytes2 = audio_data2.tobytes()

    max_risk_real = 0.0
    real_verdict = "REAL"

    async with websockets.connect(f"{WS_BASE}/ws/stream/{call_id2}") as ws:
        full_stream2 = pcm_bytes2 * 2
        for i in range(0, len(full_stream2), chunk_size):
            chunk = full_stream2[i:i + chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.1)
            while True:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=0.05)
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "risk_update":
                        score = msg.get("fused_risk_score", 0)
                        max_risk_real = max(max_risk_real, score)
                        real_verdict = msg.get("verdict", real_verdict)
                        print(f"      -> Risk Update (Real): score={score:.4f}, verdict={msg.get('verdict')}")
                except asyncio.TimeoutError:
                    break

        for _ in range(10):
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=0.3)
                msg = json.loads(raw_msg)
                if msg.get("type") == "risk_update":
                    score = msg.get("fused_risk_score", 0)
                    max_risk_real = max(max_risk_real, score)
                    real_verdict = msg.get("verdict", real_verdict)
                    print(f"      -> Risk Update (Real): score={score:.4f}, verdict={msg.get('verdict')}")
            except asyncio.TimeoutError:
                pass

    print(f"      Peak Real Risk: {max_risk_real:.4f} | Verdict: {real_verdict}")
    assert max_risk_real < 0.40, f"Real audio scored too high: {max_risk_real}"
    print("      [PASS] Real speech cleanly identified as REAL (low risk).")

    print("\n" + "=" * 65)
    print("FULL STACK LIVE DEMO FLOW VERIFIED 100% SUCCESSFUL!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(test_full_live_flow())
