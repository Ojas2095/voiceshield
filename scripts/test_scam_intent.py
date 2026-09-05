import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from intelligence.intent_classifier import score_intent

scripts = [
    # ── Standard Benign Dialogues ──
    ('Normal: Coffee meeting', 'Hey bro, how are you? Are we meeting for coffee today at the cafeteria?'),
    ('Normal: Project review', 'Let us review the presentation slides for tomorrow morning meeting with the team.'),
    ('Normal: Hinglish college', 'Haan bhai kaisa hai, kal chalte hain college project submit karne.'),
    ('Normal: Weather inquiry', 'What is the weather forecast for tomorrow? Looks like it might rain in the evening.'),

    # ── 6 Hard Negatives (Scam-adjacent words in benign/casual contexts) ──
    ('Hard Neg: Traffic fine joke', 'Traffic police stopped me today haha, had to pay a 500 rupees fine, lol so annoying.'),
    ('Hard Neg: Legitimate courier', 'Hello, this is BlueDart courier service confirming your package delivery for today afternoon.'),
    ('Hard Neg: Family Netflix OTP', 'Beta, I am logging into our family Netflix account, did you get the login OTP on your phone?'),
    ('Hard Neg: Real bank advisory', 'Good morning, this is ICICI Bank fraud alert service. We noticed unusual activity. Please check your net banking or visit your branch. Never share your password with anyone.'),
    ('Hard Neg: Tech ML discussion', 'We are building a machine learning model for cyber crime and credit card fraud prevention.'),
    ('Hard Neg: Past customs anecdote', 'My friend was telling me yesterday about how someone got arrested by customs at the airport for smuggled goods, crazy story!'),

    # ── Confirmed Scam Scenarios ──
    ('Scam: SBI OTP Phishing', 'Dear customer your SBI debit card is blocked. Please share the 6-digit OTP sent to your phone immediately to verify.'),
    ('Scam: Digital Arrest', 'This is Inspector Sharma from Cyber Crime Police Station. A parcel with illegal drugs was seized in your name. You are under digital arrest, transfer money immediately to avoid FIR.'),
    ('Scam: Electricity Disconnect', 'Your electricity connection will be disconnected tonight at 9:30 PM due to unpaid bill. Call this number and pay the bill immediately.'),
    ('Scam: Hindi OTP Scam', 'Sir main State Bank se bol raha hoon, aapka khata band ho jayega, turant OTP bataiye.'),
    ('Scam: Customs CBI', 'Customs office Mumbai se bol raha hoon, aapke courier me fake passport aur narcotics mila hai, turant arrest warrant jari hoga.'),
]

print(f"{'SCENARIO':35} | {'INTENT RISK':12} | {'VERDICT':10} | {'STATUS':6} | {'MATCHED'}")
print('-' * 95)
all_passed = True
for name, text in scripts:
    is_scam = name.startswith('Scam:')
    r = score_intent(text)
    risk = r['intent_risk']
    label = 'SCAM' if risk >= 0.50 else 'NORMAL'
    matched_str = ', '.join(r['matched'][:2])
    status_ok = (label == 'SCAM') if is_scam else (label == 'NORMAL')
    if not status_ok:
        all_passed = False
    status_tag = 'PASS' if status_ok else 'FAIL'
    print(f"{name:35} | {risk:10.4f}   | {label:10} | {status_tag:6} | {matched_str}")

print('-' * 95)
print(f"ACCEPTANCE TEST RESULT: {'100% PASSED - READY FOR MERGE' if all_passed else 'FAILED'}")
if not all_passed:
    import sys
    sys.exit(1)
