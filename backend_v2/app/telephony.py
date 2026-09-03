"""
Telephony Simulator — degrades clean audio to match real PSTN/VoIP conditions.

Pipeline:
  raw PCM (any rate) → 8 kHz downsample → μ-law encode/decode → additive noise
  → 16 kHz upsample (for wav2vec2 feature extractor)

All processing is synchronous and runs in the ThreadPoolExecutor via the VAD
pipeline, never on the async event loop.
"""
import logging

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)

# Typical PSTN band-pass: 300 Hz – 3400 Hz (G.711 specification)
PSTN_LOW_HZ = 300
PSTN_HIGH_HZ = 3_400
TELEPHONY_SR = 8_000       # 8 kHz intermediate
TARGET_SR = 16_000         # wav2vec2 expects 16 kHz
NOISE_AMPLITUDE = 0.005    # background noise level (−46 dBFS roughly)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """High-quality polyphase resampling."""
    if orig_sr == target_sr:
        return audio
    ratio = target_sr / orig_sr
    out_len = int(len(audio) * ratio)
    return signal.resample_poly(audio, target_sr, orig_sr, padtype="line").astype(np.float32)[:out_len]


def _bandpass(audio: np.ndarray, sr: int, low: float, high: float) -> np.ndarray:
    """Apply a 5th-order Butterworth band-pass filter."""
    nyq = sr / 2.0
    sos = signal.butter(
        5,
        [low / nyq, high / nyq],
        btype="band",
        output="sos",
    )
    return signal.sosfilt(sos, audio).astype(np.float32)


def _ulaw_encode_decode(audio: np.ndarray) -> np.ndarray:
    """
    Simulate μ-law (G.711) codec distortion.
    Encode to 8-bit μ-law then immediately decode back to float32 — this
    introduces the quantisation noise characteristic of telephony.
    """
    # μ-law companding (ITU-T G.711)
    MU = 255.0
    clipped = np.clip(audio, -1.0, 1.0)
    encoded = np.sign(clipped) * np.log1p(MU * np.abs(clipped)) / np.log1p(MU)
    # Quantise to 8 bits (clip to prevent integer overflow wraparound +128 -> -128)
    quantised = np.clip(np.round(encoded * 128), -128, 127).astype(np.int8).astype(np.float32) / 128.0
    # Decode
    decoded = np.sign(quantised) * (np.expm1(np.abs(quantised) * np.log1p(MU))) / MU
    return decoded.astype(np.float32)


def _add_background_noise(audio: np.ndarray, amplitude: float = NOISE_AMPLITUDE) -> np.ndarray:
    """Add white Gaussian noise to simulate line noise."""
    noise = np.random.randn(len(audio)).astype(np.float32) * amplitude
    return np.clip(audio + noise, -1.0, 1.0).astype(np.float32)


def simulate_telephony(
    audio: np.ndarray,
    input_sr: int = TARGET_SR,
    add_noise: bool = True,
) -> np.ndarray:
    """
    Full telephony simulation pipeline.

    Args:
        audio:    float32 mono PCM at `input_sr` Hz, normalised to [-1, 1]
        input_sr: sample rate of `audio`
        add_noise: whether to inject background noise

    Returns:
        float32 mono PCM at 16 kHz, telephony-degraded
    """
    # 1. Downsample to 8 kHz
    audio_8k = _resample(audio, input_sr, TELEPHONY_SR)

    # 2. Band-pass to PSTN range (300–3400 Hz)
    audio_bp = _bandpass(audio_8k, TELEPHONY_SR, PSTN_LOW_HZ, PSTN_HIGH_HZ)

    # 3. μ-law codec quantisation
    audio_ulaw = _ulaw_encode_decode(audio_bp)

    # 4. Background noise
    if add_noise:
        audio_ulaw = _add_background_noise(audio_ulaw)

    # 5. Upsample back to 16 kHz for the feature extractor
    audio_16k = _resample(audio_ulaw, TELEPHONY_SR, TARGET_SR)

    return audio_16k
