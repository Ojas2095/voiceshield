"""
Prepare demo audio for VoiceShield's Replay Demo Call.

Converts your recorded REAL clips to 16 kHz mono and generates AI-CLONED
counterparts with Coqui XTTS, writing the four files the frontend expects:

    frontend/public/demo/real_en.wav
    frontend/public/demo/cloned_en.wav
    frontend/public/demo/real_hi.wav
    frontend/public/demo/cloned_hi.wav

Usage:
    python scripts/prepare_demo_audio.py \
        --real_en path/to/real_english.wav \
        --real_hi path/to/real_hindi.wav \
        --out frontend/public/demo

Requirements (on a machine with the ML env):
    pip install TTS torchaudio soundfile
XTTS runs much faster on a GPU but works on CPU.

These are REAL audio files fed through the real pipeline — not scripted results.
"""
import argparse
from pathlib import Path

TARGET_SR = 16000

CLONE_TEXT = {
    "en": "Hello, this is an urgent call from your bank. Your account has been "
          "compromised. Please confirm your one time password immediately.",
    "hi": "नमस्ते, मैं आपके बैंक से बोल रहा हूँ। आपका खाता असुरक्षित है, "
          "कृपया तुरंत अपना ओटीपी बताइए।",
}


def to_16k_mono(src: str, dst: Path) -> None:
    import torchaudio
    wav, sr = torchaudio.load(src)
    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)
    if sr != TARGET_SR:
        wav = torchaudio.transforms.Resample(sr, TARGET_SR)(wav)
    dst.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(dst), wav, TARGET_SR)
    print(f"[real ] {src} -> {dst}")


def clone(ref: str, text: str, lang: str, dst: Path) -> None:
    import torch
    from TTS.api import TTS
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=torch.cuda.is_available())
    tmp = dst.with_suffix(".raw.wav")
    tts.tts_to_file(text=text, speaker_wav=ref, language=lang, file_path=str(tmp))
    to_16k_mono(str(tmp), dst)
    tmp.unlink(missing_ok=True)
    print(f"[clone] xtts({lang}) -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real_en", required=True, help="Your consented English recording")
    ap.add_argument("--real_hi", required=True, help="Your consented Hindi recording")
    ap.add_argument("--out", default="frontend/public/demo", help="Output dir")
    ap.add_argument("--no_clone", action="store_true", help="Only convert reals (skip XTTS)")
    args = ap.parse_args()

    out = Path(args.out)
    to_16k_mono(args.real_en, out / "real_en.wav")
    to_16k_mono(args.real_hi, out / "real_hi.wav")

    if not args.no_clone:
        clone(args.real_en, CLONE_TEXT["en"], "en", out / "cloned_en.wav")
        clone(args.real_hi, CLONE_TEXT["hi"], "hi", out / "cloned_hi.wav")

    print("\nDone. Files in", out)


if __name__ == "__main__":
    main()
