"""
VoiceShield — Intelligence Layers (2 & 3)
=========================================
Beyond Layer 1 (voice authenticity), these modules answer the judges' ask:
detect voice fraud *in general*, including scams spoken by a REAL human.

  Layer 2  intent_classifier  → is the CONVERSATION a scam? (from transcript)
  Layer 2  asr                → speech-to-text (Whisper) feeding the classifier
  Layer 3  call_signals       → is the CALL itself suspicious? (metadata/number)

All three sub-scores are fused with Layer 1 into one risk score (see backend.app.risk).
"""
