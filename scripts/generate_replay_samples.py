"""
Generate 4 self-contained 16kHz WAV demo samples for the Replay Lab:
- frontend/public/demo/real_en.wav
- frontend/public/demo/cloned_en.wav
- frontend/public/demo/real_hi.wav
- frontend/public/demo/cloned_hi.wav
"""
import sys
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from ai.train.synthetic_seed import (
    generate_human_like_audio,
    generate_ai_fake_like_audio,
    apply_telephony_degradation,
)

def generate_samples():
    out_dir = repo_root / "frontend" / "public" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    sr = 16000

    # 1. Real English (human harmonic speech)
    real_en = apply_telephony_degradation(generate_human_like_audio(duration=4.5), sr)
    wav_en_int16 = (real_en.squeeze().numpy() * 32767).astype(np.int16)
    wavfile.write(str(out_dir / "real_en.wav"), sr, wav_en_int16)
    print(f"[OK] Generated: {out_dir / 'real_en.wav'}")

    # 2. Cloned English (synthetic vocoder buzz + phase jitter)
    cloned_en = apply_telephony_degradation(generate_ai_fake_like_audio(duration=4.5), sr)
    cloned_en_int16 = (cloned_en.squeeze().numpy() * 32767).astype(np.int16)
    wavfile.write(str(out_dir / "cloned_en.wav"), sr, cloned_en_int16)
    print(f"[OK] Generated: {out_dir / 'cloned_en.wav'}")

    # 3. Real Hindi
    real_hi = apply_telephony_degradation(generate_human_like_audio(duration=4.5), sr)
    wav_hi_int16 = (real_hi.squeeze().numpy() * 32767).astype(np.int16)
    wavfile.write(str(out_dir / "real_hi.wav"), sr, wav_hi_int16)
    print(f"[OK] Generated: {out_dir / 'real_hi.wav'}")

    # 4. Cloned Hindi
    cloned_hi = apply_telephony_degradation(generate_ai_fake_like_audio(duration=4.5), sr)
    cloned_hi_int16 = (cloned_hi.squeeze().numpy() * 32767).astype(np.int16)
    wavfile.write(str(out_dir / "cloned_hi.wav"), sr, cloned_hi_int16)
    print(f"[OK] Generated: {out_dir / 'cloned_hi.wav'}")

    print("\nAll 4 Replay Lab demo vectors are populated and ready!")

if __name__ == "__main__":
    generate_samples()
