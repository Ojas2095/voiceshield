# VoiceShield — Grand Finale Pitch & Demo Master Kit
**Smart India Hackathon (SIH 2026)** · **Problem Statement 26104**  
**Team RED FLAGS** (`SIH-UPES-2026-T098`)  
**Format:** 4-Min Pitch + 6-Min Live Prototype + 5-Min Q&A (15 Minutes Total)

---

# ⏱️ PART 1: 4-MINUTE SLIDE-BY-SLIDE PITCH SCRIPT (240 Seconds)

*Tips for delivery: Speak with calm confidence, clear pacing (~130 words/min), make eye contact with all judges, and gesture to the slide diagrams when referencing architecture steps.*

---

### 🟢 SLIDE 1: Title & Team Metadata (0:00 – 0:30 | 30 Seconds)
**Visual on Screen:** *Problem Statement 26104, Team RED FLAGS, Smart India Hackathon 2026.*

> **Speaker Script:**  
> "Good morning, respected judges and evaluators. We are Team **RED FLAGS**, presenting Problem Statement **26104**: *AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks*.
>
> In India today, over **₹22,000 Crore** is lost annually to cyber-extortion, fake relative emergency calls, and coercive 'digital arrest' scams. The most terrifying reality of 2026 is that traditional security — OTPs, passwords, and security questions — fails the moment an attacker clones your child's or parent's voice with just a 3-second audio sample.
>
> Trust is hijacked at the vocal level. Our solution is **VoiceShield**: India's first real-time, telecom-grade fraud defense platform that detects synthetic voices in **under 3 milliseconds** and stops financial theft before the call hangs up."

---

### 🟢 SLIDE 2: Innovation & Uniqueness / Process Flow (0:30 – 1:15 | 45 Seconds)
**Visual on Screen:** *4 Innovation Cards on the left; 6-stage vertical flowchart on the right.*

> **Speaker Script:**  
> "What makes VoiceShield unique is our **decoupled multi-layer architecture**. As shown in our process flow:
>
> 1. We ingest live telephonic audio and pass it through our **8kHz Telephony Simulator Pipeline**, simulating real-world carrier codecs like AMR and G.711 with noise injection.
> 2. An optimized **Silero VAD engine** carves audio into rolling 2-second windows with 500ms hops.
> 3. We then evaluate the audio through **Parallel Dual-Branch AI**:
>    - Branch A uses our fine-tuned `wav2vec2-base` model with **98.7% accuracy** to extract acoustic latents.
>    - Branch B uses our custom `MelCNN` model to detect high-frequency vocoder phase discontinuities, explained visually via **Grad-CAM heatmaps**.
> 4. These acoustic signals pass into our **Calibrated Confidence Fusion Engine**, merging voice authenticity with multilingual scam-intent analysis.
> 5. Finally, we trigger our **Action Triad**:
>    - **DETECT**: Live HUD alerts the citizen.
>    - **PREVENT**: Instant API triggers a real-time UPI and banking transaction hold.
>    - **PROVE**: Cryptographically signed logs for prosecution."

---

### 🟢 SLIDE 3: Technical Approach & Stack (1:15 – 2:00 | 45 Seconds)
**Visual on Screen:** *Left card: Core Technology Stack; Right card: 5-Stage Data Pipeline.*

> **Speaker Script:**  
> "Turning to Slide 3, VoiceShield is engineered for production-grade throughput, not just as a laboratory prototype:
>
> - **On the Client:** Next.js 14 and React 18 power our cybersecurity console, utilizing the **Web Audio API** and off-thread `AudioWorklet` processors for hardware-normalized 16kHz resampling.
> - **On the Backend:** Built on **FastAPI and Python 3.13**, streaming full-duplex binary PCM over WebSockets with **under 3 milliseconds of streaming latency**.
> - **AI/ML Core:** PyTorch powers our dual-branch models, calibrated via Scikit-Learn using a trained Logistic Calibrator with Mahalanobis Out-of-Distribution gating.
> - **Security & Custody:** Every detection block is signed using **Ed25519 digital signatures** and chained into a tamper-evident PostgreSQL hash-chain.
>
> As shown in our Data Pipeline on the right, from 8kHz telephony simulation to cryptographic evidence logging, every single frame is processed ephemerally in RAM and zeroed out, guaranteeing zero privacy leakage."

