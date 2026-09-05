import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import asyncio
import json
import time
import os
import glob
import numpy as np
import scipy.io.wavfile as wavfile
import websockets
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

async def test_audio_file(file_path: str, expected_voice: str, expected_threat: str):
    print(f"\n========================================================")
    print(f"Testing: {os.path.basename(file_path)}")
    print(f"Expected Voice: {expected_voice} | Expected Threat: {expected_threat}")
    print(f"========================================================")
    
    # 1. Start call
    req = urllib.request.Request(f"{BASE_URL}/api/calls/start", data=json.dumps({"source": "phone_sim"}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        call_id = json.loads(resp.read().decode())["call_id"]
        
    sr, data = wavfile.read(file_path)
    if data.ndim > 1: data = data[:, 0]
    if sr != 16000:
        # resample to 16k
        import scipy.signal
        samples = scipy.signal.resample(data, int(len(data) * 16000 / sr)).astype(np.int16)
    else:
        samples = data.astype(np.int16)
        
    pcm_bytes = samples.tobytes()
    chunk_size = 16000 # 500ms chunk
    
    last_threat = "UNKNOWN"
    last_voice = "UNKNOWN"
    last_verdict = "UNKNOWN"
    max_risk = 0.0
    hold_triggered = False
    reasons = []
    transcripts = []
    
    async with websockets.connect(f"{WS_URL}/ws/stream/{call_id}", ping_interval=None, ping_timeout=None) as ws:
        chunks_to_send = list(range(0, len(pcm_bytes), chunk_size))[:70]  # Up to 35s of audio
        for i in chunks_to_send:
            chunk = pcm_bytes[i:i+chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.12)
            
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.05)
                    msg = json.loads(raw)
                    if msg.get("type") == "risk_update":
                        last_threat = msg.get("threat_category", last_threat)
                        last_voice = msg.get("voice_classification", last_voice)
                        last_verdict = msg.get("verdict", last_verdict)
                        max_risk = max(max_risk, msg.get("fused_risk_score", 0.0))
                        if msg.get("matched_reasons"):
                            reasons = msg.get("matched_reasons")
                        if msg.get("transcript"):
                            transcripts.append(msg.get("transcript"))
                    elif msg.get("type") == "hold_triggered":
                        hold_triggered = True
                except asyncio.TimeoutError:
                    break
            
            # Early exit if pass criteria already achieved
            if (last_voice == expected_voice) and (last_threat == expected_threat) and (not (expected_threat in ("HUMAN_VISHING", "AI_SYNTHETIC")) or hold_triggered):
                break
                    
        # Drain remaining messages to capture background ASR completion
        for _ in range(25):
            if (last_voice == expected_voice) and (last_threat == expected_threat):
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.3)
                msg = json.loads(raw)
                if msg.get("type") == "risk_update":
                    last_threat = msg.get("threat_category", last_threat)
                    last_voice = msg.get("voice_classification", last_voice)
                    last_verdict = msg.get("verdict", last_verdict)
                    max_risk = max(max_risk, msg.get("fused_risk_score", 0.0))
                    if msg.get("matched_reasons"):
                        reasons = msg.get("matched_reasons")
                    if msg.get("transcript"):
                        transcripts.append(msg.get("transcript"))
                elif msg.get("type") == "hold_triggered":
                    hold_triggered = True
            except asyncio.TimeoutError:
                pass

    print(f"Result -> Threat: {last_threat} | Voice: {last_voice} | Verdict: {last_verdict} | Max Risk: {max_risk*100:.1f}% | Hold: {hold_triggered}")
    if reasons:
        print(f"Matched Reasons: {reasons}")
    if transcripts:
        print(f"Transcript Snippet: {transcripts[-1][:120]}...")
        
    # Check correctness
    voice_ok = (last_voice == expected_voice)
    threat_ok = (last_threat == expected_threat)
    status = "[PASS]" if (voice_ok and threat_ok) else "[FAIL]"
    print(f"Status: {status} (Voice: {voice_ok}, Threat: {threat_ok})")
    return voice_ok and threat_ok

async def main():
    tests = [
        ("data/test_long/real_long_conversation.wav", "HUMAN", "LEGITIMATE_HUMAN"),
        ("frontend/public/demo/human_scam_sbi_otp.wav", "HUMAN", "HUMAN_VISHING"),
        ("frontend/public/demo/human_scam_customs_parcel.wav", "HUMAN", "HUMAN_VISHING"),
        ("frontend/public/demo/human_scam_electricity_hi.wav", "HUMAN", "HUMAN_VISHING"),
        ("frontend/public/demo/cloned_long_scam.wav", "SYNTHETIC", "AI_SYNTHETIC"),
        ("frontend/public/demo/cloned_en.wav", "SYNTHETIC", "AI_SYNTHETIC"),
    ]
    
    results = []
    for path, exp_v, exp_t in tests:
        if os.path.exists(path):
            ok = await test_audio_file(path, exp_v, exp_t)
            results.append((os.path.basename(path), ok))
        else:
            print(f"File not found: {path}")
            
    print("\n========================================================")
    print("FINAL SUMMARY:")
    for name, ok in results:
        print(f"  {name:35} : {'PASS' if ok else 'FAIL'}")
    print("========================================================")

if __name__ == "__main__":
    asyncio.run(main())
