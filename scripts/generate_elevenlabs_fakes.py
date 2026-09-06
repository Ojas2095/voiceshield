"""
VoiceShield — Multi-Engine Synthetic Voice Generator (ElevenLabs)
================================================================
Generates 35 diverse synthetic speech clips across multiple voices and prompts
using the ElevenLabs API with direct 16kHz linear PCM streaming.

Saves clips to `data/fake/elevenlabs/` and logs acoustic sanity metrics
(duration, hf_ratio, jitter) to confirm valid non-silent audio.
"""
import sys
import os
import time
import json
import urllib.request
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "fake" / "elevenlabs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load API key from env or backend_v2/.env
API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
if not API_KEY:
    env_file = REPO_ROOT / "backend_v2" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip()

if not API_KEY:
    print("[ERROR] ELEVENLABS_API_KEY not found in environment or backend_v2/.env")
    sys.exit(1)

# Diverse ElevenLabs voice IDs across genders & accents
VOICES = [
    ("Roger", "CwhRBWXzGAHq8TQ4Fs17", "Male American"),
    ("Sarah", "EXAVITQu4vr4xnSDxMaL", "Female American"),
    ("Charlie", "IKne3meq5aSn9XLyUdCD", "Male Australian"),
    ("George", "JBFqnCBsd6RMkjVDRZzb", "Male British"),
    ("Alice", "Xb7hH8MSUJpSbSDYk0k2", "Female British"),
    ("Callum", "N2lVS1w4EtoT3dr4eOWO", "Male American Character"),
    ("Laura", "FGY2WhTYpPnrIDTdsKH5", "Female American Expressive"),
    ("River", "SAz9YHcvj6GT2YYXdXww", "Neutral American"),
]

# Realistic scam, fraud, and conversational scripts (concise, high impact)
PROMPTS = [
    # English Scam & Impersonation
    ("en", "This is an urgent call from State Bank fraud department. Your debit card has been locked. Share the one time password now."),
    ("en", "Hello, I am calling from Mumbai Police cyber division. An arrest warrant is issued in your name regarding money laundering."),
    ("en", "Attention, your electricity connection will be terminated tonight at eight PM due to overdue charges. Pay immediately."),
    ("en", "Customs inspection office at airport. A parcel containing contraband in your name was intercepted. Transfer penalty immediately."),
    ("en", "Dear customer, your credit card loyalty reward of twenty five thousand rupees is expiring today. Confirm your PIN to redeem."),
    ("en", "This is Microsoft technical support. We detected dangerous trojan malware on your computer. Download our remote tool now."),
    ("en", "Notice from tax department. Immediate settlement is required for your pending assessment or legal action will follow."),
    ("en", "Your package delivery failed because shipping address is incomplete. Please pay thirty rupees re-delivery fee right now."),
    ("en", "Your savings account has been put on temporary hold. Provide your account number and security code to restore access."),
    ("en", "Urgent alert: unauthorized transaction of forty thousand rupees detected on your wallet. Call back immediately to reverse."),

    # English Conversational / Dialogue
    ("en", "Hi there, are we still scheduled for our project sync meeting this afternoon at three?"),
    ("en", "Good morning, I reviewed the financial quarterly summary and sent the updated draft to your email."),
    ("en", "Hey, don't forget to submit the assignment before midnight today so we can finalize the presentation."),
    ("en", "Hello, I wanted to follow up regarding our phone conversation yesterday about the software demo."),
    ("en", "Could you please send me the contact information for the vendor we spoke with earlier this week?"),

    # Hindi / Hinglish Scam & Impersonation
    ("hi", "नमस्ते, मैं स्टेट बैंक ऑफ इंडिया के फ्रॉड डिपार्टमेंट से बोल रहा हूँ। आपका खाता ब्लॉक हो गया है, तुरंत ओटीपी बताएं।"),
    ("hi", "यह क्राइम ब्रांच मुंबई पुलिस का अलर्ट है। आपके आधार कार्ड पर मनी लॉन्ड्रिंग का केस दर्ज हुआ है।"),
    ("hi", "आपकी बिजली का बिल बकाया होने के कारण आज रात नौ बजे बिजली काट दी जाएगी। तुरंत भुगतान करें।"),
    ("hi", "कस्टम्स विभाग से बोल रहा हूँ। आपके नाम का एक पार्सल पकड़ा गया है, तुरंत दिए गए खाते में जुर्माना जमा कराएं।"),
    ("hi", "प्रिय ग्राहक, आपके क्रेडिट कार्ड रिवार्ड पॉइंट्स एक्सपायर हो रहे हैं, तुरंत रिडीम करने के लिए अपना पासवर्ड बताएं।"),
    ("hi", "कस्टमर केयर से बोल रहा हूँ, आपका सिम कार्ड चौबीस घंटे में बंद हो जाएगा, री-वेरिफिकेशन के लिए डिटेल दें।"),
    ("hi", "इनकम टैक्स डिपार्टमेंट का फाइनल नोटिस है, कानूनी कार्रवाई से बचने के लिए तुरंत पेनल्टी ट्रांसफर करें।"),
    ("hi", "आपके बैंक खाते से तीस हजार रुपये का अनाधिकृत लेनदेन हुआ है, तुरंत स्टॉप करने के लिए पिन बताएं।"),

    # Hindi Conversational / Dialogue
    ("hi", "नमस्ते, क्या आप आज शाम की मीटिंग में शामिल हो रहे हैं? मुझे प्रेजेंटेशन के बारे में बात करनी थी।"),
    ("hi", "अरे भाई कैसे हो, कल कॉलेज का प्रोजेक्ट फाइनल करना है, टाइम से आ जाना।"),
    ("hi", "मैंने रिपोर्ट चेक कर ली है और सारे बदलाव फाइल में अपडेट कर दिए हैं।"),
    ("hi", "शुभ प्रभात, आज का मौसम बहुत अच्छा है, क्या आज शाम को कॉफी के लिए मिलना संभव है?"),
    ("hi", "कृपया मुझे उस वेंडर का फोन नंबर भेज दीजिए जिससे हमारी कल बात हुई थी।"),

    # Cross-accent variations
    ("en", "Security alert: multiple failed login attempts on your banking portal. Verify your credentials immediately."),
    ("en", "This is an automated reminder regarding your overdue loan installment. Settle the balance today to avoid recovery visit."),
    ("en", "Congratulations! You have been selected as the grand prize winner of fifty thousand dollars. Claim your prize now."),
    ("en", "Police headquarters notification. You must remain on this video call under digital arrest until verification completes."),
    ("hi", "सतर्कता कार्यालय विद्युत वितरण निगम। आपके मीटर का बकाया बिल तुरंत जमा करें वरना लाइन काट दी जाएगी।"),
    ("hi", "साइबर सेल नई दिल्ली। आपके खिलाफ गैरकानूनी पार्सल का वारंट जारी किया गया है। तुरंत संपर्क करें।"),
    ("en", "Thank you for contacting customer support. How may I assist you with your subscription renewal today?")
]