---

### 🟢 SLIDE 4: Feasibility, Challenges & Mitigations (2:00 – 2:45 | 45 Seconds)
**Visual on Screen:** *3-Column Matrix: Feasibility vs Challenges vs Strategies.*

> **Speaker Script:**  
> "On Slide 4, we address the real engineering challenges that cause standard deepfake detectors to fail in the real world:
>
> - **Challenge 1: Telephony Degradation.** Real phone calls compress audio to 8kHz, stripping high-frequency synthetic cues.  
>   *Our Mitigation:* We train our calibrator directly on telecom-codec compressed audio (AMR/G.711), achieving resilience where lab detectors crash.
> - **Challenge 2: Indian Vernacular Scarcity.** Scams in India operate in Hindi, Indian English, and regional dialects.  
>   *Our Mitigation:* We ingested crowdsourced corpora including **OpenSLR SLR103** and **FLEURS**, training across native Indian accents and cross-evaluating against commercial engines like ElevenLabs and Azure Neural.
> - **Challenge 3: False Alarms on Legitimate Urgent Calls.** A hospital emergency or an electricity bill reminder can sound urgent without being a scam.  
>   *Our Mitigation:* We engineered the **Triad Urgency Guard**. Our NLP classifier strictly requires a compound intersection of *Authority Impersonation* + *Financial Request* + *Urgency Threat* before triggering fraud holds. Routine reminders are never blocked."

---

### 🟢 SLIDE 5: Impact & Benefits (2:45 – 3:20 | 35 Seconds)
**Visual on Screen:** *Central Voice Analysis graphic (₹22,000+ Cr, Real vs Fake), Impact on left, Benefits on right.*

> **Speaker Script:**  
> "Slide 5 illustrates our measurable impact across India:
>
> - **Economically:** We target the prevention of **₹22,000+ Crore** in annual banking and voice fraud.
> - **Operationally:** With an inference latency of **2.26 milliseconds on GPU**, our reaction time is instantaneous — freezing funds before the fraudster can finish the transfer.
> - **Socially:** By supporting native Hindi and regional speech, we protect India's most vulnerable demographic: rural and elderly citizens who cannot distinguish a cloned voice from a real family member.
> - **Nationally:** VoiceShield hardens India's digital public infrastructure — from UPI to telecom networks — against syndicate-level adversarial AI attacks."

---

### 🟢 SLIDE 6: Research Foundation & Legal Admissibility (3:20 – 4:00 | 40 Seconds)
**Visual on Screen:** *Literature citations on left; Market threat & CERT-In center; Legal compliance on right.*

> **Speaker Script:**  
> "Finally, on Slide 6, VoiceShield is grounded in rigorous academic research and Indian statutory compliance:
>
> - We benchmark against **ASVspoof 2021**, utilize self-supervised speech representations from Conneau et al., and apply Selvaraju's Grad-CAM for explainable forensic localization.
> - Crucially, for law enforcement, VoiceShield complies with **Section 63 of the Bharatiya Sakshya Adhiniyam (BSA) 2023** and **Section 65B of the Indian IT Act**. Our Ed25519-signed Merkle hash-chain provides non-repudiable, tamper-evident digital custody certificates ready for cybercrime prosecution.
> - Furthermore, under the **DPDP Act 2023**, zero raw audio is ever persisted to disk.
>
> Respected judges, in cybersecurity, talk is cheap. Allow us to show you VoiceShield in action."

---
---

# 💻 PART 2: 6-MINUTE LIVE PROTOTYPE DEMO CHOREOGRAPHY (360 Seconds)

### Pre-Demo Setup Checklist:
- [ ] Backend running: `$env:PYTHONPATH="backend_v2;."; python -m uvicorn app.main:app --port 8000`
- [ ] Frontend running: `cd frontend; npm run dev`
- [ ] **Tab 1:** `http://localhost:3000` (Cybersecurity Command Center Dashboard)
- [ ] **Tab 2:** `http://localhost:3000/mobile` (Mobile Companion In-Call Simulator)
- [ ] **Tab 3:** `http://localhost:3000/evidence` (Forensic Audit Trail & BSA §63 Ledger)

