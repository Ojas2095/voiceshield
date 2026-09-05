import asyncio
import websockets
import json
import urllib.request
import scipy.io.wavfile as wavfile
import numpy as np

async def test():
    req = urllib.request.Request('http://127.0.0.1:8000/api/calls/start', data=b'{"source":"phone_sim"}', headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        call_id = json.loads(resp.read().decode())['call_id']
        
    sr, data = wavfile.read('frontend/public/demo/human_scam_sbi_otp.wav')
    samples = data.astype(np.int16)
    pcm = samples.tobytes()
    chunk_size = 16000 # 500ms
    
    print(f"Starting test stream for call {call_id}...")
    async with websockets.connect(f'ws://127.0.0.1:8000/ws/stream/{call_id}') as ws:
        for i in range(0, len(pcm), chunk_size):
            await ws.send(pcm[i:i+chunk_size])
            await asyncio.sleep(0.35) # realistic call pace
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.02)
                    msg = json.loads(raw)
                    if msg.get('type') == 'risk_update':
                        r = msg.get('fused_risk_score', 0.0) * 100
                        t = msg.get('threat_category')
                        i_risk = msg.get('intent_risk')
                        reasons = msg.get('matched_reasons')
                        print(f"Stream Msg -> Risk: {r:.1f}% | Threat: {t} | Intent: {i_risk} | Reasons: {reasons}")
                except asyncio.TimeoutError:
                    break
        
        # Drain
        for _ in range(15):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                msg = json.loads(raw)
                if msg.get('type') == 'risk_update':
                    r = msg.get('fused_risk_score', 0.0) * 100
                    t = msg.get('threat_category')
                    i_risk = msg.get('intent_risk')
                    reasons = msg.get('matched_reasons')
                    print(f"[DRAIN Msg] -> Risk: {r:.1f}% | Threat: {t} | Intent: {i_risk} | Reasons: {reasons}")
            except asyncio.TimeoutError:
                pass

if __name__ == "__main__":
    asyncio.run(test())