def generate_clip(text: str, lang: str, voice_name: str, voice_id: str, index: int) -> Path | None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_16000"
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "xi-api-key": API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "VoiceShield-Synthesizer/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pcm_data = resp.read()
    except Exception as e:
        print(f"  ❌ [{index:02d}] Failed {voice_name} ({lang}): {e}")
        return None

    arr = np.frombuffer(pcm_data, dtype=np.int16)
    if len(arr) < 8000:
        print(f"  ⚠ [{index:02d}] Audio too short (< 0.5s): {len(arr)} samples")
        return None

    # Sanity metrics
    samples = arr.astype(np.float32) / 32768.0
    duration_s = len(samples) / 16000.0

    # Measure HF ratio
    n = min(len(samples), 32000)
    fft_mag = np.abs(np.fft.rfft(samples[:n]))
    freqs = np.fft.rfftfreq(n, 1.0 / 16000.0)
    hf_mask = (freqs >= 2800) & (freqs <= 3400)
    lf_mask = (freqs >= 250) & (freqs <= 2200)
    hf_energy = float(np.mean(fft_mag[hf_mask] ** 2)) if np.any(hf_mask) else 0.0
    lf_energy = float(np.mean(fft_mag[lf_mask] ** 2)) + 1e-9
    hf_ratio = hf_energy / lf_energy

    out_file = OUT_DIR / f"elevenlabs_{index:03d}_{voice_name.lower()}_{lang}.wav"
    wavfile.write(str(out_file), 16000, arr)

    print(f"  ✔ [{index:02d}] {out_file.name:42} ({duration_s:.1f}s, hf_ratio={hf_ratio:.3f}, voice={voice_name})")
    return out_file


def main():
    print("=" * 80)
    print("VOICESHIELD: GENERATING MULTI-ENGINE SYNTHETIC SPEECH VIA ELEVENLABS")
    print(f"Destination directory: {OUT_DIR}")
    print(f"Target count: {len(PROMPTS)} clips")
    print("=" * 80)

    generated = []
    t0 = time.time()

    for idx, (lang, text) in enumerate(PROMPTS, start=1):
        voice_name, voice_id, voice_desc = VOICES[(idx - 1) % len(VOICES)]
        out = generate_clip(text, lang, voice_name, voice_id, idx)
        if out:
            generated.append(out)
        time.sleep(0.3)  # Gentle rate limit pacing

    elapsed = time.time() - t0
    print("\n" + "=" * 80)
    print(f"🎉 GENERATION COMPLETE: {len(generated)}/{len(PROMPTS)} clips generated in {elapsed:.1f}s")
    print(f"Location: {OUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