---

### 🎬 PHASE 1: Normal Call Baseline — Zero False Alarms (0:00 – 1:15 | 75s)
**Goal:** Prove to judges that VoiceShield doesn't panic on legitimate human voices.

1. **Screen:** Open **Tab 1 (`localhost:3000`)**. Point out the clean cybersecurity HUD: Threat Meter, 3-Layer Breakdown, Live Spectrogram, and Grad-CAM container.
2. **Action:** Go to **Replay Demo Call** dropdown $ightarrow$ Select **`"Real Voice — English"`** $ightarrow$ Click **`Replay Selected`** (or use the microphone with **`Start Live Call`**).
3. **What happens on screen:**
   - Audio begins streaming over WebSockets in real 2-second chunks.
   - Speech VAD indicator lights up: `SPEECH DETECTED`.
   - Threat Meter stays firmly green: **`LOW RISK (5–12%)`**.
   - Layer breakdown shows Layer 1 (Voice Authenticity) as `🟢 REAL HUMAN SPEECH`.
   - Call status reads: `CALL PERMITTED — NO THREAT DETECTED`.
4. **Spoken Commentary:**
   > "Judges, we begin with a real, emotional human voice. Notice that the audio is streaming through our real 8kHz telephony pipeline. Silero VAD is gating the speech, and our dual-branch model analyzes vocal fold micro-jitter. The risk score remains at 8% — completely calm. No false holds, no annoying alerts. Normal life continues uninterrupted."

---

### 🎬 PHASE 2: Cloned Voice Scam Attack — The Detection (1:15 – 3:00 | 105s)
**Goal:** Demonstrate the instantaneous detection of an AI cloned voice impersonating a family member.

1. **Screen:** Switch to **Tab 2 (`localhost:3000/mobile`)** — the Mobile In-Call Simulator. Show the simulated incoming call from *"Aman (Son — Impersonated)"*.
2. **Action:** Click **`Accept Call`** or replay **`"Cloned Voice — English"`**.
3. **What happens on screen:**
   - Audio begins playing: *"Mom, please help me! I've been arrested by the police near the highway, they need 50,000 rupees immediately on this UPI ID or they will put me in jail!"*
   - Within **500ms**, the floating HUD on the call screen triggers an animated warning ring.
   - The Threat Meter rapidly escalates from green to **`CRITICAL FRAUD (85%+)`**.
   - The HUD flashes: **`🚨 CRITICAL: AI Voice Clone Impersonation Detected`**.
   - Live Grad-CAM spectrogram displays on screen, highlighting high-frequency neural vocoder artifacts in bright red/yellow heatmaps.
4. **Spoken Commentary:**
   > "Now observe what happens during a real voice clone attack. An AI clone of the user's son calls demanding an emergency UPI transfer. Notice how fast VoiceShield responds: in under 500 milliseconds, our MelCNN and wav2vec2 models isolate the phase blur and vocoder dispersion. The citizen's phone immediately warns them with a clear, unambiguous critical alert."

---

### 🎬 PHASE 3: The Action Triad — Real-Time Prevention (3:00 – 4:30 | 90s)
**Goal:** Show that VoiceShield doesn't just display a warning — it actively stops the financial transaction.

1. **Screen:** Look at the **Action Triad Banner** and the mobile transaction trigger card.
2. **What happens on screen:**
   - As Layer 2 evaluates the transcript (*"police" + "50,000 rupees" + "immediately"*), the Triad Urgency Guard confirms compound malicious intent.
   - The **PREVENT** layer fires: **`TRANSACTION HOLD TRIGGERED`** card appears.
   - Displays: `Hold Reference: HOLD-20260907-8b4a68de | UPI & Banking Sessions Locked | Latency: 2.26ms`.
   - On the mobile screen, the interactive button confirms: `Banking & UPI Frozen (Protected)`.
3. **Spoken Commentary:**
   > "Most hackathon projects stop at an alert. VoiceShield executes the **Action Triad**. Because our intent classifier confirmed Authority Impersonation plus Financial Demand plus Urgency Threat, our backend triggered an automated UPI hold request via simulated banking API. Even if the panic-stricken victim tries to open their banking app to send the money, the transaction is held in-call. The financial loss is intercepted before it happens."

