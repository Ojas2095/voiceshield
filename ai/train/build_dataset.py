"""
VoiceShield — Dataset Builder (for your friend)
================================================
Downloads real speech, generates AI fakes, applies telephony augmentation,
and outputs a structured PyTorch dataset ready for training.

Usage:
    python -m ai.train.build_dataset --output_dir ./data --num_fake_per_real 2
"""
import os
import sys
import argparse
import random
import json
import torch
import torchaudio
import numpy as np
from pathlib import Path
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ai.preprocessing import apply_telephony_degradation, resample, pad_or_trim, TELEPHONY_SR


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg"}
TARGET_DURATION = 2.0  # seconds
TARGET_SAMPLES = int(TELEPHONY_SR * TARGET_DURATION)


def discover_audio_files(directory: str) -> List[Path]:
    """Recursively find all audio files in a directory."""
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(Path(directory).rglob(f"*{ext}"))
    return sorted(files)


def load_and_preprocess(filepath: Path, apply_augmentation: bool = True) -> torch.Tensor:
    """
    Load an audio file, resample to 8kHz, apply telephony degradation,
    and pad/trim to exactly 2 seconds.
    """
    waveform, sr = torchaudio.load(str(filepath))

    # Convert to mono if stereo
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Apply telephony degradation (8kHz + bandpass + noise)
    if apply_augmentation:
        waveform = apply_telephony_degradation(waveform, sr)
    else:
        waveform = resample(waveform, sr, TELEPHONY_SR)

    # Pad/trim to exactly 2 seconds
    waveform = pad_or_trim(waveform, TARGET_SAMPLES)

    return waveform


