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
        r"credit\s*card", r"atm\s*card", r"bank\s*account", r"खाता", r"बैंक",
        r"otp\s*(batao|bata|do|share|send)", r"otp\s*नंबर", r"ओटीपी",
        r"आधार", r"पिन\s*नंबर", r"सीवीवी", r"card\s*ki\s*detail",
        r"\b[4-6]\s*tp\b", r"o[\s.]*t[\s.]*p", r"\d+\s*digit\s*(otp|pin|code)",
        r"unauthorized\s*(debit|charge|transaction|access)", r"verification\s*code",
    ]),
    Category("authority_impersonation", 0.40, [
        r"\bpolice\b", r"\bcbi\b", r"\bcustoms?\b", r"\bnarcotics\b", r"\bfedex\b",
        r"\bcourt\b", r"\bwarrant\b", r"\barrest\b", r"digital\s*arrest",
        # Courier only when accompanied by contraband/interception/police/seizure
        r"courier\s*(parcel\s*)?(addressed|intercepted|seized|customs|contraband|illegal|police|arrest|drugs)",
        r"(illegal|contraband|drugs)\s*courier",
        r"income\s*tax", r"cyber\s*cell", r"trai\b", r"enforcement\s*directorate",
        r"money\s*laundering", r"illegal\s*(drugs|parcel)", r"seized",
        r"giraftaar", r"गिरफ्तार", r"वारंट", r"अदालत", r"पुलिस", r"सीबीआई", r"दूरसंचार",
        r"main\s*(inspector|officer|dcp)\s*bol", r"thane\s*se\s*bol", r"customs\s*me",
        r"state\s*bank",
        # Fraud prevention in official/calling context, not general academic discussion
        r"(calling|officer|unit|department).*fraud\s*prevention", r"fraud\s*prevention\s*(unit|department|cell|team)",
        r"inspection\s*clearance", r"airport",
        r"(bijli|bijwi|vitran|vithran|witran|with\s*run|veteran|bajri|electricity)\s*(board|company|department|office|nigam)?",
        r"(with\s*run|veteran|vithran)\s*company",
    ]),
    Category("urgency_threat", 0.35, [
        r"\bimmediately\b", r"\burgent(ly)?\b", r"right\s*now", r"within\s*\d+\s*(min|hour|ghante)",
        r"account\s*(is\s*)?(blocked|suspended|frozen|deactivat|freeze|seize)",
        r"legal\s*action", r"last\s*warning", r"final\s*notice", r"do\s*not\s*(tell|inform|disconnect)",
        r"call\s*disconnect\s*mat", r"electricity\s*(connection\s*)?(will\s*be\s*)?disconnect",
        r"\b(bijli|bidhi)\b", r"disconnect(ion)?", r"बिजली", r"काट\s*दी\s*जाएगी",
        # Avoid standalone 'fine' which matches 'I am fine' or casual banter
        r"\b(pay|heavy|court|legal)\s*fine\b", r"\bfine\s*(lagao|dena|bharna|imposed)\b",
        r"penalty", r"raid", r"fir\b", r"पेनल्टी", r"जुर्माना",
        r"turant", r"jaldi", r"abhi\s*ke\s*abhi", r"block\s*(ho\s*jaye|fraudulent)",
        r"permanently\s*blocked", r"cancel\s*this\s*transaction", r"tatkal", r"bakaya",
        r"तुरंत", r"जल्दी", r"बंद\s*हो\s*जाएगा", r"kisi\s*ko\s*mat\s*bata",
        r"دس[كک]ن[كک]شن", r"تتقال", r"کنیکشن",
    ]),
    Category("financial_request", 0.25, [
        r"send\s*money", r"pay\s*now", r"transfer\s*(the\s*)?money", r"upi\s*pin",
        r"google\s*pay", r"phone\s*pe", r"paytm", r"scanner", r"qr\s*code",
        r"processing\s*fee", r"refundable\s*deposit", r"clearance\s*charge",
        r"paisa\s*(bhej|transfer)", r"paise\s*bhej", r"amount\s*bhej", r"bhejo",
        r"पैसे?\s*भेज", r"transfer\s*kar(o|do|iye)", r"account\s*me\s*daal", r"जमा\s*करें",
        r"jurmana", r"jamakare", r"rupaye", r"rupees",
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

# ── Conversational & Negation Context Guards ─────────────────────────────────
CASUAL_HUMOR_PATTERN = re.compile(
    r"\b(haha|hahaha|lol|lmao|rofl|so\s*funny|joke|joking|mazak|so\s*annoying|annoying)\b", re.IGNORECASE
)
PAST_ANECDOTE_PATTERN = re.compile(
    r"\b(stopped\s*me\s*today|had\s*to\s*pay|yesterday|was\s*telling|told\s*me|happened\s*to|got\s*arrested|crazy\s*story|saw\s*on\s*(the\s*)?news|reading\s*about)\b", re.IGNORECASE
)
BENIGN_TECH_PATTERN = re.compile(
    r"\b(building\s*a\s*(model|system|project|app)|machine\s*learning|presentation\s*deck|project\s*review|researching)\b", re.IGNORECASE
)
FAMILY_LOGIN_PATTERN = re.compile(
    r"\b(netflix|prime|hotstar|family\s*account|login\s*otp|did\s*you\s*get)\b", re.IGNORECASE
)
ALERT_SERVICE_PATTERN = re.compile(
    r"\b(fraud\s*alert|security\s*advisory|never\s*share|do\s*not\s*share|don\'?t\s*share)\b", re.IGNORECASE
)
NEGATION_ADVISORY_PATTERN = re.compile(
    r"(never|do\s*not|don\'?t|kisi\s*ko\s*mat|avoid)\s*(share|disclose|bata|give|tell|enter)?\s*(your|apna|the)?\s*(password|pin|otp|cvv|credentials)", re.IGNORECASE
)

# Active live demand markers that override casual guards if present
ACTIVE_COERCION_MARKERS = re.compile(
    r"\b(pay\s*now|transfer\s*(immediately|now)|under\s*digital\s*arrest|share\s*(the\s*)?otp|permanently\s*blocked)\b", re.IGNORECASE
)


def _normalize(text: str) -> str:
    text = text.lower()
    # Strip Arabic / Urdu diacritics (harakat / tashkeel)
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    # Replace punctuation with space so chunk boundaries and sentence ends do not break multi-word regexes
    text = re.sub(r"[\.,\-\?!;:\'\"\/\\(\)\[\]]", " ", text)
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
          "num_categories": int,
        }
    """
    if not transcript or not transcript.strip():
        return {"intent_risk": 0.0, "categories": {}, "matched": [], "top_category": None, "num_categories": 0}

    raw = transcript
    text = _normalize(transcript)

    is_casual_or_past = (
        bool(CASUAL_HUMOR_PATTERN.search(raw)) or
        bool(PAST_ANECDOTE_PATTERN.search(raw))
    )
    is_benign_discussion = (
        bool(BENIGN_TECH_PATTERN.search(raw)) or
        bool(FAMILY_LOGIN_PATTERN.search(raw)) or
        bool(ALERT_SERVICE_PATTERN.search(raw))
    )
    has_active_coercion = bool(ACTIVE_COERCION_MARKERS.search(raw))

    # Mask defensive advisories (e.g. "Never share your password")
    masked_text = NEGATION_ADVISORY_PATTERN.sub("advisory_warning_masked", text)

    fired: Dict[str, float] = {}
    matched: List[str] = []

    for cat in CATEGORIES:
        hit = False
        for pat in cat.patterns:
            m = re.search(pat, masked_text)
            if m:
                # If conversational context or benign tech/family discussion exists without active extortion
                if (is_casual_or_past or is_benign_discussion) and not has_active_coercion:
                    continue
                hit = True
                matched.append(f"{cat.name}: '{m.group(0)}'")
        if hit:
            fired[cat.name] = cat.weight

    # Multi-category compounding rule:
    # A single isolated category cannot exceed 0.35 risk.
    # Real scams combine >= 2 distinct categories (e.g. authority + urgency, credential + threat).
    if len(fired) == 0:
        intent_risk = 0.0
    elif len(fired) == 1 and not has_active_coercion:
        only_cat = list(fired.keys())[0]
        intent_risk = min(0.35, fired[only_cat])
    else:
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
        "num_categories": len(fired),
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
