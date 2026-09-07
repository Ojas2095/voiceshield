# VoiceShield — Team Contributions & Work Distribution
**Smart India Hackathon (SIH 2026)**  
**Problem Statement ID:** 26104 — *AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks*  
**Team ID:** SIH-UPES-2026-T098  
**Team Name:** RED FLAGS  

---

## 👥 Executive Summary of Roles & Deliverables

| Teammate | Primary Role | Core Engineering Deliverables | Files Contributed (from Git History) |
| :--- | :--- | :--- | :--- |
| **Ojaswee** | **Team Lead & AI/ML Architecture** | Dual-Branch AI (wav2vec2-base 98.7% + MelCNN 2.26ms), statistical calibrator, Triad risk fusion, end-to-end orchestration | i/layer1_authenticity.py, i/models/calibrator.joblib, i/preprocessing.py, scripts/train_calibrator.py |
| **Tanishq Khandelwal** | **Full-Stack & Frontend Lead** | Next.js 14 Cybersecurity Dashboard, AudioWorklet 16kHz PCM streaming capture, client lifecycle hooks, WebSocket streaming integration, OU process | rontend/app/page.tsx, rontend/app/evidence/page.tsx, rontend/hooks/useVoiceShield.ts, rontend/hooks/useMicStream.ts, rontend/public/worklet.js, ackend_v2/app/routers/websocket.py, ackend_v2/app/inference.py |
| **Tanvi Kapoor** | **Frontend Engineering & UI/UX Design** | Next.js 14 UI architecture, responsive cybersecurity console, Evidence Station, real-time threat meters, Tailwind design system, cross-browser UX | rontend/app/page.tsx, rontend/app/layout.tsx, rontend/app/evidence/page.tsx, rontend/components/, rontend/hooks/ |
| **Sarthak Kothiyal** | **Backend Infrastructure & Security** | FastAPI server lifespan, CORS & dependencies, JWT authentication & call authorization, DSP audio pipeline (8kHz G.711 / G.712), Silero VAD, automated 12-case security proof suite | ackend/app/main.py, ackend/app/config.py, ackend/app/security/auth.py, ackend/app/security/jwt.py, ackend/app/audio/pipeline.py, ackend/app/websocket.py, ackend/app/middleware.py, ackend/tests/test_security_suite.py |
| **Akshat Sharma** | **Database Persistence & Evidence Chain** | PostgreSQL persistence, Alembic migrations, Call session models, cryptographic SHA-256 Merkle evidence chain service, PREVENT transaction hold endpoints, E2E test suite | ackend/app/db/models.py, ackend/app/db/session.py, ackend/app/services/evidence_chain.py, ackend/app/routers/evidence.py, ackend/app/routers/prevent.py, ackend/tests/test_e2e_flow.py |
| **Arnav Garg** | **Intelligence Layer & Forensic Validation** | 12-category multilingual scam-intent classifier (Triad Urgency Guard), BSA 2023 §63 & IT Act §65B court-admissible PDF certificate generator, Replay Lab benchmarking, held-out EER tests | intelligence/intent_classifier.py, intelligence/eval_intent.py, rontend/app/evidence/page.tsx, rontend/app/history/page.tsx, scripts/evaluate_voice_diversity.py, ackend_v2/tests/test_hash_chain.py |

---

## 📌 Detailed Individual Contributions

### 1. Ojaswee — Team Lead & AI/ML Lead
- **Multimodal AI Architecture**: Architected the 3-layer decoupled fusion design separating acoustic authenticity (Layer 1) from conversational intent (Layer 2) and deterministic telecom heuristics (Layer 3).
- **Acoustic Model Training (i/)**:
  - Fine-tuned the wav2vec2-base acoustic representation head (i/train/train_head.py, i/models/best_wav2vec_head.pt) achieving **98.7% validation accuracy** on telephony speech.
  - Trained the lightweight MelCNN spectrogram model (i/models/best_mel_cnn.pt), clocking **2.26ms GPU / 12ms CPU** inference latency.
  - Integrated Grad-CAM explainable AI (i/gradcam.py) generating live spectrogram heatmaps of neural vocoder phase artifacts.
- **Calibrator & Out-Of-Distribution (OOD) Guard**:
  - Replaced legacy heuristic scoring with a trained LogisticRegression calibrator (i/models/calibrator.joblib) with Brier score .1273$ and Expected Calibration Error (ECE) optimization.
  - Implemented Mahalanobis distance gating to flag Out-of-Distribution audio without triggering false alarms.
- **Team Leadership**: Spearheaded model convergence, managed task handoffs, and ensured end-to-end integration between AI, backend, and frontend systems.

---

### 2. Tanishq Khandelwal — Full-Stack & Frontend Lead
- **Next.js 14 Cybersecurity Dashboard (rontend/)**:
  - Built the primary command console (rontend/app/page.tsx) with real-time threat meters, 3-layer risk breakdown bars, and Action Triad status indicators.
  - Built the **Evidence Audit Trail page** (rontend/app/evidence/page.tsx) featuring call history tables, cryptographic hash-chain inspection modals, and JSON forensic export.
- **Real-Time Client Audio Streaming**:
  - Implemented off-thread AudioWorklet processor (rontend/public/worklet.js) for non-blocking 500ms audio chunk assembly.
  - Built useMicStream.ts hook capturing 16kHz PCM audio and useVoiceShield.ts managing WebSocket call lifecycles (/ws/stream/{uuid}).
