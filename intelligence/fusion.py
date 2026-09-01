"""
VoiceShield — 3-Layer Risk Fusion
=================================
Combines the three fraud lenses into ONE risk score:

  Layer 1  voice_authenticity  P(voice is fake / cloned / replayed)
  Layer 2  intent_risk         P(conversation is a scam)
  Layer 3  call_signal_risk    P(call metadata is suspicious)

Fusion policy
-------------
We blend a **weighted average** (rewards corroboration across layers) with a
**single-layer escalation** (a strongly confident single lens should still raise
the alarm — a clear deepfake OR a blatant scam script is enough).

    weighted   = Σ wᵢ·xᵢ / Σ wᵢ
    escalated  = ESCALATION · max(xᵢ)
    fused      = max(weighted, escalated)

This matches the product promise: flag if the voice is fake OR the conversation
is a scam OR the call is suspicious — while giving extra confidence when several
agree.
"""
from __future__ import annotations

from typing import Dict, Optional

# Reliability weights — Layer 1 is the most trusted, Layer 3 the least.
DEFAULT_WEIGHTS: Dict[str, float] = {"voice": 0.50, "intent": 0.35, "signal": 0.15}

# How much a single very-confident layer alone can drive the score.
ESCALATION = 0.85


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def fuse_layers(
    voice_authenticity: float,
    intent_risk: float = 0.0,
    call_signal_risk: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
    escalation: float = ESCALATION,
) -> float:
    """Fuse the three layer scores into a single risk in [0, 1]."""
    v = _clamp(voice_authenticity)
    i = _clamp(intent_risk)
    s = _clamp(call_signal_risk)

    w = weights or DEFAULT_WEIGHTS
    wv, wi, ws = w.get("voice", 0.5), w.get("intent", 0.35), w.get("signal", 0.15)
    total = wv + wi + ws or 1.0

    weighted = (wv * v + wi * i + ws * s) / total
    escalated = escalation * max(v, i, s)
    return round(max(weighted, escalated), 4)


def verdict_from_risk(risk: float, fraud_at: float = 0.70, suspicious_at: float = 0.40) -> str:
    """Map a fused risk to a label used by the UI."""
    if risk >= fraud_at:
        return "FRAUD"
    if risk >= suspicious_at:
        return "SUSPICIOUS"
    return "REAL"


if __name__ == "__main__":
    cases = [
        ("benign call",            0.10, 0.00, 0.10),
        ("clear deepfake only",    0.95, 0.00, 0.00),
        ("human scam script only", 0.10, 0.86, 0.20),
        ("suspicious number only", 0.15, 0.00, 0.90),
        ("all three agree",        0.80, 0.75, 0.70),
        ("borderline",             0.45, 0.40, 0.30),
    ]
    for name, v, i, s in cases:
        r = fuse_layers(v, i, s)
        print(f"{name:24} v={v:.2f} i={i:.2f} s={s:.2f} -> fused={r:.2f} ({verdict_from_risk(r)})")
