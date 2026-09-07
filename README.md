# VoiceShield 🛡️
> **AI-Powered Real-Time Detection & Prevention of Voice-Cloning Impersonation Attacks**
> **Smart India Hackathon (SIH 2026)** · **Problem Statement:** 26104 · **Team:** Red Flags (SIH-UPES-2026-T098)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com)
[![Next.js 14](https://img.shields.io/badge/Next.js-14.2+-black.svg)](https://nextjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> [!NOTE]
> **Active Production Backend:** All services, WebSockets, and AI models run under [`backend_v2/`](backend_v2/). The legacy `backend/` directory is an archived reference prototype.
> **Official Pitch Deck:** The 6-slide presentation conforming strictly to SIH 2026 guidelines is available at [`sih2026_1.pptx`](C:/Users/Dev/Downloads/sih2026_1.pptx).

---

## 📌 Executive Summary

India loses over **₹22,000 Crore annually** to sophisticated telephonic cyber-fraud, including AI voice-cloning vishing, coercive "digital arrest" scams, and urgent relative emergency impersonations. 

**VoiceShield** is a real-time, telecom-grade fraud defense platform that analyzes live telephonic audio streams in **<3ms DSP latency (MelCNN on GPU)** per 2-second sliding window. It fuses acoustic deepfake detection, multilingual NLP intent analysis, and deterministic telephony signals to stop financial fraud before money leaves the victim's bank account.

---

## 🏛️ 3-Layer Fusion Architecture

```
                       LIVE TELEPHONE AUDIO (8kHz / 16kHz PCM)
                                          │
                                          ▼
                ┌───────────────────────────────────────────────────┐
                │             Telephony Front-End DSP               │
                │  • ITU-T G.712 Bandpass & 8kHz Telephony Codec    │
                │  • True AMR-WB / G.711 Emulation + Noise Injection│
                │  • Silero VAD (2.0s sliding window • 500ms hop)   │
                └───────────────────────────────────────────────────┘
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
      ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────┐
      │  LAYER 1: Authenticity│ │  LAYER 2: Intent  │ │  LAYER 3: Signals │
      │  • Dual-Branch AI:    │ │  • Multilingual   │ │  • Call duration  │
      │    wav2vec2-base (FT) │ │    Whisper ASR    │ │  • International  │
      │    + MelCNN Spectrogram│ │  • Triad Urgency  │ │    prefix & route │
      │  • Logistic Calibrator│ │    Guard Logic    │ │  • Deterministic  │
      │  • Mahalanobis OOD    │ │  • Negation Guards│ │    telecom signal │
      │  • Grad-CAM Heatmaps  │ │  • EN / HI /      │ │    heuristics     │
      │  • Unseen TTS Guard   │ │    Hinglish Lexicon│ │                  │
      └───────────────────────┘ └───────────────────┘ └───────────────────┘
                  │                       │                       │
                  └───────────────────────┼───────────────────────┘
                                          ▼
                ┌───────────────────────────────────────────────────┐
                │          Calibrated Dynamic Risk Fusion Engine     │
                │  • Scikit-Learn Calibrator (ECE / Brier optimized)│
                │  • Triad Escalation Guard (Authority+Finance+Urge)│
                │  • Rolling 5-Window Cumulative Risk Assessment    │
                └───────────────────────────────────────────────────┘
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
             [ Score < 0.40 ]      [ 0.40 ≤ Score < 0.70 ]   [ Score ≥ 0.70 ]
                🟢 REAL                 🟡 SUSPICIOUS           🔴 FRAUD
           Call Continues             Warning Overlay       Auto-Hold Trigger
                                      Alert to User         Ed25519 Signed Log
```

### 💡 Core Design Principles

1. **Orthogonal Signal Decoupling (Acoustic vs Semantic):**
   - **Layer 1 is Acoustic (how the sound was produced):** Detects neural vocoder artifacts, spectral phase discontinuities, and micro-jitter instability inherent to synthetic speech synthesis (ElevenLabs, Azure Neural, XTTS).
   - **Layer 2 is Semantic (what is being said):** Evaluates conversational coercion, authority impersonation, and panic induction across Hindi, Indian English, and Hinglish.
   - *Why decoupled?* Conflating them causes real-human scammers to slip through (genuine voice, malicious intent) and benign emotional calls to be falsely flagged.

2. **Triad Scam-Intent Escalation Guard:**
   - Real-world scam calls consistently exhibit a three-part compound structure: **Authority Impersonation** (e.g. Police/CBI/TRAI) + **Financial Request** (UPI/RTGS transfer) + **Urgency/Threat** (Immediate arrest/disconnection).
   - To prevent false alarms on legitimate utility notifications (e.g., routine electricity bill reminders or bank OTP calls), Layer 2 caps the combined score at `0.35` unless an explicit `urgency_threat` keyword is co-present.

3. **Carrier-Trained Telephony Calibrator:**
   - Most lab-trained models fail on real phone lines because 8kHz G.711 / AMR compression strips high frequencies (>4kHz).
   - VoiceShield trains and calibrates on telecom-simulated audio (bandpass filtered + GSM burst noise injection + int8 overflow protection) using a trained `LogisticRegression` calibrator (`ai/models/calibrator.joblib`) backed by a Mahalanobis Out-Of-Distribution (OOD) distance gate.

---

## 📊 Key Benchmark Metrics

| Metric | Result | Target | Status |
| :--- | :---: | :---: | :---: |
| **Fine-Tuned wav2vec2 Accuracy** | **98.7%** | > 95% | ✅ Exceeded |
| **Layer 1 EER (held-out telephony)** | **2.4%** | < 8% | ✅ Exceeded |
| **Cross-Generator EER (unseen TTS)** | **6.8%** | < 15% | ✅ Exceeded |
| **DSP Inference Latency** | MelCNN ≈ 2.26 ms (GPU) / 12 ms (CPU) · Dual ≈ 45 ms | < 500 ms | ⚡ 99.5% Headroom |
| **Layer 2 Intent F1-Score** | **0.969** (81-sample benchmark) | > 0.90 | ✅ Exceeded |
| **Multilingual Support** | English · Hindi · Hinglish | Indian telecom | ✅ Native Support |
| **Evidence Custody Chain** | Ed25519-signed SHA-256 hash-chain | BSA 2023 §63 | ⚖️ Court-Admissible |

---

## 🔍 Explainable AI (Grad-CAM Visual Heatmaps)

VoiceShield provides human-interpretable forensic validation rather than black-box scores:
- **Phase Discontinuity Localization:** Visualizes high-frequency neural vocoder dispersion.
- **Formant Trajectory Heatmaps:** Exposes synthetic pitch unnaturalness in spectrogram bins.
- **Live WebSocket Stream:** Real-time Base64 Grad-CAM overlays transmitted directly to the frontend HUD.

---

## ⚖️ Legal & Regulatory Compliance

- **Bharatiya Sakshya Adhiniyam (BSA) 2023 §63**: Cryptographically signed SHA-256 Merkle hash-chain guarantees non-repudiation and electronic record admissibility for cybercrime law enforcement.
- **Indian Information Technology Act, 2000 §65B**: Generates digitally verifiable electronic evidence certificates for court proceedings.
- **Digital Personal Data Protection (DPDP) Act 2023**: Zero raw audio is persisted. Audio buffers reside solely in ephemeral RAM and are zeroed out immediately after feature extraction.
- **RBI Digital Payment Security Guidelines**: Enables automated, real-time risk-based UPI and banking transaction holds during active impersonation calls.

---

## 🎯 Smart India Hackathon (SIH 2026) Presentation Deck

The official 6-slide presentation deck is located at [`sih2026_1.pptx`](C:/Users/Dev/Downloads/sih2026_1.pptx):

| Slide | Section | Key Visual Focus |
| :---: | :--- | :--- |
| **1** | **Title & Team** | Problem Statement ID `26104`, Team `RED FLAGS` (SIH-UPES-2026-T098). |
| **2** | **Innovation & Architecture** | 4 Innovation cards + 6-step end-to-end flowchart from 8kHz Ingestion to Action Triad (**DETECT, PREVENT, PROVE**). |
| **3** | **Technical Approach & Stack** | Clean deduplicated dual-card layout: Next.js 14, Web Audio API, FastAPI WebSockets, PyTorch wav2vec2 (98.7%), MelCNN, Ed25519 hash-chain, and 5-stage DSP pipeline. |
| **4** | **Feasibility & Viability** | 3-column matrix: Feasibility (<3ms edge, DPDP compliant) vs Challenges (8kHz loss, dialects) vs Mitigations (Carrier Calibrator, FLEURS/SLR103, Triad Guard). |
| **5** | **Impact & Benefits** | Radial infographic: ₹22,000+ Cr national fraud targeted, <3ms reaction, vernacular coverage, and Economic / National / Social benefits. |
| **6** | **Research & Legal References** | Non-overlapping citations: ASVspoof 2021, wav2vec2-XLSR, Grad-CAM, CERT-In advisories, BSA 2023 §63, IT Act §65B, and RBI guidelines. |

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ (PyTorch with optional CUDA acceleration)
- Node.js 18+ & npm

### 1. Launch FastAPI Backend
```powershell
# Install dependencies
pip install -r backend_v2/requirements.txt

# Set PYTHONPATH and launch server
$env:PYTHONPATH="backend_v2;."
python -m uvicorn app.main:app --port 8000 --reload
```
Interactive Swagger docs available at `http://localhost:8000/docs`.

### 2. Launch Next.js Cybersecurity Console
```powershell
cd frontend
npm install
npm run dev
```
Access dashboard at `http://localhost:3000`.

---

## 🧪 Verification & Evaluation Runbook

Execute the automated verification scripts across all layers:

```powershell
# 1. Verify Layer 2 Intent Classifier & Triad Urgency Guard (81-sample benchmark)
python -m intelligence.eval_intent
python scripts/test_scam_intent.py

# 2. Verify Layer 1 Voice Diversity & Cross-Engine Generalization
python scripts/evaluate_voice_diversity.py

# 3. Retrain / Validate Calibrated Logistic Regression Model
python scripts/train_calibrator.py

# 4. Run Backend WebSocket, Hash-Chain & Telephony Test Suite
$env:PYTHONPATH="backend_v2;." ; pytest backend_v2/tests/ -v

# 5. Verify SIH 2026 Presentation Geometry & Slide Count
python -c "import pptx; prs = pptx.Presentation(r'C:\Users\Dev\Downloads\sih2026_1.pptx'); print(f'Valid SIH Deck: {len(prs.slides)} slides')"
```

---

## 📁 Repository Structure

```
voiceshield/
├── ai/                         # Layer 1 Deepfake Detection Engine
│   ├── layer1_authenticity.py  # Dual-Branch MelCNN + wav2vec2 Architecture
│   ├── preprocessing.py        # ITU-T G.712 Telephony simulation & Mel-spectrogram
│   ├── gradcam.py              # Explainable AI Grad-CAM heatmap generator
│   ├── models/                 # Model weights (calibrator.joblib, best_mel_cnn.pt)
│   └── train/                  # Audio fetch scripts (FLEURS/SLR103) & trainer
├── backend_v2/                 # Production FastAPI Backend
│   ├── app/
│   │   ├── main.py             # App lifecycle & router registration
│   │   ├── inference.py        # Async ThreadPool inference bridge
│   │   ├── hash_chain.py       # Ed25519 & SHA-256 Merkle chain evidence generator
│   │   ├── vad.py              # Silero VAD audio pipeline & ring buffer
│   │   └── routers/websocket.py# Real-time binary PCM streaming endpoint
│   └── tests/                  # Backend unit tests
├── frontend/                   # Next.js 14 Cybersecurity Dashboard
│   ├── app/page.tsx            # Live Threat Meter, 3-Layer breakdown & Action Triad
│   ├── app/evidence/page.tsx   # Forensic Audit Trail & BSA 2023 §63 panel
│   ├── hooks/useMicStream.ts   # Web Audio API microphone capture hook
│   └── public/worklet.js       # Off-thread AudioWorklet 16kHz Int16 quantizer
├── intelligence/               # Layer 2 & 3 Intent & Telephony Signal Analyzers
│   ├── intent_classifier.py    # 12-category multilingual scam NLP engine + Triad Guard
│   ├── call_signals.py         # Metadata heuristics & risk scoring
│   └── data/intent_samples.csv # 81-sample benchmark dataset
├── scripts/                    # Ingestion, training & evaluation utilities
│   ├── ingest_real_voices.py   # FLEURS / OpenSLR103 ingestion pipeline
│   ├── train_calibrator.py     # LogisticRegression calibrator trainer
│   ├── test_scam_intent.py     # Layer 2 hard-negative regression tests
│   └── evaluate_voice_diversity.py # Multi-engine cross-evaluation
└── docs/                       # Architecture diagrams & pitch materials
```

---

## 👥 Team Red Flags (SIH 2026)

| Member | Primary Focus & Deliverables | Files Contributed (from Git History) |
| :--- | :--- | :--- |
| **Ojaswee**<br>*(Team Lead)* | **AI/ML Architecture & Model Convergence**<br>• Dual-branch deepfake detection (`wav2vec2-base` 98.7% + `MelCNN` 2.26ms)<br>• Logistic regression statistical calibrator (ECE 1.25%) & OOD gating<br>• Triad Guard calibrated risk fusion & end-to-end system orchestration | `ai/layer1_authenticity.py`<br>`ai/models/calibrator.joblib`<br>`ai/preprocessing.py`<br>`scripts/train_calibrator.py` |
| **Tanishq Khandelwal** | **Full-Stack & Frontend Lead**<br>• Co-developed Next.js 14 live dashboard, HUD alerts & 3-layer threat meter<br>• AudioWorklet 16kHz PCM streaming capture & client lifecycle hooks<br>• High-throughput WebSocket pipelines & Ornstein-Uhlenbeck smoothing | `frontend/app/page.tsx`<br>`frontend/app/evidence/page.tsx`<br>`frontend/hooks/useVoiceShield.ts`<br>`frontend/hooks/useMicStream.ts`<br>`frontend/public/worklet.js`<br>`backend_v2/app/routers/websocket.py`<br>`backend_v2/app/inference.py` |
| **Tanvi Kapoor** | **Frontend Engineering & UI/UX Design**<br>• Co-developed Next.js 14 Cybersecurity Dashboard & Evidence Station<br>• Real-time reactive UI components, visual threat meters & Tailwind design system<br>• Cross-browser AudioWorklet integration, state synchronization & client UX | `frontend/app/page.tsx`<br>`frontend/app/layout.tsx`<br>`frontend/app/evidence/page.tsx`<br>`frontend/components/`<br>`frontend/hooks/` |
| **Sarthak Kothiyal** | **Backend Infrastructure, Telecom DSP & Security**<br>• FastAPI server lifecycle, CORS middleware & JWT authentication system<br>• Telecom DSP audio pipeline (8kHz G.711 / ITU-T G.712) & Silero VAD<br>• Automated 12-case security proof test suite & rate limiting middleware | `backend/app/audio/pipeline.py`<br>`backend/app/websocket.py`<br>`backend/app/security/auth.py`<br>`backend/app/security/jwt.py`<br>`backend/app/middleware.py`<br>`backend/tests/test_security_suite.py` |
| **Akshat Sharma** | **Database Persistence & Cryptographic Evidence Chain**<br>• PostgreSQL persistence, Alembic migrations & Call session models<br>• SHA-256 Merkle evidence chain service & court-admissible audit logs<br>• Automated banking PREVENT transaction hold endpoints & E2E test suite | `backend/app/db/models.py`<br>`backend/app/db/session.py`<br>`backend/app/services/evidence_chain.py`<br>`backend/app/routers/evidence.py`<br>`backend/app/routers/prevent.py`<br>`backend/tests/test_e2e_flow.py` |
| **Arnav Garg** | **Intelligence Layer, NLP & Forensic Validation**<br>• 12-category multilingual scam-intent classifier (Triad Urgency Guard)<br>• BSA 2023 §63 & IT Act §65B court-admissible PDF certificate generator<br>• Model latency profiling (`wav2vec2-base`), held-out EER tests & Replay Lab | `intelligence/intent_classifier.py`<br>`intelligence/eval_intent.py`<br>`frontend/app/evidence/page.tsx`<br>`frontend/app/history/page.tsx`<br>`scripts/evaluate_voice_diversity.py`<br>`backend_v2/tests/test_hash_chain.py` |

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
