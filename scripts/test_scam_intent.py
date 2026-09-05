from intelligence.intent_classifier import score_intent

scripts = [
    ('Normal conversation 1', 'Hey bro, how are you? Are we meeting for coffee today at the cafeteria?'),
    ('Normal conversation 2', 'Let us review the presentation slides for tomorrow morning meeting with the team.'),
    ('Normal conversation 3', 'Haan bhai kaisa hai, kal chalte hain college project submit karne.'),
    ('Normal conversation 4', 'What is the weather forecast for tomorrow? Looks like it might rain in the evening.'),
    ('Scam: SBI OTP Phishing', 'Dear customer your SBI debit card is blocked. Please share the 6-digit OTP sent to your phone immediately to verify.'),
    ('Scam: Digital Arrest', 'This is Inspector Sharma from Cyber Crime Police Station. A parcel with illegal drugs was seized in your name. You are under digital arrest, transfer money immediately to avoid FIR.'),
    ('Scam: Electricity Disconnect', 'Your electricity connection will be disconnected tonight at 9:30 PM due to unpaid bill. Call this number and pay the bill immediately.'),
    ('Scam: Hindi OTP Scam', 'Sir main State Bank se bol raha hoon, aapka khata band ho jayega, turant OTP bataiye.'),
    ('Scam: Customs CBI', 'Customs office Mumbai se bol raha hoon, aapke courier me fake passport aur narcotics mila hai, turant arrest warrant jari hoga.'),
]

print(f"{'SCENARIO':32} | {'INTENT RISK':12} | {'VERDICT':10} | {'MATCHED'}")
print('-' * 85)
for name, text in scripts:
    r = score_intent(text)
    risk = r['intent_risk']
    label = 'SCAM' if risk >= 0.40 else 'NORMAL'
    matched_str = ', '.join(r['matched'][:2])
    print(f"{name:32} | {risk:10.4f}   | {label:10} | {matched_str}")
