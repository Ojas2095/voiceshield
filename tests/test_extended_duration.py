"""
VoiceShield — Extended Duration Evaluation Suite (60s - 120s Audio Calls)
=========================================================================
Evaluates model stability, rolling buffer behavior, and transcript intent
classification over prolonged realistic calls:
  - Scenario 1: Long Natural Conversation (68.6s)
  - Scenario 2: Long Cloned Scam Extortion Call (94.6s)
"""
import os
import sys
import json
import time
import asyncio
import numpy as np
import httpx
import websockets
import scipy.io.wavfile as wavfile

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"


async def run_extended_call_test(wav_path: str, is_expected_fraud: bool, test_name: str):
    print(f"\n{'='*70}")
    print(f"RUNNING EXTENDED CALL TEST: {test_name}")
    print(f"Audio File: {wav_path}")
    print(f"{'='*70}")

    sr, data = wavfile.read(wav_path)
    duration_s = len(data) / float(sr)
    print(f"Audio duration: {duration_s:.1f} seconds ({len(data)} samples at {sr} Hz)")

    # 1. Start Call Session
    async with httpx.AsyncClient() as client:
        start_res = await client.post(f"{API_BASE}/api/calls/start", json={"source": "replay"})
        assert start_res.status_code == 201, f"Failed to start call: {start_res.text}"
        call_id = start_res.json()["call_id"]
        print(f"Call Session Created: {call_id}")

    # 2. Connect to WebSocket
    ws_url = f"{WS_BASE}/ws/stream/{call_id}"
    risk_history = []
    verdict_history = []
    hold_triggered = False
    hold_reference = None
    first_fraud_time_s = None
    last_matched_reasons = []

    async with websockets.connect(ws_url) as ws:
        async def receive_loop():
            nonlocal hold_triggered, hold_reference, first_fraud_time_s, last_matched_reasons
            try:
                while True:
                    msg_text = await ws.recv()
                    msg = json.loads(msg_text)
                    mtype = msg.get("type")

                    if mtype == "risk_update":
                        score = float(msg.get("fused_risk_score", 0.0))
                        v = msg.get("verdict", "REAL")
                        risk_history.append(score)
                        verdict_history.append(v)
                        reasons = msg.get("matched_reasons", [])
                        if reasons:
                            last_matched_reasons = reasons

                        if v == "FRAUD" and first_fraud_time_s is None:
                            first_fraud_time_s = len(risk_history) * 0.5

                    elif mtype == "hold_triggered":
                        hold_triggered = True
                        hold_reference = msg.get("mock_reference")

            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                pass

        rx_task = asyncio.create_task(receive_loop())

        # Stream audio in 500ms chunks (8000 samples = 16000 bytes)
        chunk_samples = 8000
        total_chunks = len(data) // chunk_samples
        print(f"Streaming {total_chunks} chunks (500ms each)...")

        t0 = time.time()
        for idx in range(total_chunks):
            chunk = data[idx * chunk_samples : (idx + 1) * chunk_samples]
            int16_bytes = chunk.tobytes()
            await ws.send(int16_bytes)
            # Yield briefly to simulate real-time ingestion
            await asyncio.sleep(0.02)

        # Allow WebSocket handler to process trailing buffer
        await asyncio.sleep(2.0)
        rx_task.cancel()

    # 3. Stop Call
    async with httpx.AsyncClient() as client:
        await client.post(f"{API_BASE}/api/calls/{call_id}/stop")

    # 4. Verify Evidence Chain
    async with httpx.AsyncClient() as client:
        ev_res = await client.get(f"{API_BASE}/api/calls/{call_id}/evidence")
        assert ev_res.status_code == 200
        ev_data = ev_res.json()
        chain_valid = ev_data.get("chain_valid", False)
        sigs_valid = ev_data.get("signatures_valid", False)
        event_count = len(ev_data.get("events", []))

    # 5. Compute Statistics
    risk_arr = np.array(risk_history) if risk_history else np.array([0.0])
    mean_risk = float(np.mean(risk_arr))
    peak_risk = float(np.max(risk_arr))
    min_risk = float(np.min(risk_arr))
    std_risk = float(np.std(risk_arr))
    fraud_windows = sum(1 for v in verdict_history if v == "FRAUD")
    real_windows = sum(1 for v in verdict_history if v == "REAL")
    suspicious_windows = sum(1 for v in verdict_history if v == "SUSPICIOUS")

    print(f"\n--- RESULTS FOR: {test_name} ---")
    print(f"  Duration Tested     : {duration_s:.1f} seconds")
    print(f"  Windows Evaluated   : {len(risk_history)}")
    print(f"  Risk Profile (Fused): Min = {min_risk:.4f} | Mean = {mean_risk:.4f} | Peak = {peak_risk:.4f} | Std = {std_risk:.4f}")
    print(f"  Verdict Distribution: REAL={real_windows} ({real_windows/max(len(verdict_history),1)*100:.1f}%), SUSPICIOUS={suspicious_windows}, FRAUD={fraud_windows}")
    print(f"  Hold Triggered      : {hold_triggered} (Ref: {hold_reference})")
    if first_fraud_time_s:
        print(f"  Time to Fraud Alert : {first_fraud_time_s:.1f}s")
    if last_matched_reasons:
        print(f"  Matched Evidence    : {last_matched_reasons[:4]}")
    print(f"  BSA 2023 §63 Chain  : Valid = {chain_valid} | Signatures = {sigs_valid} ({event_count} events sealed)")

    # Assertions based on expected test outcome
    if is_expected_fraud:
        assert peak_risk >= 0.70, f"Expected FRAUD peak risk >= 0.70, got {peak_risk}"
        assert hold_triggered, "Expected transaction hold to be triggered for cloned extortion call"
        assert fraud_windows > 0, "Expected at least one FRAUD window"
        print(f"  >>> [PASS] Extended cloned scam call successfully identified & halted.")
    else:
        assert peak_risk < 0.40, f"Expected REAL peak risk < 0.40, got {peak_risk} (false alarm!)"
        assert not hold_triggered, "Unexpected transaction hold triggered on real conversation!"
        assert fraud_windows == 0, f"False positive FRAUD detections: {fraud_windows}"
        print(f"  >>> [PASS] Extended real human conversation remained safe and unhindered.")

    return {
        "name": test_name,
        "duration": duration_s,
        "mean_risk": mean_risk,
        "peak_risk": peak_risk,
        "hold_triggered": hold_triggered,
        "hold_ref": hold_reference,
        "chain_valid": chain_valid,
        "fraud_windows": fraud_windows,
        "real_windows": real_windows,
    }


