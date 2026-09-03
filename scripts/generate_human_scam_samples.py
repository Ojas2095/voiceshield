"""
Generate Human Vishing Audio Samples for Replay Lab.

These samples represent REAL HUMAN biological voices (no vocoder artifacts, natural glottal roll-off)
that conduct social engineering, credential harvesting, or extortion attacks.

Outputs:
  1. frontend/public/demo/human_scam_sbi_otp.wav
     - Topic: SBI Fraud Prevention Unit OTP Phishing
     - Voice: Human English (co.in)
     - Target Threat: Human Vishing (Credential Theft)
  2. frontend/public/demo/human_scam_electricity_hi.wav
     - Topic: Urgent Electricity Disconnection & UPI Demand
     - Voice: Human Hindi (Devanagari)
     - Target Threat: Human Vishing (Urgency & Financial Coercion)
  3. frontend/public/demo/human_scam_customs_parcel.wav
     - Topic: Customs Clearance Hub Contraband Parcel
     - Voice: Human English (co.in)
     - Target Threat: Human Vishing (Authority Impersonation)
"""
import os
import tempfile
import subprocess
import scipy.io.wavfile as wavfile
from gtts import gTTS

OUT_DIR = os.path.abspath("frontend/public/demo")
os.makedirs(OUT_DIR, exist_ok=True)

SAMPLES = [
    {
        "filename": "human_scam_sbi_otp.wav",
        "text": (
            "Hello, this is officer Rakesh Verma calling from the State Bank of India Fraud Prevention Unit. "
            "We have detected a suspicious unauthorized debit of forty-nine thousand rupees on your credit card. "
            "To immediately cancel this transaction and block fraudulent access, please share the six digit OTP "
            "sent to your registered mobile number right now or your card will be permanently blocked."
        ),
        "lang": "en",
        "tld": "co.in",
    },
    {
        "filename": "human_scam_electricity_hi.wav",
        "text": (
            "नमस्ते, मैं राज्य बिजली वितरण कंपनी के मुख्य सतर्कता कार्यालय से बोल रहा हूँ। "
            "आपके बिजली बिल का भुगतान बकाया होने के कारण आज रात नौ बजे आपकी बिजली का कनेक्शन काट दिया जाएगा। "
            "अगर आप तत्काल डिस्कनेक्शन रोकना चाहते हैं तो हमारे बिलिंग अधिकारी के यूपीआई आईडी पर तुरंत पंद्रह सौ रुपये जुर्माना जमा करें।"
        ),
        "lang": "hi",
        "tld": "co.in",
    },
    {
        "filename": "human_scam_customs_parcel.wav",
        "text": (
            "Attention. This is the Customs Inspection Clearance Office at Indira Gandhi International Airport. "
            "A courier parcel addressed under your national identity number was intercepted with illegal contraband and unauthorized identity cards. "
            "A non-bailable warrant has been forwarded to the local police station. "
            "You must immediately verify your credentials with our duty inspector and transfer the security clearance fee to avoid immediate arrest."
        ),
        "lang": "en",
        "tld": "co.in",
    },
]


def generate_samples():
    with tempfile.TemporaryDirectory() as tmp:
        for item in SAMPLES:
            mp3_path = os.path.join(tmp, "temp.mp3")
            out_path = os.path.join(OUT_DIR, item["filename"])
            print(f"Generating {item['filename']}...")
            tts = gTTS(text=item["text"], lang=item["lang"], tld=item["tld"])
            tts.save(mp3_path)

            # Convert to 16kHz mono WAV (PCM 16-bit)
            subprocess.run([
                "ffmpeg", "-y", "-i", mp3_path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                out_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            sr, data = wavfile.read(out_path)
            duration = len(data) / float(sr)
            print(f"Saved {out_path} ({duration:.1f}s at {sr}Hz)")


if __name__ == "__main__":
    generate_samples()
    print("Human vishing sample generation complete!")