- **Backend Streaming Integration**:
  - Integrated the 3-layer intelligence pipeline into the WebSocket router (ackend_v2/app/routers/websocket.py).
  - Implemented the Ornstein-Uhlenbeck (OU) mean-reverting smoothing process in ackend_v2/app/inference.py to prevent false positives on live human speech.

---

### 3. Tanvi Kapoor — Frontend Engineering & UI/UX Design
- **Cybersecurity Console Architecture (rontend/)**:
  - Co-architected the Next.js 14 / React 18 dark-mode dashboard with Tailwind CSS styling and responsive layout grid.
  - Designed the visual threat gauges, biometric confidence meters, and real-time alert banners for live call fraud intervention.
- **Evidence Station & Forensic UX**:
  - Co-developed the Evidence Station interface (rontend/app/evidence/page.tsx) displaying Ed25519 digital signatures, Merkle root verification, and BSA 2023 §63 legal badges.
  - Structured modular UI component hierarchies (rontend/components/) and centralized client-side environment configurations (rontend/.env.local).
- **Cross-Browser Audio UX & Quality Assurance**:
  - Tested and optimized AudioWorklet buffer handling across Chrome, Edge, and mobile browser runtimes to eliminate audio packet dropouts.

---

### 4. Sarthak Kothiyal — Backend Infrastructure, Telecom DSP & Security
- **Backend Architecture & Config (ackend/app/)**:
  - Developed the FastAPI application skeleton (ackend/app/main.py), application lifespan management, CORS middleware, and environment configuration (ackend/app/config.py).
  - Implemented Call lifecycle API endpoints (ackend/app/routes/calls.py, ackend/app/models/call.py) for call initialization, monitoring, and termination.
- **Telecom DSP Audio Pipeline (ackend/app/audio/)**:
  - Built the real telephony simulation pipeline (ackend/app/audio/pipeline.py) implementing 8kHz downsampling, ITU-T G.712 bandpass filtering, and G.711 codec degradation.
  - Integrated Silero Voice Activity Detection (VAD) and binary WebSocket streaming handler (ackend/app/websocket.py).
- **Security & Rate Limiting (ackend/app/security/)**:
  - Built JWT authentication (ackend/app/security/jwt.py, uth.py) and call ownership verification middleware.
  - Developed the automated 12-case security proof test suite (ackend/tests/test_security_suite.py) and rate-limiting security headers.

---

### 5. Akshat Sharma — Database Persistence & Cryptographic Evidence Chain
- **PostgreSQL Database Architecture (ackend/app/db/)**:
  - Designed relational database schemas and SQLAlchemy ORM models (ackend/app/db/models.py) for calls, detections, evidence logs, and system audits.
  - Authored Alembic database migrations (ackend/alembic/versions/0001_initial_schema.py) and session management (ackend/app/db/session.py).
- **Cryptographic Evidence Chain (ackend/app/services/)**:
  - Implemented SHA-256 Merkle hash-chain service (ackend/app/services/evidence_chain.py) ensuring tamper-proof record-keeping for legal custody.
  - Developed REST API endpoints for evidence verification (ackend/app/routers/evidence.py) and call auditing.
- **PREVENT Intervention & End-to-End Testing**:
  - Built banking API hold endpoints (ackend/app/routers/prevent.py) triggering instant transaction freezes during active fraud calls.
  - Created automated end-to-end integration and evidence verification test suites (ackend/tests/test_e2e_flow.py, 	est_evidence_chain.py).

---

### 6. Arnav Garg — AI Intelligence Layer, NLP & Forensic Validation
- **Layer 2 Multilingual Scam-Intent Classifier (intelligence/)**:
  - Developed 12-category multilingual scam NLP engine (intelligence/intent_classifier.py) covering Hindi, Indian English, and Hinglish.
  - Engineered the **Triad Scam-Intent Escalation Guard** requiring compounding of Authority + Financial + Urgency keywords before escalating fraud risk.
- **BSA 2023 §63 & IT Act §65B Court Evidence Generator**:
  - Engineered printable court-admissible PDF evidence certificate export (rontend/app/evidence/page.tsx, rontend/app/globals.css).
  - Added Ed25519 digital signature and Merkle chain-integrity tests (ackend_v2/tests/test_hash_chain.py).
- **Evaluation & Benchmarking**:
  - Curated 81-sample benchmark dataset (intelligence/data/intent_samples.csv), validating **0.969 intent F1-score**.
  - Sourced and benchmarked real Indian speech datasets (OpenSLR SLR103, FLEURS) and ran cross-generator diversity evaluations.

---

## 🏆 Key Achievements & Validated Metrics
- **98.7% Validation Accuracy**: Fine-tuned wav2vec2-base acoustic classifier.
- **<3ms DSP Latency**: Real-time sliding window inference on consumer GPU.
- **6.8% Cross-Generator EER**: Evaluated on unseen commercial TTS engines (ElevenLabs / Azure Neural).
- **0.969 Intent F1-Score**: Multilingual intent classification on 81 benchmark calls.
- **100% BSA 2023 §63 Compliance**: Tamper-evident Ed25519-signed SHA-256 hash-chains.
- **Strict 6-Slide SIH Compliance Deck**: [VoiceShield_SIH2026_Editable.pptx](C:/Users/Dev/Downloads/VoiceShield_SIH2026_Editable.pptx).