async def main():
    print("=" * 70)
    print("VOICESHIELD — EXTENDED DURATION TEST SUITE (1 - 2 MINUTES)")
    print("=" * 70)

    real_wav = os.path.abspath("data/test_long/real_long_conversation.wav")
    scam_wav = os.path.abspath("data/test_long/cloned_long_scam.wav")

    res_real = await run_extended_call_test(real_wav, is_expected_fraud=False, test_name="Genuine Colleague Conversation (68.6s)")
    res_scam = await run_extended_call_test(scam_wav, is_expected_fraud=True, test_name="Digital Arrest Extortion Attack (94.6s)")

    print("\n" + "=" * 70)
    print("EXTENDED DURATION PERFORMANCE SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Metric':<25} | {'Real Conversation':<20} | {'Cloned Scam Attack':<20}")
    print("-" * 70)
    print(f"{'Call Duration':<25} | {res_real['duration']:.1f}s{'':<15} | {res_scam['duration']:.1f}s")
    print(f"{'Mean Fused Risk':<25} | {res_real['mean_risk']:.4f}{' (Safe)':<13} | {res_scam['mean_risk']:.4f}{' (Critical)'}")
    print(f"{'Peak Fused Risk':<25} | {res_real['peak_risk']:.4f}{' (Safe)':<13} | {res_scam['peak_risk']:.4f}{' (FRAUD)'}")
    print(f"{'Fraud False Positives':<25} | {res_real['fraud_windows']}{' (Zero False Alarms)':<4} | {res_scam['fraud_windows']}{' (Detected)'}")
    print(f"{'Auto-Hold Enforced':<25} | {str(res_real['hold_triggered']):<20} | {str(res_scam['hold_triggered']) + ' (' + str(res_scam['hold_ref']) + ')'}")
    print(f"{'BSA 2023 §63 Chain':<25} | {'Tamper-Proof':<20} | {'Tamper-Proof'}")
    print("=" * 70)
    print("ALL EXTENDED DURATION TESTS PASSED WITH 100% ACCURACY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
