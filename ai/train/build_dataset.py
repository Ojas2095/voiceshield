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


def generate_fake_with_gtts(text: str, output_path: str) -> bool:
    """Generate a fake audio sample using Google TTS."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(output_path)
        return True
    except Exception as e:
        print(f"  [gTTS] Failed: {e}")
        return False


def generate_fake_with_xtts(text: str, speaker_wav: str, output_path: str) -> bool:
    """
    Generate a cloned voice using Coqui XTTS-v2.
    Requires: pip install TTS
    """
    try:
        from TTS.api import TTS
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=torch.cuda.is_available())
        tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language="en",
            file_path=output_path,
        )
        return True
    except Exception as e:
        print(f"  [XTTS] Failed: {e}")
        return False


def build_dataset(
    real_audio_dir: str,
    output_dir: str,
    num_fake_per_real: int = 2,
    use_xtts: bool = True,
    texts_for_tts: List[str] = None,
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
        texts_for_tts = [
            "Hello, this is your bank calling about your account.",
            "Please share your OTP for verification purposes.",
            "Your account has been compromised, transfer funds immediately.",
            "This is the police, you are under digital arrest.",
            "Please confirm your identity by providing your Aadhaar number.",
            "Your credit card has been blocked due to suspicious activity.",
            "We need to verify your account, please stay on the line.",
            "This call is being recorded for quality assurance.",
            "Your loan application has been approved, please confirm.",
            "There is a warrant issued in your name, cooperate now.",
        ]

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
            success = generate_fake_with_xtts(text, ref_file, raw_path)
            generator = "xtts_v2"
        
        if not success:
            success = generate_fake_with_gtts(text, raw_path)
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

    # Save manifest
    manifest_path = output / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n=== Dataset Complete ===")
    print(f"  Real samples: {sum(1 for m in manifest if m['label'] == 0)}")
    print(f"  Fake samples: {sum(1 for m in manifest if m['label'] == 1)}")
    print(f"  Manifest: {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build VoiceShield training dataset")
    parser.add_argument("--real_dir", type=str, required=True, help="Directory of real audio files")
    parser.add_argument("--output_dir", type=str, default="./data", help="Output directory")
    parser.add_argument("--num_fake", type=int, default=2, help="Fake samples per real sample")
    parser.add_argument("--no_xtts", action="store_true", help="Disable XTTS (gTTS only)")
    args = parser.parse_args()

    build_dataset(
        real_audio_dir=args.real_dir,
        output_dir=args.output_dir,
        num_fake_per_real=args.num_fake,
        use_xtts=not args.no_xtts,
    )