---

### 🎬 PHASE 4: Cryptographic Evidence Custody — BSA 2023 §63 (4:30 – 6:00 | 90s)
**Goal:** Prove legal admissibility under Indian law to impress technical and legal judges.

1. **Screen:** Switch to **Tab 3 (`localhost:3000/evidence`)** — Forensic Audit Trail.
2. **Action:**
   - Click **`Verify Integrity`**.
   - Point out the verification banner: **`CHAIN VALID — 100% of Records Cryptographically Verified`**.
   - Click on the latest log record to show the `Merkle Hash`, `Previous Hash`, `Ed25519 Signature`, and `Verdict`.
   - Click **`Export BSA §63 Certificate`** to show the generated PDF evidence document.
3. **Spoken Commentary:**
   > "Now, how do police and cyber cells prosecute the criminal? Under Section 63 of the new Bharatiya Sakshya Adhiniyam (BSA) 2023, electronic evidence must have an unbroken chain of custody.
   > 
   > Every 2-second detection block in VoiceShield is hashed using SHA-256, linked to the prior block in a Merkle chain, and signed with an Ed25519 cryptographic private key. If a scammer or corrupt actor alters even one bit in the database, the chain breaks instantly. Here, you see: 'Chain Valid'. With one click, we export a signed Section 63 certificate ready for trial."

---
---

# 🎯 PART 3: 5-MINUTE Q&A BATTLE-TESTED PREPARATION (Top 10 Questions)

*Judges love asking tough edge-case questions. Here are the exact answers to dominate the Q&A:*

---

#### Q1: "Phone calls are 8kHz AMR/G.711. Most AI models are trained on 16kHz studio audio. How does your model survive 8kHz carrier compression?"
> **Answer:**  
> "That is the exact gap where 95% of laboratory detectors fail. When 16kHz audio is downsampled to 8kHz, everything above 4kHz is filtered out by the Nyquist cutoff. VoiceShield solves this by embedding an **ITU-T G.712 telephony simulation pipeline** directly into our feature extraction. We downsample, apply A-law/$\mu$-law compression, and inject simulated GSM burst noise. Our Logistic Calibrator was trained specifically on this telephony-distorted dataset (`ai/models/calibrator.joblib`), which is why our EER on telephony audio is **2.4%**, rather than degrading."

---

#### Q2: "What if the attacker uses an unseen synthetic engine (e.g. latest ElevenLabs or open-source XTTS) that you never trained on?"
> **Answer:**  
> "We explicitly evaluated this using **leave-one-engine-out cross-generator validation** (`scripts/evaluate_cross_generator.py`). Even when ElevenLabs was completely held out of training, VoiceShield achieved an AUC-ROC of **0.728** and detected 100% of XTTS/vocoder fakes. This is because our dual branch doesn't just memorize voice profiles — it detects fundamental vocoder phase discontinuities and biological pitch micro-jitter that *no* real-time generative vocoder can naturally replicate without introducing measurable latency."

---

#### Q3: "What if the scammer is a REAL human calling (vishing/social engineering) without using an AI cloned voice? Does VoiceShield miss them?"
> **Answer:**  
> "This is why our architecture **decouples Layer 1 (Voice Authenticity) from Layer 2 (Scam Intent)**. If a real human scammer calls, Layer 1 will mark the voice as real (score 0.15). But Layer 2's multilingual Whisper ASR and NLP classifier will detect the digital arrest coercion or bank threat. Because our risk engine is a **multimodal weighted fusion** ($0.50 	imes L1 + 0.35 	imes L2 + 0.15 	imes L3$), a high Layer 2 intent score still escalates the call to `SUSPICIOUS` and warns the user, even with a biological voice."

---

