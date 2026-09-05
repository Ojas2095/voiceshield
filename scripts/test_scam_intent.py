"""
VoiceShield - Layer 2 Systematic Intent Acceptance Test Suite
============================================================
Comprehensive test suite running:
1. Standard & Hard-Negative Sanity Cases (15 cases)
2. Systematic Category-Pair Matrix across English, Hindi, and Hinglish (72 cases)
3. Strict Pair-Completeness & Balance Assertions

Run:
    python scripts/test_scam_intent.py
Exit code: 0 on 100% pass, 1 on any failure.
"""
import sys, os
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from intelligence.intent_classifier import score_intent

# ─────────────────────────────────────────────────────────────────────────────
# 1. Standard & Hard Negative Sanity Scenarios (15 cases)
# ─────────────────────────────────────────────────────────────────────────────
SANITY_CASES = [
    # Standard Benign Dialogues
    ('Normal: Coffee meeting', 'Hey bro, how are you? Are we meeting for coffee today at the cafeteria?'),
    ('Normal: Project review', 'Let us review the presentation slides for tomorrow morning meeting with the team.'),
    ('Normal: Hinglish college', 'Haan bhai kaisa hai, kal chalte hain college project submit karne.'),
    ('Normal: Weather inquiry', 'What is the weather forecast for tomorrow? Looks like it might rain in the evening.'),

    # 6 Hard Negatives (Scam-adjacent words in benign/casual contexts)
    ('Hard Neg: Traffic fine joke', 'Traffic police stopped me today haha, had to pay a 500 rupees fine, lol so annoying.'),
    ('Hard Neg: Legitimate courier', 'Hello, this is BlueDart courier service confirming your package delivery for today afternoon.'),
    ('Hard Neg: Family Netflix OTP', 'Beta, I am logging into our family Netflix account, did you get the login OTP on your phone?'),
    ('Hard Neg: Real bank advisory', 'Good morning, this is ICICI Bank fraud alert service. We noticed unusual activity. Please check your net banking or visit your branch. Never share your password with anyone.'),
    ('Hard Neg: Tech ML discussion', 'We are building a machine learning model for cyber crime and credit card fraud prevention.'),
    ('Hard Neg: Past customs anecdote', 'My friend was telling me yesterday about how someone got arrested by customs at the airport for smuggled goods, crazy story!'),

    # Confirmed Scam Scenarios
    ('Scam: SBI OTP Phishing', 'Dear customer your SBI debit card is blocked. Please share the 6-digit OTP sent to your phone immediately to verify.'),
    ('Scam: Digital Arrest', 'This is Inspector Sharma from Cyber Crime Police Station. A parcel with illegal drugs was seized in your name. You are under digital arrest, transfer money immediately to avoid FIR.'),
    ('Scam: Electricity Disconnect', 'Your electricity connection will be disconnected tonight at 9:30 PM due to unpaid bill. Call this number and pay the bill immediately.'),
    ('Scam: Hindi OTP Scam', 'Sir main State Bank se bol raha hoon, aapka khata band ho jayega, turant OTP bataiye.'),
    ('Scam: Customs CBI', 'Customs office Mumbai se bol raha hoon, aapke courier me fake passport aur narcotics mila hai, turant arrest warrant jari hoga.'),
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. Systematic Category-Pair Matrix (72 cases across EN, HI, Hinglish)
# ─────────────────────────────────────────────────────────────────────────────
TEST_MATRIX = [
    # ── Pair 1: (authority_impersonation, financial_request) ──────────────────────
    {
        "id": "P01_AUTH_FIN_EN_BENIGN",
        "pair": ("authority_impersonation", "financial_request"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Good afternoon, this is an automated notification from Tata Power regarding your monthly electricity bill of 1200 rupees due on the 25th of this month.",
    },
    {
        "id": "P01_AUTH_FIN_EN_SCAM",
        "pair": ("authority_impersonation", "financial_request"),
        "lang": "en",
        "expected": "SCAM",
        "text": "This is the electricity board vigilance squad, you have a heavy pending penalty of 1200 rupees, disconnect tonight unless paid immediately!",
    },
    {
        "id": "P01_AUTH_FIN_HI_BENIGN",
        "pair": ("authority_impersonation", "financial_request"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "नमस्ते, यह विद्युत वितरण कंपनी से सूचना है कि आपका मासिक बिजली बिल आठ सौ रुपये अगले सप्ताह तक देय है।",
    },
    {
        "id": "P01_AUTH_FIN_HI_SCAM",
        "pair": ("authority_impersonation", "financial_request"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "हम बिजली विभाग सतर्कता दल से हैं, आपका पंद्रह सौ रुपये जुर्माना बकाया है, आज रात कनेक्शन कटेगा तुरंत पैसे भेजो।",
    },
    {
        "id": "P01_AUTH_FIN_HING_BENIGN",
        "pair": ("authority_impersonation", "financial_request"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Hello sir, Tata Power customer care se call hai, aapka electricity bill 1200 rupees generate ho gaya hai, due date agle hafte hai.",
    },
    {
        "id": "P01_AUTH_FIN_HING_SCAM",
        "pair": ("authority_impersonation", "financial_request"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Bijli vibhag vigilance officer bol raha hoon, 1500 rupees penalty turant transfer karo warna connection cut ho jayega.",
    },

    # ── Pair 2: (authority_impersonation, urgency_threat) ────────────────────────
    {
        "id": "P02_AUTH_URG_EN_BENIGN",
        "pair": ("authority_impersonation", "urgency_threat"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "The traffic police officer checked my vehicle papers today haha, so annoying that I had to wait in traffic for an hour!",
    },
    {
        "id": "P02_AUTH_URG_EN_SCAM",
        "pair": ("authority_impersonation", "urgency_threat"),
        "lang": "en",
        "expected": "SCAM",
        "text": "This is Senior Inspector Sharma from Delhi Cyber Crime Police Station, a non-bailable arrest warrant has been issued against you, respond immediately!",
    },
    {
        "id": "P02_AUTH_URG_HI_BENIGN",
        "pair": ("authority_impersonation", "urgency_threat"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "कल पुलिस चेकिंग में बहुत देर खड़ी रहनी पड़ी, बड़ा सिरदर्द हो गया था यार।",
    },
    {
        "id": "P02_AUTH_URG_HI_SCAM",
        "pair": ("authority_impersonation", "urgency_threat"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "यह मुख्य पुलिस अधीक्षक कार्यालय है, आपके खिलाफ तुरंत गिरफ्तारी वारंट जारी हुआ है, अभी के अभी फोन मत काटना।",
    },
    {
        "id": "P02_AUTH_URG_HING_BENIGN",
        "pair": ("authority_impersonation", "urgency_threat"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Police ne aaj subah road block ki thi checking ke liye lol, traffic me phas gaya tha.",
    },
    {
        "id": "P02_AUTH_URG_HING_SCAM",
        "pair": ("authority_impersonation", "urgency_threat"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Customs cyber branch se bol raha hoon, turant digital arrest warrant issue hua hai, call disconnect mat karna.",
    },

    # ── Pair 3: (authority_impersonation, credential_theft) ──────────────────────
    {
        "id": "P03_AUTH_CRED_EN_BENIGN",
        "pair": ("authority_impersonation", "credential_theft"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "We are building an AI machine learning defense system against state bank credential theft and credit card fraud.",
    },
    {
        "id": "P03_AUTH_CRED_EN_SCAM",
        "pair": ("authority_impersonation", "credential_theft"),
        "lang": "en",
        "expected": "SCAM",
        "text": "This is Officer Rakesh Verma calling from State Bank of India fraud prevention unit, share your 6-digit OTP right now to unblock your credit card.",
    },
    {
        "id": "P03_AUTH_CRED_HI_BENIGN",
        "pair": ("authority_impersonation", "credential_theft"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "हम कॉलेज में साइबर सेल और बैंक खाता धोखाधड़ी रोकने के लिए प्रोजेक्ट बना रहे हैं।",
    },
    {
        "id": "P03_AUTH_CRED_HI_SCAM",
        "pair": ("authority_impersonation", "credential_theft"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "मैं स्टेट बैंक सतर्कता शाखा से बोल रहा हूँ, आपका खाता बंद हो गया है, अपना छह अंकों का ओटीपी तुरंत बताओ।",
    },
    {
        "id": "P03_AUTH_CRED_HING_BENIGN",
        "pair": ("authority_impersonation", "credential_theft"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Hum bank security model discuss kar rahe hain jo fake police aur OTP fraud prevent karta hai.",
    },
    {
        "id": "P03_AUTH_CRED_HING_SCAM",
        "pair": ("authority_impersonation", "credential_theft"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "State Bank manager bol raha hoon, aapka debit card block ho chuka hai, unblock karne ke liye OTP batao.",
    },

    # ── Pair 4: (authority_impersonation, remote_access) ─────────────────────────
    {
        "id": "P04_AUTH_REM_EN_BENIGN",
        "pair": ("authority_impersonation", "remote_access"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Our office IT support team is deploying TeamViewer for the cyber security compliance audit tomorrow.",
    },
    {
        "id": "P04_AUTH_REM_EN_SCAM",
        "pair": ("authority_impersonation", "remote_access"),
        "lang": "en",
        "expected": "SCAM",
        "text": "This is Telecom Regulatory Authority officer, your SIM is flagged for illegal activities, install AnyDesk app immediately so we can inspect your screen.",
    },
    {
        "id": "P04_AUTH_REM_HI_BENIGN",
        "pair": ("authority_impersonation", "remote_access"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "कल हमारे दफ्तर में आईटी टीम कंप्यूटर ठीक करने के लिए स्क्रीन शेयरिंग सॉफ्टवेयर देख रही थी।",
    },
    {
        "id": "P04_AUTH_REM_HI_SCAM",
        "pair": ("authority_impersonation", "remote_access"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "सीबीआई साइबर सेल से बोल रहा हूँ, अपने फोन में तुरंत एनीडेस्क ऐप डाउनलोड करो और स्क्रीन दिखाओ।",
    },
    {
        "id": "P04_AUTH_REM_HING_BENIGN",
        "pair": ("authority_impersonation", "remote_access"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Company IT desk kal AnyDesk use karke audit check karne wali hai.",
    },
    {
        "id": "P04_AUTH_REM_HING_SCAM",
        "pair": ("authority_impersonation", "remote_access"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Police cyber department se bol raha hoon, AnyDesk install karke screen connect karo verification ke liye.",
    },

    # ── Pair 5: (financial_request, urgency_threat) ──────────────────────────────
    {
        "id": "P05_FIN_URG_EN_BENIGN",
        "pair": ("financial_request", "urgency_threat"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Hey, remember that 500 rupees lunch from yesterday? No rush at all, just send the money whenever you get free time haha.",
    },
    {
        "id": "P05_FIN_URG_EN_SCAM",
        "pair": ("financial_request", "urgency_threat"),
        "lang": "en",
        "expected": "SCAM",
        "text": "Pay 5000 rupees immediately to this UPI ID right now or your account will be permanently blocked and legal action taken!",
    },
    {
        "id": "P05_FIN_URG_HI_BENIGN",
        "pair": ("financial_request", "urgency_threat"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "अरे भाई कल के खाने के तीन सौ रुपये जब फुर्सत मिले तब गूगल पे कर देना, कोई जल्दी नहीं है।",
    },
    {
        "id": "P05_FIN_URG_HI_SCAM",
        "pair": ("financial_request", "urgency_threat"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "तुरंत दस हजार रुपये इस यूपीआई पर ट्रांसफर करो वरना तुम्हारे खिलाफ कानूनी कार्रवाई की जाएगी और जुर्माना लगेगा।",
    },
    {
        "id": "P05_FIN_URG_HING_BENIGN",
        "pair": ("financial_request", "urgency_threat"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Kal ke movie ticket ke 400 rupees free ho ke GPay kar dena bro, chill scene hai.",
    },
    {
        "id": "P05_FIN_URG_HING_SCAM",
        "pair": ("financial_request", "urgency_threat"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Abhi ke abhi 2000 rupees pay karo penalty warna account block ho jayega aur police raid padegi.",
    },

    # ── Pair 6: (financial_request, credential_theft) ────────────────────────────
    {
        "id": "P06_FIN_CRED_EN_BENIGN",
        "pair": ("financial_request", "credential_theft"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "ICICI Bank advisory: We will never ask you to send money or share your credit card password to process a refund.",
    },
    {
        "id": "P06_FIN_CRED_EN_SCAM",
        "pair": ("financial_request", "credential_theft"),
        "lang": "en",
        "expected": "SCAM",
        "text": "To process the refund of 49,000 rupees on your credit card, please provide your card number, CVV, and OTP right now.",
    },
    {
        "id": "P06_FIN_CRED_HI_BENIGN",
        "pair": ("financial_request", "credential_theft"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "बैंक सतर्कता संदेश: बैंक कभी भी आपसे पैसे भेजने या अपना गोपनीय पासवर्ड बताने को नहीं कहता है।",
    },
    {
        "id": "P06_FIN_CRED_HI_SCAM",
        "pair": ("financial_request", "credential_theft"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "आपके खाते में पच्चीस हजार रुपये ट्रांसफर करने के लिए अपना एटीएम कार्ड नंबर और गुप्त पिन बताओ।",
    },
    {
        "id": "P06_FIN_CRED_HING_BENIGN",
        "pair": ("financial_request", "credential_theft"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Bank notification hai ki kisi ko bhi paise transfer mat karo aur na hi apna net banking password share karo.",
    },
    {
        "id": "P06_FIN_CRED_HING_SCAM",
        "pair": ("financial_request", "credential_theft"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Aapko 5000 rupees cashback transfer karne ke liye apna UPI PIN aur OTP enter karna hoga.",
    },

    # ── Pair 7: (financial_request, remote_access) ───────────────────────────────
    {
        "id": "P07_FIN_REM_EN_BENIGN",
        "pair": ("financial_request", "remote_access"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "My brother was showing me how to setup Google Pay through screen share yesterday, worked smoothly.",
    },
    {
        "id": "P07_FIN_REM_EN_SCAM",
        "pair": ("financial_request", "remote_access"),
        "lang": "en",
        "expected": "SCAM",
        "text": "To claim your refundable deposit of 5000 rupees, install AnyDesk app on your phone and open your Google Pay app.",
    },
    {
        "id": "P07_FIN_REM_HI_BENIGN",
        "pair": ("financial_request", "remote_access"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "कल भैया एनीडेस्क पर स्क्रीन दिखा कर फोन पे चलाना सिखा रहे थे।",
    },
    {
        "id": "P07_FIN_REM_HI_SCAM",
        "pair": ("financial_request", "remote_access"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "रिफंडेबल प्रोसेसिंग फीस ट्रांसफर करने के लिए एनीडेस्क डाउनलोड करो और अपना गूगल पे खोलो।",
    },
    {
        "id": "P07_FIN_REM_HING_BENIGN",
        "pair": ("financial_request", "remote_access"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Kal cousin AnyDesk se screen share karke Paytm wallet setting explain kar raha tha.",
    },
    {
        "id": "P07_FIN_REM_HING_SCAM",
        "pair": ("financial_request", "remote_access"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Payment refund lene ke liye TeamViewer install karo aur UPI scanner se paise transfer accept karo.",
    },

    # ── Pair 8: (urgency_threat, credential_theft) ───────────────────────────────
    {
        "id": "P08_URG_CRED_EN_BENIGN",
        "pair": ("urgency_threat", "credential_theft"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Hey, I am logging into our family Netflix account, did you get the 4-digit login OTP on your phone?",
    },
    {
        "id": "P08_URG_CRED_EN_SCAM",
        "pair": ("urgency_threat", "credential_theft"),
        "lang": "en",
        "expected": "SCAM",
        "text": "Your net banking account is permanently blocked due to suspicious activity! Share the 6-digit OTP sent to your phone immediately to unblock it!",
    },
    {
        "id": "P08_URG_CRED_HI_BENIGN",
        "pair": ("urgency_threat", "credential_theft"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "बेटा, टीवी पर नेटफ्लिक्स चालू कर रहा हूँ, तुम्हारे मोबाइल पर कोई लॉगिन कोड आया क्या?",
    },
    {
        "id": "P08_URG_CRED_HI_SCAM",
        "pair": ("urgency_threat", "credential_theft"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "आपका खाता तुरंत बंद हो जाएगा! कार्ड को चालू रखने के लिए अभी के अभी ओटीपी नंबर शेयर करो!",
    },
    {
        "id": "P08_URG_CRED_HING_BENIGN",
        "pair": ("urgency_threat", "credential_theft"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Bhai Netflix profile login kar raha hoon, phone pe jo OTP aaya bata de jab free ho.",
    },
    {
        "id": "P08_URG_CRED_HING_SCAM",
        "pair": ("urgency_threat", "credential_theft"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Aapka bank account permanently freeze ho jayega! Turant apna 6 digit OTP share kijiye right now!",
    },

    # ── Pair 9: (urgency_threat, remote_access) ──────────────────────────────────
    {
        "id": "P09_URG_REM_EN_BENIGN",
        "pair": ("urgency_threat", "remote_access"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Our IT engineer told me yesterday to download TeamViewer so he could fix my laptop display driver.",
    },
    {
        "id": "P09_URG_REM_EN_SCAM",
        "pair": ("urgency_threat", "remote_access"),
        "lang": "en",
        "expected": "SCAM",
        "text": "Your device has been compromised with severe malware! Download QuickSupport app immediately or your entire system will be wiped right now!",
    },
    {
        "id": "P09_URG_REM_HI_BENIGN",
        "pair": ("urgency_threat", "remote_access"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "दफ्तर के सॉफ्टवेयर में दिक्कत थी तो इंजीनियर ने कल टीमव्यूअर से स्क्रीन चेक की थी।",
    },
    {
        "id": "P09_URG_REM_HI_SCAM",
        "pair": ("urgency_threat", "remote_access"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "आपके फोन में वायरस आ गया है, तुरंत एनीडेस्क ऐप इंस्टॉल करो वरना फोन हमेशा के लिए लॉक हो जाएगा!",
    },
    {
        "id": "P09_URG_REM_HING_BENIGN",
        "pair": ("urgency_threat", "remote_access"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Laptop screen hang ho gayi thi to IT support wale ne TeamViewer download karwaya tha fix karne ke liye.",
    },
    {
        "id": "P09_URG_REM_HING_SCAM",
        "pair": ("urgency_threat", "remote_access"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Turant AnyDesk app install karo abhi ke abhi warna aapka sara data delete ho jayega!",
    },

    # ── Pair 10: (credential_theft, remote_access) ───────────────────────────────
    {
        "id": "P10_CRED_REM_EN_BENIGN",
        "pair": ("credential_theft", "remote_access"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Never type your bank password or credit card CVV while screen sharing on Zoom or Google Meet.",
    },
    {
        "id": "P10_CRED_REM_EN_SCAM",
        "pair": ("credential_theft", "remote_access"),
        "lang": "en",
        "expected": "SCAM",
        "text": "Install AnyDesk app, open your banking application, and enter your net banking password and OTP on the screen.",
    },
    {
        "id": "P10_CRED_REM_HI_BENIGN",
        "pair": ("credential_theft", "remote_access"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "स्क्रीन शेयर करते समय कभी भी अपना बैंक पासवर्ड या एटीएम पिन स्क्रीन पर नहीं दिखाना चाहिए।",
    },
    {
        "id": "P10_CRED_REM_HI_SCAM",
        "pair": ("credential_theft", "remote_access"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "एनीडेस्क डाउनलोड करो और स्क्रीन पर अपना बैंक पासवर्ड और आधार कार्ड नंबर डालो।",
    },
    {
        "id": "P10_CRED_REM_HING_BENIGN",
        "pair": ("credential_theft", "remote_access"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Security guideline hai ki screen share ke dauran apna OTP ya password screen pe mat dikhana.",
    },
    {
        "id": "P10_CRED_REM_HING_SCAM",
        "pair": ("credential_theft", "remote_access"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "AnyDesk connect karo aur screen pe apna debit card number aur OTP verify karo.",
    },

    # ── Pair 11: (lottery_prize, financial_request) ──────────────────────────────
    {
        "id": "P11_LOT_FIN_EN_BENIGN",
        "pair": ("lottery_prize", "financial_request"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Reading an article about how lucky draw lottery winners donate their cash prize money to charity.",
    },
    {
        "id": "P11_LOT_FIN_EN_SCAM",
        "pair": ("lottery_prize", "financial_request"),
        "lang": "en",
        "expected": "SCAM",
        "text": "Congratulations you have won 25 lakh rupees in lottery lucky draw! Pay 5000 rupees processing fee to receive your cash prize.",
    },
    {
        "id": "P11_LOT_FIN_HI_BENIGN",
        "pair": ("lottery_prize", "financial_request"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "समाचार में पढ़ रहा था कि कैसे लॉटरी में इनाम जीतने वाले लोग अस्पताल को पैसे दान करते हैं।",
    },
    {
        "id": "P11_LOT_FIN_HI_SCAM",
        "pair": ("lottery_prize", "financial_request"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "बधाई हो! आपने लॉटरी में पच्चीस लाख का इनाम जीता है! पुरस्कार पाने के लिए तुरंत पंद्रह सौ रुपये प्रोसेसिंग फीस जमा करें।",
    },
    {
        "id": "P11_LOT_FIN_HING_BENIGN",
        "pair": ("lottery_prize", "financial_request"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Ek documentary dekh raha tha jisme lucky draw winner ne cash prize hospital ko donate kar diya.",
    },
    {
        "id": "P11_LOT_FIN_HING_SCAM",
        "pair": ("lottery_prize", "financial_request"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Aapka 10 lakh ka cash prize nikla hai, claim karne ke liye 2500 rupees clearance fee GPay karo.",
    },

    # ── Pair 12: (lottery_prize, urgency_threat) ─────────────────────────────────
    {
        "id": "P12_LOT_URG_EN_BENIGN",
        "pair": ("lottery_prize", "urgency_threat"),
        "lang": "en",
        "expected": "NORMAL",
        "text": "Someone won a mega lottery prize yesterday, crazy story how their life changed overnight haha!",
    },
    {
        "id": "P12_LOT_URG_EN_SCAM",
        "pair": ("lottery_prize", "urgency_threat"),
        "lang": "en",
        "expected": "SCAM",
        "text": "You have won a pre-approved personal loan reward! Offer expires within 15 minutes, claim immediately or your prize will be cancelled!",
    },
    {
        "id": "P12_LOT_URG_HI_BENIGN",
        "pair": ("lottery_prize", "urgency_threat"),
        "lang": "hi",
        "expected": "NORMAL",
        "text": "अरे कल कोई लॉटरी में भारी इनाम जीत गया, रातों-रात किस्मत बदल गई यार।",
    },
    {
        "id": "P12_LOT_URG_HI_SCAM",
        "pair": ("lottery_prize", "urgency_threat"),
        "lang": "hi",
        "expected": "SCAM",
        "text": "आपको दस लाख का लकी ड्रा इनाम मिला है! यह ऑफर केवल दस मिनट में बंद हो जाएगा, तुरंत क्लेम करें!",
    },
    {
        "id": "P12_LOT_URG_HING_BENIGN",
        "pair": ("lottery_prize", "urgency_threat"),
        "lang": "hinglish",
        "expected": "NORMAL",
        "text": "Kal news me dekha ek auto driver ne lottery jeet li lol, lottery lagte hi party shuru ho gayi.",
    },
    {
        "id": "P12_LOT_URG_HING_SCAM",
        "pair": ("lottery_prize", "urgency_threat"),
        "lang": "hinglish",
        "expected": "SCAM",
        "text": "Aapka prize money cancel ho jayega agar turant right now claim nahi kiya, last warning hai!",
    },
]

def run_matrix():
    print("=" * 105)
    print("VOICESHIELD SYSTEMATIC CATEGORY-PAIR TEST MATRIX EVALUATION")
    print("=" * 105)

    # 1. Verify Pair Completeness Assertion
    pair_counts = {}
    for item in TEST_MATRIX:
        pair_key = tuple(sorted(item["pair"]))
        exp = item["expected"]
        if pair_key not in pair_counts:
            pair_counts[pair_key] = {"NORMAL": 0, "SCAM": 0}
        pair_counts[pair_key][exp] += 1

    for pair_key, counts in pair_counts.items():
        assert counts["NORMAL"] > 0, f"Violation: Category pair {pair_key} is missing a BENIGN (NORMAL) counterpart!"
        assert counts["SCAM"] > 0, f"Violation: Category pair {pair_key} is missing a MALICIOUS (SCAM) counterpart!"

    print(f"Matrix Completeness: Verified {len(pair_counts)} category pairs (each has >= 1 BENIGN and >= 1 MALICIOUS counterpart)")
    print(f"Total Test Cases: {len(TEST_MATRIX)}")
    print("-" * 105)

    all_passed = True
    failures = []
    for item in TEST_MATRIX:
        res = score_intent(item["text"])
        risk = res["intent_risk"]
        exp = item["expected"]
        label = "SCAM" if risk >= 0.50 else "NORMAL"
        passed = (label == exp)
        status_tag = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
            failures.append((item["id"], exp, label, risk, res["categories"], res["matched"], item["text"]))
        print(f"{item['id']:28} | Pair: {str(item['pair']):45} | Risk: {risk:5.3f} | Exp: {exp:6} | Got: {label:6} | {status_tag}")

    print("=" * 105)
    if all_passed:
        print("RESULT: ALL MATRIX TEST CASES PASSED (100% ACCURACY ACROSS ALL PAIRS & LANGUAGES)!")
    else:
        print(f"RESULT: {len(failures)} FAILURES ENCOUNTERED:")
        for fid, exp, got, risk, cats, matched, text in failures:
            print(f"  FAIL: {fid} (Exp: {exp}, Got: {got}, Risk: {risk:.3f}, Cats: {cats}, Matched: {matched}) Text: '{text}'")
        sys.exit(1)

if __name__ == "__main__":
    run_matrix()

def run_suite():
    print('=' * 105)
    print('VOICESHIELD ACCEPTANCE TEST: LAYER 2 SCAM-INTENT CLASSIFIER')
    print('=' * 105)

    all_passed = True
    failures = []

    # ── Part 1: Sanity & Hard Negatives ──
    print(f'\n[1/3] Running {len(SANITY_CASES)} Sanity & Hard-Negative Test Cases...')
    print(f"{'SCENARIO':35} | {'RISK':8} | {'VERDICT':8} | {'STATUS':6} | {'MATCHED'}")
    print('-' * 105)
    for name, text in SANITY_CASES:
        is_scam = name.startswith('Scam:')
        r = score_intent(text)
        risk = r['intent_risk']
        verdict = 'SCAM' if risk >= 0.50 else 'NORMAL'
        expected = 'SCAM' if is_scam else 'NORMAL'
        status_ok = (verdict == expected)
        if not status_ok:
            all_passed = False
            failures.append(f'Sanity: {name} (expected {expected}, got {verdict}, risk {risk:.3f})')
        tag = 'PASS' if status_ok else 'FAIL'
        matched_str = ', '.join(r['matched'][:2])
        print(f"{name:35} | {risk:8.3f} | {verdict:8} | {tag:6} | {matched_str}")

    # ── Part 2: Pair-Completeness & Coverage Validation ──
    print(f'\n[2/3] Validating Systematic Category-Pair Matrix Completeness (72 cases)...')
    pair_counts = defaultdict(lambda: {'NORMAL': 0, 'SCAM': 0, 'langs': set()})
    for c in TEST_MATRIX:
        pair_counts[c['pair']][c['expected']] += 1
        pair_counts[c['pair']]['langs'].add(c['lang'])

    completeness_failures = []
    for pair, stats in pair_counts.items():
        if stats['NORMAL'] < 1:
            completeness_failures.append(f'Missing benign counterpart for pair: {pair}')
        if stats['SCAM'] < 1:
            completeness_failures.append(f'Missing malicious counterpart for pair: {pair}')
        for req_lang in ('en', 'hi', 'hinglish'):
            if req_lang not in stats['langs']:
                completeness_failures.append(f'Pair {pair} missing coverage for language: {req_lang}')

    if completeness_failures:
        print('  ❌ Pair-completeness validation failed:')
        for cf in completeness_failures:
            print(f'    - {cf}')
        all_passed = False
        failures.extend(completeness_failures)
    else:
        print(f'  ✔ All {len(pair_counts)} category pairs have balanced benign/scam counterparts across EN, HI, Hinglish.')

    # ── Part 3: Matrix Test Cases ──
    print(f'\n[3/3] Running {len(TEST_MATRIX)} Systematic Category-Pair Test Cases...')
    print(f"{'ID':28} | {'PAIR':48} | {'RISK':6} | {'EXP':6} | {'GOT':6} | {'STATUS'}")
    print('-' * 105)
    matrix_passes = 0
    for c in TEST_MATRIX:
        r = score_intent(c['text'])
        risk = r['intent_risk']
        verdict = 'SCAM' if risk >= 0.50 else 'NORMAL'
        status_ok = (verdict == c['expected'])
        if status_ok:
            matrix_passes += 1
        else:
            all_passed = False
            failures.append(f"{c['id']}: expected {c['expected']}, got {verdict}, risk {risk:.3f}, matched: {r['matched']}")
        tag = 'PASS' if status_ok else 'FAIL'
        pair_str = str(c['pair'])
        print(f"{c['id']:28} | {pair_str:48} | {risk:6.3f} | {c['expected']:6} | {verdict:6} | {tag}")

    print('=' * 105)
    total_cases = len(SANITY_CASES) + len(TEST_MATRIX)
    print(f'SUMMARY: {len(SANITY_CASES)} sanity cases + {matrix_passes}/{len(TEST_MATRIX)} matrix cases passed.')

    if all_passed:
        print(f'\n🎉 ACCEPTANCE TEST RESULT: ALL {total_cases} CASES PASSED (100% COVERAGE & ACCURACY)!')
        sys.exit(0)
    else:
        print(f'\n❌ ACCEPTANCE TEST RESULT: {len(failures)} FAILURES ENCOUNTERED:')
        for f in failures:
            print(f'  - {f}')
        sys.exit(1)

if __name__ == '__main__':
    run_suite()
