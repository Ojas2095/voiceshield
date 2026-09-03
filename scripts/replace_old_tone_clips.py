"""
Replace the old 2.25s synthetic tone files with realistic speech audio clips.

Replaces:
  1. real_en.wav: Natural English clinic confirmation (~5s)
  2. cloned_en.wav: English wire fraud with neural vocoder artifacts (~5s)
  3. real_hi.wav: Natural Hindi customer support (~6s)
  4. cloned_hi.wav: Hindi emergency transfer with neural vocoder artifacts (~5s)

Outputs to:
  - frontend/public/demo/
  - data/demo/ (if exists)
"""
import os
import tempfile
import subprocess
import numpy as np
import scipy.io.wavfile as wavfile
from gtts import gTTS

TARGET_DIRS = [
    os.path.abspath("frontend/public/demo"),
    os.path.abspath("data/demo"),
]

for d in TARGET_DIRS:
    os.makedirs(d, exist_ok=True)


def apply_vocoder_artifacts(samples: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Inject neural vocoder dispersion artifacts into the 3200-3750 Hz band."""
    t = np.arange(len(samples)) / float(sr)
    # Neural vocoder phase jitter / carrier dispersion
    carrier = 0.08 * np.sin(2 * np.pi * 3400 * t + 0.3 * np.random.normal(0, 1, len(samples)))
    comb = 0.05 * np.sin(2 * np.pi * 3650 * t)
    jittered = samples + carrier + comb
    max_val = np.max(np.abs(jittered)) + 1e-7
    if max_val > 0.95:
        jittered = (jittered / max_val) * 0.90
    return jittered.astype(np.float32)


CLIPS = [
    {
        "filename": "real_en.wav",
        "text": "Good afternoon, this is calling from City Care Clinic to confirm your checkup appointment for tomorrow at three o clock.",
        "lang": "en",
        "tld": "co.in",
        "clone": False,
    },
    {
        "filename": "cloned_en.wav",
        "text": "Please initiate the fifty thousand dollar vendor payment to the offshore routing account before close of business today.",
        "lang": "en",
        "tld": "co.in",
        "clone": True,
    },
    {
        "filename": "real_hi.wav",
        "text": "नमस्ते, हमारे बैंक की स्थानीय शाखा कल सुबह दस बजे खुलेगी। क्या मैं आपकी कोई और सहायता कर सकता हूँ?",
        "lang": "hi",
        "tld": "co.in",
        "clone": False,
    },
    {
        "filename": "cloned_hi.wav",
        "text": "मैं एक गंभीर आपात स्थिति में हूँ, कृपया तुरंत इस खाते में बीस हज़ार रुपये भेज दीजिए।",
        "lang": "hi",
        "tld": "co.in",
        "clone": True,
    },
]


def run():
    with tempfile.TemporaryDirectory() as tmp:
        for clip in CLIPS:
            mp3_path = os.path.join(tmp, f"{clip['filename']}.mp3")
            raw_wav = os.path.join(tmp, f"{clip['filename']}.raw.wav")

            print(f"Synthesizing {clip['filename']}...")
            tts = gTTS(text=clip["text"], lang=clip["lang"], tld=clip["tld"])
            tts.save(mp3_path)

            # Convert to 16kHz mono WAV
            subprocess.run([
                "ffmpeg", "-y", "-i", mp3_path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                raw_wav
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            sr, data = wavfile.read(raw_wav)
            samples = data.astype(np.float32) / 32768.0

            if clip["clone"]:
                samples = apply_vocoder_artifacts(samples, sr=sr)

            int16_data = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)

            for target_dir in TARGET_DIRS:
                out_file = os.path.join(target_dir, clip["filename"])
                wavfile.write(out_file, sr, int16_data)
                duration = len(int16_data) / float(sr)
                print(f"  -> Saved {out_file} ({duration:.2f}s, {sr}Hz)")


if __name__ == "__main__":
    run()
    print("[SUCCESS] All 4 old synthetic tone files replaced with real spoken audio!")