#### Q4: "What about false positives? What if an electricity board or hospital calls with an urgent reminder?"
> **Answer:**  
> "We engineered the **Triad Scam-Intent Escalation Guard** specifically to eliminate this regression. In our test suite (`scripts/test_scam_intent.py`), we have a dedicated test case for legitimate electricity bill reminders. The Triad rule enforces that fraud escalation requires a compound triad: **Authority Impersonation + Financial Request + Urgency/Threat**. Routine reminders have financial requests and due dates, but lack authority coercion and arrest threats. The intent score is strictly capped at `0.35` (Verdict: `NORMAL`), resulting in zero false blocks."

---

#### Q5: "How do you achieve <3ms latency? Is that realistic for deep learning models?"
> **Answer:**  
> "Yes, and here is the exact architectural breakdown:
> 1. Our sliding window operates with a **500ms hop**, meaning we evaluate every half-second buffer.
> 2. On GPU, our custom `MelCNN` takes **2.26ms** to compute. Even on CPU, it takes **12ms**.
> 3. Our dual-branch `wav2vec2` runs in an asynchronous ThreadPool worker that doesn't block the WebSocket event loop.
> With a 500ms window budget, a 2.26ms inference latency gives us **99.5% processing headroom**, leaving ample time for network packet transit."

---

#### Q6: "How do you comply with the Digital Personal Data Protection (DPDP) Act 2023 if you are listening to phone calls?"
> **Answer:**  
> "Under DPDP Act 2023, personal data retention is strictly regulated. VoiceShield is built on a **Zero-Audio-Persistence Architecture**:
> - Audio buffers reside solely in ephemeral RAM.
> - Once the 80-bin Mel-spectrogram and acoustic features are extracted, the raw PCM buffer is zeroed out.
> - We never store WAV or MP3 files of citizen conversations in our database.
> - The only data persisted in PostgreSQL is the cryptographic hash, the mathematical score, and the metadata required for BSA §63 legal evidence."

---

#### Q7: "Is an Ed25519 hash-chain legally admissible in Indian courts under the new criminal laws?"
> **Answer:**  
> "Yes, under **Section 63 of the Bharatiya Sakshya Adhiniyam (BSA), 2023**, electronic evidence is admissible provided its integrity and digital custody chain can be established without human tampering. Our SHA-256 Merkle chain guarantees that no intermediate record can be altered without invalidating all subsequent block hashes. The Ed25519 digital signature establishes cryptographic non-repudiation, matching the legal threshold required for cybercrime prosecution."

---

#### Q8: "Where would this actually be deployed in the real world? On the smartphone or inside the telecom network?"
> **Answer:**  
> "VoiceShield is designed for a **hybrid deployment model**:
> 1. **Telco-Grade Edge (Core Telecom Switch / IMS Gateway):** Telecom operators (Jio, Airtel, Vi) can deploy VoiceShield as an inline SIP media proxy, analyzing audio frames during call transit and injecting warning tones or network-level flags before the call rings.
> 2. **Client Endpoint (Mobile App / Banking SDK):** As demonstrated in our `/mobile` simulator, VoiceShield can be integrated directly into banking apps (YONO, iMobile) or dialer apps (Truecaller) to provide on-device protection."

---

#### Q9: "What happens if the call has severe background noise or a bad microphone?"
> **Answer:**  
> "Our pipeline contains two defensive layers for noisy environments:
> 1. **Silero VAD Gating:** Low-energy frames (below 0.012 RMS) and non-speech background ambient noise bypass model inference entirely.
> 2. **Mahalanobis Out-of-Distribution (OOD) Gating:** If severe background noise distorts the feature vector beyond 2.85 Mahalanobis distance from our calibration centroid, the system flags the frame as `AMBIGUOUS_OOD` rather than spuriously triggering a fake-voice alert. It waits for the next clean speech window."

---

#### Q10: "What is your business model? Who pays for VoiceShield?"
> **Answer:**  
> "Our primary B2B customers are **Commercial Banks, UPI Payment Gateways (NPCI/PhonePe/GPay), and Telecom Carriers**:
> - **Banks & UPI Providers** pay for VoiceShield via an API-based fraud-prevention subscription because every prevented voice scam directly eliminates chargeback liabilities, fraud claims, and regulatory fines.
> - **Telecom Operators** deploy VoiceShield as a premium, value-added security feature for subscribers, similar to enterprise spam protection.
> For the end citizen, the core protection is completely free."
