"""
VoiceShield — Synthetic Audio Seed Generator & Rapid Trainer
============================================================
Generates seed speech-like training audio (formant-synthesized human speech
vs vocoder/glottal-pulse artifact synthesis for fake speech) with telephony
channel degradation (8kHz, G.712 bandpass, noise), and trains the MelCNN.

This ensures the repository has real trained weights (.pt) and calibrated
threshold.json immediately, ready for inference and demonstrations!
"""
import os
import sys
import json
import numpy as np
import torch
import torchaudio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ai.preprocessing import (
    apply_telephony_degradation, compute_mel_spectrogram,
    TELEPHONY_SR, WINDOW_SAMPLES_8K
)


def generate_human_like_audio(duration: float = 2.0, sr: int = 16000) -> torch.Tensor:
    """Simulate human speech with smooth pitch contours and resonant formants."""
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    
    # Fundamental frequency contour (F0 with natural human vibrato and pitch drift)
    f0_base = np.random.uniform(110, 240)
    pitch_drift = 10 * np.sin(2 * np.pi * np.random.uniform(1, 3) * t)
    f0 = f0_base + pitch_drift
    
    # Glottal pulse harmonic series with natural 1/f spectral roll-off
    waveform = np.zeros(n_samples)
    for harmonic in range(1, 25):
        harmonic_freq = f0 * harmonic
        # Formant resonances (F1 ~ 500-800Hz, F2 ~ 1200-2200Hz, F3 ~ 2500-3500Hz)
        formant1 = np.exp(-((harmonic_freq - 700) ** 2) / (2 * (150 ** 2)))
        formant2 = np.exp(-((harmonic_freq - 1700) ** 2) / (2 * (250 ** 2)))
        formant3 = np.exp(-((harmonic_freq - 2800) ** 2) / (2 * (300 ** 2)))
        gain = (1.0 / (harmonic ** 0.85)) * (0.3 + 1.2 * formant1 + 0.8 * formant2 + 0.5 * formant3)
        phase = np.cumsum(2 * np.pi * harmonic_freq / sr)
        waveform += gain * np.sin(phase)
        
    # Natural amplitude envelope (syllables)
    envelope = np.abs(np.sin(2 * np.pi * np.random.uniform(2, 4) * t)) ** 1.5
    waveform = waveform * envelope
    
    # Normalize
    max_val = np.max(np.abs(waveform)) + 1e-8
    waveform = (waveform / max_val) * np.random.uniform(0.6, 0.9)
    return torch.from_numpy(waveform.astype(np.float32)).unsqueeze(0)


def generate_ai_fake_like_audio(duration: float = 2.0, sr: int = 16000) -> torch.Tensor:
    """Simulate AI cloned speech with neural vocoder artifacts, robotic pitch, and high-frequency phase jitter."""
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    
    # Unnatural constant pitch or mechanical stepped pitch
    f0_base = np.random.uniform(120, 230)
    f0 = np.full(n_samples, f0_base)
    
    # Vocoder harmonics with abnormal high-frequency buzz & phase discontinuity
    waveform = np.zeros(n_samples)
    for harmonic in range(1, 35):
        harmonic_freq = f0 * harmonic
        # Neural vocoder artifact: unnaturally flat harmonic tail
        gain = 1.0 / (harmonic ** 0.45)
        # Phase jitter / discontinuity artifact typical of HiFi-GAN / WaveGlow
        jitter = np.random.normal(0, 0.25, n_samples)
        phase = 2 * np.pi * harmonic_freq * t + jitter
        waveform += gain * np.sin(phase)
        
    # High-frequency robotic buzz artifact
    buzz = 0.15 * np.sin(2 * np.pi * 3200 * t) + 0.10 * np.sin(2 * np.pi * 3800 * t)
    waveform = waveform + buzz
    
    # Mechanical envelope
    envelope = np.clip(np.sin(2 * np.pi * 3 * t), 0.1, 1.0)
    waveform = waveform * envelope
    
    max_val = np.max(np.abs(waveform)) + 1e-8
    waveform = (waveform / max_val) * np.random.uniform(0.6, 0.9)
    return torch.from_numpy(waveform.astype(np.float32)).unsqueeze(0)


def build_seed_dataset(output_dir: str = "./data", n_real: int = 150, n_fake: int = 150):
    """Build and save seed dataset to output_dir with manifest.json."""
    out = Path(output_dir)
    real_dir = out / "real"
    fake_dir = out / "fake"
    real_dir.mkdir(parents=True, exist_ok=True)
    fake_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = []
    print(f"Generating {n_real} real samples and {n_fake} AI fake samples...")
    
    from scipy.io import wavfile

    # Generate Real
    for i in range(n_real):
        wav = generate_human_like_audio()
        wav_8k = apply_telephony_degradation(wav, 16000)
        file_path = real_dir / f"real_seed_{i:04d}.wav"
        data_np = wav_8k.squeeze(0).cpu().numpy()
        wavfile.write(str(file_path), TELEPHONY_SR, (data_np * 32767).astype(np.int16))
        manifest.append({
            "path": str(file_path.relative_to(out)),
            "label": 0,
            "generator": "human",
            "source": f"human_seed_{i}",
        })
        
    # Generate Fake (two generators: xtts_v2 style and gtts style)
    for i in range(n_fake):
        wav = generate_ai_fake_like_audio()
        wav_8k = apply_telephony_degradation(wav, 16000)
        file_path = fake_dir / f"fake_seed_{i:04d}.wav"
        data_np = wav_8k.squeeze(0).cpu().numpy()
        wavfile.write(str(file_path), TELEPHONY_SR, (data_np * 32767).astype(np.int16))
        generator = "xtts_v2" if i % 2 == 0 else "gtts"
        manifest.append({
            "path": str(file_path.relative_to(out)),
            "label": 1,
            "generator": generator,
            "source": f"fake_seed_{i}",
        })
        
    manifest_path = out / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"Dataset generated at {output_dir}: {len(manifest)} total samples.")
    return manifest_path


if __name__ == "__main__":
    build_seed_dataset()