def generate_fake_with_gtts(text: str, output_path: str, lang: str = "en") -> bool:
    """Generate a fake audio sample using Google TTS (supports 'hi', 'ta', 'bn', ...)."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_path)
        return True
    except Exception as e:
        print(f"  [gTTS] Failed: {e}")
        return False


def generate_fake_with_xtts(text: str, speaker_wav: str, output_path: str, language: str = "en") -> bool:
    """
    Generate a cloned voice using Coqui XTTS-v2 (multilingual — set language='hi'
    for Hindi clones). Requires: pip install TTS
    """
    try:
        from TTS.api import TTS
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=torch.cuda.is_available())
        tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=output_path,
        )
        return True
    except Exception as e:
        print(f"  [XTTS] Failed: {e}")
        return False


# Realistic scam scripts to synthesize as fakes, per language.
SCAM_TEXTS = {
    "en": [
        "Hello, this is your bank calling about your account.",
        "Please share your OTP for verification purposes.",
        "Your account has been compromised, transfer funds immediately.",
        "This is the police, you are under digital arrest.",
        "Please confirm your identity by providing your Aadhaar number.",
        "Your credit card has been blocked due to suspicious activity.",
        "We need to verify your account, please stay on the line.",
        "Your loan application has been approved, please confirm.",
        "There is a warrant issued in your name, cooperate now.",
        "Install AnyDesk so we can process your refund.",
    ],
    "hi": [
        "नमस्ते, मैं आपके बैंक से बोल रहा हूँ, आपके खाते के बारे में बात करनी है।",
        "कृपया वेरिफिकेशन के लिए अपना ओटीपी बताइए।",
        "आपका खाता हैक हो गया है, तुरंत पैसे ट्रांसफर कीजिए।",
        "मैं पुलिस से बोल रहा हूँ, आप डिजिटल अरेस्ट में हैं।",
        "अपनी पहचान की पुष्टि के लिए अपना आधार नंबर बताइए।",
        "आपका क्रेडिट कार्ड संदिग्ध गतिविधि के कारण ब्लॉक कर दिया गया है।",
        "आपके नाम पर वारंट है, अभी सहयोग कीजिए वरना गिरफ्तारी होगी।",
        "केवाईसी अपडेट करने के लिए यह ऐप इंस्टॉल कीजिए।",
    ],
}


def build_dataset(
    real_audio_dir: str,
    output_dir: str,
    num_fake_per_real: int = 2,
    use_xtts: bool = True,
    texts_for_tts: List[str] = None,
    lang: str = "en",
):
    """
    Build the full training dataset.

    Structure:
        output_dir/
        ├── real/       # Telephony-augmented real speech
        ├── fake/       # Telephony-augmented AI-generated speech
        └── manifest.json  # Metadata for all samples
    """
    output = Path(output_dir)
    real_out = output / "real"
    fake_out = output / "fake"
    real_out.mkdir(parents=True, exist_ok=True)
    fake_out.mkdir(parents=True, exist_ok=True)

    if texts_for_tts is None:
        texts_for_tts = SCAM_TEXTS.get(lang, SCAM_TEXTS["en"])

    manifest = []
    real_files = discover_audio_files(real_audio_dir)

    if not real_files:
        print(f"[ERROR] No audio files found in {real_audio_dir}")
        print("Please download Mozilla Common Voice or add your own .wav files.")
        return

    print(f"Found {len(real_files)} real audio files")

    # Process real audio
    for i, filepath in enumerate(real_files):
        try:
            waveform = load_and_preprocess(filepath, apply_augmentation=True)
            out_path = real_out / f"real_{i:05d}.wav"
            torchaudio.save(str(out_path), waveform, TELEPHONY_SR)
            manifest.append({
                "path": str(out_path.relative_to(output)),
                "label": 0,  # 0 = real
                "source": str(filepath.name),
                "generator": "human",
            })
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(real_files)} real samples")
        except Exception as e:
            print(f"  [SKIP] {filepath.name}: {e}")

    # Generate fake audio
    fake_count = 0
    for i in range(len(real_files) * num_fake_per_real):
        text = random.choice(texts_for_tts)
        raw_path = str(fake_out / f"fake_raw_{fake_count:05d}.wav")

        # Alternate between generators
        success = False
        if use_xtts and fake_count % 3 != 0:
            # Use a random real file as the speaker reference for cloning
            ref_file = str(random.choice(real_files))
            success = generate_fake_with_xtts(text, ref_file, raw_path, language=lang)
            generator = "xtts_v2"

        if not success:
            success = generate_fake_with_gtts(text, raw_path, lang=lang)
            generator = "gtts"

        if success and os.path.exists(raw_path):
            try:
                waveform = load_and_preprocess(Path(raw_path), apply_augmentation=True)
                out_path = fake_out / f"fake_{fake_count:05d}.wav"
                torchaudio.save(str(out_path), waveform, TELEPHONY_SR)
                manifest.append({
                    "path": str(out_path.relative_to(output)),
                    "label": 1,  # 1 = fake
                    "source": text[:50],
                    "generator": generator,
                })
                fake_count += 1
                # Clean up raw file
                os.remove(raw_path)
            except Exception as e:
                print(f"  [SKIP] fake_{fake_count}: {e}")

        if (fake_count + 1) % 50 == 0:
            print(f"  Generated {fake_count + 1} fake samples")

    # Save full manifest
    manifest_path = output / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Held-out train/test split (stratified by label, fixed seed) so evaluation
    # is done on data the model NEVER trained on — otherwise EER is ~0% (leakage).
    rng = random.Random(42)
    reals = [m for m in manifest if m["label"] == 0]
    fakes = [m for m in manifest if m["label"] == 1]

    def _split(items):
        items = items[:]
        rng.shuffle(items)
        k = int(len(items) * 0.2)          # 20% held out for test
        return items[k:], items[:k]

    tr_r, te_r = _split(reals)
    tr_f, te_f = _split(fakes)
    train_manifest = tr_r + tr_f
    test_manifest = te_r + te_f
    rng.shuffle(train_manifest)
    rng.shuffle(test_manifest)
    with open(output / "manifest_train.json", "w") as f:
        json.dump(train_manifest, f, indent=2)
    with open(output / "manifest_test.json", "w") as f:
        json.dump(test_manifest, f, indent=2)
    print(f"  Held-out split: train={len(train_manifest)}  test={len(test_manifest)}")

    print(f"\n=== Dataset Complete ===")
    print(f"  Real samples: {sum(1 for m in manifest if m['label'] == 0)}")
    print(f"  Fake samples: {sum(1 for m in manifest if m['label'] == 1)}")
    print(f"  Manifest: {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build VoiceShield training dataset")
    parser.add_argument("--real_dir", type=str, required=True, help="Directory of real audio files")
    parser.add_argument("--output_dir", "--out", type=str, default="./data", help="Output directory")
    parser.add_argument("--num_fake", type=int, default=2, help="Fake samples per real sample")
    parser.add_argument("--no_xtts", action="store_true", help="Disable XTTS (gTTS only)")
    parser.add_argument("--lang", type=str, default="en",
                        help="Language for synthesized fakes: en, hi, ta, bn, ... (Hindi backs the Indian-language claim)")
    args = parser.parse_args()

    build_dataset(
        real_audio_dir=args.real_dir,
        output_dir=args.output_dir,
        num_fake_per_real=args.num_fake,
        use_xtts=not args.no_xtts,
        lang=args.lang,
    )
