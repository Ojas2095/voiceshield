"""
VoiceShield — Layer 3: Call Signals
===================================
Scores how suspicious the CALL itself is, from cheap metadata — independent of
the audio or the words. Complements Layer 1 (voice) and Layer 2 (intent).

Signals (all rule-based, offline, instant):
  • number reputation   — local blocklist / known-scam prefixes
  • caller-ID anomalies  — spoof-looking numbers (too short, odd intl prefix,
                           bank name claimed but random mobile)
  • timing               — unsolicited call at odd hours
  • unknown caller       — not in the user's contacts

For a hackathon demo a small local table is enough; in production this is a
lookup against a telecom / TRAI / crowd-sourced reputation service.

Usage
-----
    from intelligence.call_signals import score_call_signals
    r = score_call_signals({
        "number": "+91XXXXXXXXXX",
        "hour_local": 2,           # 0-23
        "in_contacts": False,
        "claimed_entity": "SBI Bank",
    })
    # -> {"call_signal_risk": 0.7, "reasons": [...]}
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional


# Demo reputation table — replace with a real feed in production.
BLOCKLISTED_NUMBERS = {
    "+911234567890",
    "1234567890",
}
# Prefixes frequently seen in Indian vishing (illustrative, not exhaustive).
SUSPICIOUS_PREFIXES = ("+9214", "+9213", "+92", "+880", "+234")  # intl often used to spoof
KNOWN_GOOD_SHORTCODES = {"121", "1800", "1930"}  # e.g., cyber-crime helpline 1930


def _digits(number: str) -> str:
    return re.sub(r"\D", "", number or "")


def score_call_signals(meta: Optional[Dict]) -> Dict:
    """
    Args:
        meta: dict with any of:
            number: str            caller number (E.164 preferred)
            hour_local: int        0-23 local hour of the call
            in_contacts: bool      is the number in the user's contacts
            claimed_entity: str    who the caller claims to be (e.g. "SBI Bank")
    Returns:
        {"call_signal_risk": float in [0,1], "reasons": [str, ...]}
    """
    meta = meta or {}
    number = str(meta.get("number", "") or "")
    digits = _digits(number)
    reasons: List[str] = []
    risk = 0.0

    # Known-good shortcodes are trusted outright.
    if digits in KNOWN_GOOD_SHORTCODES or number in KNOWN_GOOD_SHORTCODES:
        return {"call_signal_risk": 0.0, "reasons": ["known official shortcode"]}

    # 1. Hard blocklist
    if number in BLOCKLISTED_NUMBERS or digits in BLOCKLISTED_NUMBERS:
        reasons.append("number on scam blocklist")
        risk = max(risk, 0.9)

    # 2. Suspicious international prefix
    if any(number.startswith(p) for p in SUSPICIOUS_PREFIXES):
        reasons.append("suspicious international prefix")
        risk = max(risk, 0.6)

    # 3. Malformed / spoof-looking length (real Indian mobiles are 10 digits,
    #    or 12 with country code)
    if digits and len(digits) not in (10, 11, 12) and digits not in KNOWN_GOOD_SHORTCODES:
        reasons.append(f"unusual number length ({len(digits)} digits)")
        risk = max(risk, 0.45)

    # 4. Claims to be a bank/authority but calls from a random personal mobile
    claimed = str(meta.get("claimed_entity", "") or "").lower()
    if claimed and any(k in claimed for k in ("bank", "police", "cbi", "income tax", "customs", "trai")):
        # Institutions use shortcodes / verified sender IDs, not 10-digit mobiles
        if len(digits) >= 10 and digits[0] in "6789":  # Indian personal mobile series
            reasons.append(f"claims to be '{meta.get('claimed_entity')}' from a personal mobile")
            risk = max(risk, 0.55)

    # 5. Not in contacts (neutral/advisory signal — normal for everyday calls)
    if meta.get("in_contacts") is False:
        reasons.append("caller not in contacts")
        risk = max(risk, 0.05)

    # 6. Odd-hours unsolicited call
    hour = meta.get("hour_local")
    if isinstance(hour, int) and (hour < 6 or hour >= 23):
        reasons.append(f"call at odd hour ({hour}:00)")
        risk = max(risk, min(risk + 0.15, 0.5) if risk else 0.25)

    return {"call_signal_risk": round(min(risk, 1.0), 4), "reasons": reasons}


if __name__ == "__main__":
    cases = [
        {"number": "1930"},                                                   # helpline
        {"number": "+919876543210", "in_contacts": True},                     # known contact
        {"number": "+919876543210", "in_contacts": False, "hour_local": 2},   # unknown, odd hour
        {"number": "+911234567890"},                                          # blocklisted
        {"number": "+922112345", "hour_local": 14},                           # intl + short
        {"number": "+919812345678", "claimed_entity": "SBI Bank"},            # bank from mobile
    ]
    for c in cases:
        r = score_call_signals(c)
        print(f"risk={r['call_signal_risk']:.2f}  {c}  -> {r['reasons']}")
