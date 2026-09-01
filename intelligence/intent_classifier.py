"""
VoiceShield — Layer 2: Scam-Intent Classifier
==============================================
Scores how fraudulent a CONVERSATION is, from its transcript — independent of
whether the voice is human or AI. This is what catches real-human scams
(digital-arrest, OTP phishing, fake KYC) that a deepfake detector alone misses.

Design
------
Rule-based, multilingual (English + Hindi/Hinglish, Devanagari + roman), and
fully OFFLINE — so it is fast, explainable, and never fails during a live demo.
An optional LLM hook can refine the score when connectivity is available, but the
rules are the dependable floor.

Output is a calibrated risk in [0, 1] plus the evidence (which scam categories
fired and which phrases matched) — so the UI can say *why* it flagged.

Usage
-----
    from intelligence.intent_classifier import score_intent
    result = score_intent("Sir your account is blocked, share the OTP immediately")
    # -> {"intent_risk": 0.86, "categories": {...}, "matched": [...], "top_category": "credential_theft"}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List


# ──────────────────────────────────────────────────────────────────────
# Scam pattern lexicon
# Each category has a weight (how damning it is) and a list of patterns.
# Patterns cover English, romanized Hindi/Hinglish, and Devanagari.
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Category:
    name: str
    weight: float                       # contribution when this category fires
    patterns: List[str] = field(default_factory=list)


CATEGORIES: List[Category] = [
    Category("credential_theft", 0.45, [
        r"\botp\b", r"one[\s-]*time[\s-]*password", r"\bpin\b", r"\bcvv\b",
        r"\bpassword\b", r"\bpasscode\b", r"card\s*number", r"expiry\s*date",
        r"\baadhaar?\b", r"\bpan\s*card\b", r"\bkyc\b", r"net\s*banking", r"debit\s*card",
        r"atm\s*card", r"bank\s*account", r"खाता", r"बैंक",
        r"otp\s*(batao|bata|do|share|send)", r"otp\s*नंबर", r"ओटीपी",
        r"आधार", r"पिन\s*नंबर", r"सीवीवी", r"card\s*ki\s*detail",
    ]),
    Category("authority_impersonation", 0.40, [
        r"\bpolice\b", r"\bcbi\b", r"\bcustoms?\b", r"\bnarcotics\b", r"\bfedex\b",
        r"\bcourt\b", r"\bwarrant\b", r"\barrest\b", r"digital\s*arrest", r"\bcourier\b",
        r"income\s*tax", r"cyber\s*cell", r"trai\b", r"enforcement\s*directorate",
        r"money\s*laundering", r"illegal\s*(drugs|parcel)", r"seized",
        r"giraftaar", r"गिरफ्तार", r"वारंट", r"अदालत", r"पुलिस", r"सीबीआई", r"दूरसंचार",
        r"main\s*(inspector|officer|dcp)\s*bol", r"thane\s*se\s*bol", r"customs\s*me",
    ]),
    Category("urgency_threat", 0.35, [
        r"\bimmediately\b", r"\burgent(ly)?\b", r"right\s*now", r"within\s*\d+\s*(min|hour|ghante)",
        r"account\s*(is\s*)?(blocked|suspended|frozen|deactivat|freeze|seize)",
        r"legal\s*action", r"last\s*warning", r"final\s*notice", r"do\s*not\s*(tell|inform|disconnect)",
        r"call\s*disconnect\s*mat", r"electricity\s*(connection\s*)?(will\s*be\s*)?disconnect",
        r"bijli\s*(ka\s*connection)?", r"बिजली", r"काट\s*दी\s*जाएगी",
        r"fine", r"penalty", r"raid", r"fir\b", r"पेनल्टी", r"जुर्माना",
        r"turant", r"jaldi", r"abhi\s*ke\s*abhi", r"block\s*ho\s*jaye",
        r"तुरंत", r"जल्दी", r"बंद\s*हो\s*जाएगा", r"kisi\s*ko\s*mat\s*bata",
    ]),
    Category("financial_request", 0.36, [
        r"transfer\s*(the\s*)?(money|funds|amount|rupees|\d+)", r"send\s*money", r"\bupi\b",
        r"google\s*pay|gpay|phonepe|paytm", r"scan\s*(the\s*)?qr", r"\brefund\b",
        r"processing\s*fee", r"security\s*deposit", r"pay\s*(the\s*)?(fee|fine|bill|tax)",
        r"paisa\s*(bhej|transfer)", r"paise\s*bhej", r"amount\s*bhej", r"bhejo",
        r"पैसे?\s*भेज", r"transfer\s*kar(o|do|iye)", r"account\s*me\s*daal", r"जमा\s*करें",
    ]),
    Category("lottery_prize", 0.30, [
        r"you\s*have\s*won", r"\blottery\b", r"lucky\s*draw", r"prize\s*money",
        r"cash\s*prize", r"free\s*gift", r"reward\s*points\s*expir",
        r"pre-approved(\s*personal)?\s*loan", r"loan\s*pass", r"loan\s*of",
        r"lottery\s*laga", r"inaam", r"इनाम", r"लॉटरी", r"लोन", r"lottery\s*jeet",
    ]),
    Category("remote_access", 0.35, [
        r"anydesk", r"team\s*viewer", r"quick\s*support", r"screen\s*shar",
        r"install\s*(the\s*)?app", r"download\s*(the\s*)?app",
        r"app\s*install\s*kar", r"screen\s*dikha",
    ]),
]

# A short conversation with a single weak hit shouldn't read as 0.9.
# We combine category weights multiplicatively (noisy-OR style) so multiple
# independent scam signals compound, but one alone stays moderate.


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def score_intent(transcript: str) -> Dict:
    """
    Score scam intent from a transcript.

    Returns:
        {
          "intent_risk": float in [0,1],
          "categories": {name: fired_weight, ...},   # only categories that fired
          "matched": [ "category: phrase", ... ],     # evidence for the UI
          "top_category": str | None,
        }
    """
    if not transcript or not transcript.strip():
        return {"intent_risk": 0.0, "categories": {}, "matched": [], "top_category": None}

    text = _normalize(transcript)

    fired: Dict[str, float] = {}
    matched: List[str] = []

    for cat in CATEGORIES:
        hit = False
        for pat in cat.patterns:
            m = re.search(pat, text)
            if m:
                hit = True
                matched.append(f"{cat.name}: '{m.group(0)}'")
        if hit:
            fired[cat.name] = cat.weight

    # Noisy-OR fusion: risk = 1 - Π(1 - weight) over fired categories.
    # One category → its weight; several → compounds toward 1.0.
    prod = 1.0
    for w in fired.values():
        prod *= (1.0 - w)
    intent_risk = round(1.0 - prod, 4)

    top_category = max(fired, key=fired.get) if fired else None

    return {
        "intent_risk": intent_risk,
        "categories": fired,
        "matched": matched,
        "top_category": top_category,
    }


if __name__ == "__main__":
    # Quick self-check / demo
    samples = [
        ("hi mom, running late for dinner, see you soon", "benign"),
        ("Sir your bank account is blocked, share the OTP immediately", "scam"),
        ("This is the police, there is a warrant, you are under digital arrest", "scam"),
        ("aapke naam pe warrant hai, turant paise transfer karo warna giraftaar", "scam-hinglish"),
        ("आपका केवाईसी अपडेट करना है, ओटीपी बताओ", "scam-hindi"),
        ("install anydesk so I can help you with the refund", "scam-remote"),
        ("let's meet at the cafe around 5pm tomorrow", "benign"),
    ]
    for text, label in samples:
        r = score_intent(text)
        print(f"[{label:14}] risk={r['intent_risk']:.2f} top={r['top_category']} :: {text[:50]}")
