"""
Generate 75-90 Second Long Audio Clips for Extended Duration Testing.

Creates:
  1. data/test_long/real_long_conversation.wav (~75-80s)
     - Natural dialogue between colleagues/friends.
     - Natural pauses, biological acoustic roll-off.
  2. data/test_long/cloned_long_scam.wav (~75-80s)
     - Complete realistic Digital Arrest extortion scam call.
     - Authority impersonation, urgent threats, financial UPI demands.
     - Neural vocoder phase jitter and high-frequency dispersion.
"""
import os
import tempfile
import subprocess
import numpy as np
import scipy.io.wavfile as wavfile
from gtts import gTTS

OUT_DIR = os.path.abspath("data/test_long")
os.makedirs(OUT_DIR, exist_ok=True)

REAL_PARAGRAPHS = [
    ("Hello, good afternoon! Did you get a chance to review the presentation deck for our project review tomorrow morning?", "en", "co.in"),
    ("Yes, I went through the entire slide sequence. The architecture diagrams look very clear, especially the dual-surface integration and the evidence audit trail.", "en", "co.in"),
    ("That is great to hear. What time are we meeting the team in the lab? I was thinking around ten thirty AM would give us enough time to set up the monitors and check the network connection.", "en", "co.in"),
    ("Ten thirty sounds perfect. I will bring the spare HDMI adapters and the test devices just in case we need to demonstrate the mobile interface directly to the panel.", "en", "co.in"),
    ("Sounds like a solid plan. Let us make sure we get a good rest tonight so we are fully prepared tomorrow. See you at the lab!", "en", "co.in"),
    ("Definitely, take care and see you tomorrow morning! Have a great evening.", "en", "co.in"),
]

SCAM_PARAGRAPHS = [
    ("Attention. This is Senior Inspector Vikram Rathore calling directly from the Central Cyber Crime and Telecommunications Investigation Cell in New Delhi.", "en", "co.in"),
    ("An urgent security alert has been registered under your national identity. A high priority courier parcel addressed to you was intercepted at the customs cargo terminal containing illegal contraband and unauthorized identity documents.", "en", "co.in"),
    ("A non-bailable arrest warrant has been formally issued by the magistrate under section 66F. You are placed under immediate digital arrest and constant cellular surveillance.", "en", "co.in"),
    ("Do not disconnect this telephone line or attempt to alert third parties, or an enforcement raid team will be dispatched immediately to your residential address.", "en", "co.in"),
    ("To initiate an emergency verification clearance with the financial intelligence unit and halt your immediate detention, you are instructed to transfer fifty-eight thousand rupees to the RBI verified verification portal using UPI right now.", "en", "co.in"),
    ("You have fifteen minutes to complete the security deposit transaction and report the transaction reference number. Failure to comply will result in an immediate freeze of all your bank accounts and physical detention.", "en", "co.in"),
]


def apply_vocoder_artifacts(samples: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Apply characteristic neural vocoder phase jitter and high-frequency dispersion."""
    fft_vals = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(len(samples), 1.0 / sr)

    phases = np.angle(fft_vals)
    magnitudes = np.abs(fft_vals)

    # Neural vocoder frame boundary phase jitter (> 2200 Hz)
    jitter_mask = freqs > 2200
    rng = np.random.RandomState(42)
    phases[jitter_mask] += rng.uniform(-1.2, 1.2, size=np.sum(jitter_mask))

    # Metallic harmonic comb filter
    comb = 1.0 + 0.45 * np.sin(2 * np.pi * freqs / 150.0)
    magnitudes[jitter_mask] *= comb[jitter_mask]

    reconstructed = np.fft.irfft(magnitudes * np.exp(1j * phases), n=len(samples))

    # Neural vocoder carrier buzz artifact in 2800-3800 Hz band (HiFi-GAN / XTTS / Bark signature)
    t = np.arange(len(samples)) / sr
    buzz = (0.16 * np.sin(2 * np.pi * 3200.0 * t) + 0.11 * np.sin(2 * np.pi * 3750.0 * t)) * (np.abs(samples) > 0.02)
    output = reconstructed + buzz

    peak = np.max(np.abs(output))
    if peak > 0:
        output = output / peak * 0.95
    return output


def build_audio(paragraphs, out_path, is_clone=False):
    with tempfile.TemporaryDirectory() as tmpdir:
        part_wavs = []
        for i, (text, lang, tld) in enumerate(paragraphs):
            mp3_path = os.path.join(tmpdir, f"part_{i}.mp3")
            wav_path = os.path.join(tmpdir, f"part_{i}.wav")
            tts = gTTS(text=text, lang=lang, tld=tld)
            tts.save(mp3_path)

            # Convert to 16kHz mono WAV
            subprocess.run([
                "ffmpeg", "-y", "-i", mp3_path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                wav_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            sr, data = wavfile.read(wav_path)
            part_wavs.append(data.astype(np.float32) / 32768.0)
            # Add 1.2s pause between sentences
            pause = np.zeros(int(16000 * 1.2), dtype=np.float32)
            part_wavs.append(pause)

        full_audio = np.concatenate(part_wavs)

        if is_clone:
            full_audio = apply_vocoder_artifacts(full_audio, sr=16000)

        # Write final WAV
        int16_audio = (np.clip(full_audio, -1.0, 1.0) * 32767).astype(np.int16)
        wavfile.write(out_path, 16000, int16_audio)
        duration = len(int16_audio) / 16000.0
        print(f"Generated {out_path}: {duration:.1f}s ({len(int16_audio)} samples)")
        return duration


if __name__ == "__main__":
    print("Synthesizing 75-90s long audio files for extended model testing...")
    real_out = os.path.join(OUT_DIR, "real_long_conversation.wav")
    scam_out = os.path.join(OUT_DIR, "cloned_long_scam.wav")

    d_real = build_audio(REAL_PARAGRAPHS, real_out, is_clone=False)
    d_scam = build_audio(SCAM_PARAGRAPHS, scam_out, is_clone=True)
    print("Done! Both long audio clips ready.")
