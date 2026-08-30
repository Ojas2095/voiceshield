# VoiceShield

> AI-Powered Real-Time Detection & Prevention of Voice Cloning Impersonation Attacks

**Team Red Flags** · SIH 2026 · PS-104

## Architecture

```
LIVE CALL AUDIO (phone / VoIP / mic)
        │  TLS 1.3 (encrypted)
        ▼
  Telephony Front-End (8kHz resample · codec/noise · VAD)
        │
   ┌────┼────┐
   ▼    ▼    ▼
 Layer1 Layer2 Layer3
 Voice  Intent Call
 Auth.  (ASR)  Signals
   └────┼────┘
        ▼
   Risk Fusion (0–100)
        │
  ┌─────┼─────┐
  ▼     ▼     ▼
DETECT PREVENT PROVE
```

## Tech Stack

| Component  | Technology                                |
|------------|-------------------------------------------|
| AI/ML      | PyTorch, wav2vec2-XLSR, librosa, Grad-CAM |
| Backend    | FastAPI, PostgreSQL, Ed25519 signing       |
| Frontend   | React / Next.js, Tailwind CSS, AudioWorklet|
| ASR        | Whisper (faster-whisper)                   |

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Team

| Pod                   | Owns                                            |
|-----------------------|-------------------------------------------------|
| AI/ML (2 members)    | Layer 1, preprocessing, training, Grad-CAM       |
| Backend/Intel (2)     | FastAPI, WebSocket, evidence chain, Layers 2 & 3 |
| Frontend (2)          | Dashboard, mic capture, risk meter, PDF export   |

## License

MIT
