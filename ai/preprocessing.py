"""
VoiceShield — Audio Preprocessing Module (Production)
=====================================================
Handles the full telephony-robust audio pipeline:
  Raw PCM → Resample to 16kHz → Telephony Degradation (8kHz + codec + noise)
  → VAD gating → 2-second windowing → Mel-spectrogram generation

All operations are pure NumPy/PyTorch with no blocking I/O.
"""
import io
import torch
import torchaudio
import numpy as np
from dataclasses import dataclass
from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────
TELEPHONY_SR = 8000          # Standard telephony sample rate
MODEL_SR = 16000             # wav2vec2 expects 16kHz
WINDOW_SECONDS = 2.0         # Analysis window length
WINDOW_SAMPLES_8K = int(TELEPHONY_SR * WINDOW_SECONDS)   # 16000 samples at 8kHz
WINDOW_SAMPLES_16K = int(MODEL_SR * WINDOW_SECONDS)       # 32000 samples at 16kHz

# Mel-spectrogram config
N_FFT = 512
HOP_LENGTH = 160
N_MELS = 80


@dataclass
class ProcessedChunk:
    """Output of the preprocessing pipeline for one 2-second window."""
    waveform_8k: torch.Tensor       # (1, 16000) — telephony-degraded
    waveform_16k: torch.Tensor      # (1, 32000) — upsampled for wav2vec2
    mel_spectrogram: torch.Tensor   # (1, 80, T) — log-mel for CNN branch
    energy: float                   # RMS energy (for VAD gating)
    is_speech: bool                 # Whether this chunk contains speech


# ──────────────────────────────────────────────────────────────────────
# Core Functions
# ──────────────────────────────────────────────────────────────────────

def pcm_bytes_to_tensor(raw_pcm: bytes, source_sr: int = 16000) -> torch.Tensor:
    """
    Convert raw PCM Int16 bytes to a float32 torch tensor.
    Returns: (1, num_samples) tensor normalized to [-1, 1].
    """
    audio_np = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return torch.from_numpy(audio_np).unsqueeze(0)


def resample(waveform: torch.Tensor, orig_sr: int, target_sr: int) -> torch.Tensor:
    """Resample audio to a target sample rate."""
    if orig_sr == target_sr:
        return waveform
    resampler = torchaudio.transforms.Resample(orig_freq=orig_sr, new_freq=target_sr)
    return resampler(waveform)


def apply_telephony_degradation(waveform: torch.Tensor, sr: int = 16000) -> torch.Tensor:
    """
    Simulate real-world telephony channel degradation:
      1. Downsample to 8kHz
      2. Bandpass filter 300Hz–3400Hz (ITU-T G.712 telephone band)
      3. Add additive Gaussian noise at ~15dB SNR
    Returns: (1, samples) tensor at 8kHz sample rate.
    """
    # Step 1: Downsample to 8kHz
    waveform_8k = resample(waveform, sr, TELEPHONY_SR)

    # Step 2: Bandpass filter (300Hz – 3400Hz)
    # High-pass at 300Hz
    waveform_8k = torchaudio.functional.highpass_biquad(waveform_8k, TELEPHONY_SR, 300.0)
    # Low-pass at 3400Hz
    waveform_8k = torchaudio.functional.lowpass_biquad(waveform_8k, TELEPHONY_SR, 3400.0)

    # Step 3: Add noise at ~15dB SNR
    signal_power = waveform_8k.pow(2).mean()
    if signal_power > 1e-10:  # avoid division by zero on silence
        snr_db = 15.0
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = torch.randn_like(waveform_8k) * torch.sqrt(noise_power)
        waveform_8k = waveform_8k + noise

    return waveform_8k


def pad_or_trim(waveform: torch.Tensor, target_length: int) -> torch.Tensor:
    """Pad (with zeros) or trim waveform to exactly `target_length` samples."""
    length = waveform.shape[-1]
    if length >= target_length:
        return waveform[..., :target_length]
    padding = target_length - length
    return torch.nn.functional.pad(waveform, (0, padding))


def compute_rms_energy(waveform: torch.Tensor) -> float:
    """Compute RMS energy of a waveform. Used for simple VAD gating."""
    return float(waveform.pow(2).mean().sqrt())


def simple_vad(waveform: torch.Tensor, threshold: float = 0.005) -> bool:
    """
    Simple energy-based Voice Activity Detection.
    Returns True if the chunk likely contains speech.
    """
    return compute_rms_energy(waveform) > threshold


def compute_mel_spectrogram(waveform: torch.Tensor, sr: int = TELEPHONY_SR) -> torch.Tensor:
    """
    Compute a log-scaled Mel spectrogram from a waveform.
    Returns: (1, n_mels, time_frames) tensor.
    """
    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=sr,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
        n_mels=N_MELS,
    )
    mel = mel_transform(waveform)
    # Log scale for numerical stability
    mel = torch.log(mel + 1e-9)
    return mel


# ──────────────────────────────────────────────────────────────────────
# Main Pipeline
# ──────────────────────────────────────────────────────────────────────

def preprocess_chunk(
    raw_pcm: bytes,
    source_sr: int = 16000,
    apply_degradation: bool = True,
    vad_threshold: float = 0.005,
) -> ProcessedChunk:
    """
    Full preprocessing pipeline for one raw audio chunk.

    Pipeline:
      1. PCM bytes → float tensor
      2. (Optional) Apply telephony degradation (8kHz + bandpass + noise)
      3. Pad/trim to exactly 2 seconds
      4. Compute mel-spectrogram (for CNN branch)
      5. Upsample to 16kHz (for wav2vec2 branch)
      6. VAD energy check

    Args:
        raw_pcm: Raw PCM Int16 bytes from the WebSocket
        source_sr: Original sample rate of the incoming audio
        apply_degradation: Whether to simulate telephony channel
        vad_threshold: RMS energy threshold for speech detection

    Returns:
        ProcessedChunk with all tensors ready for dual-branch inference.
    """
    # 1. Convert bytes to tensor
    waveform = pcm_bytes_to_tensor(raw_pcm, source_sr)

    # 2. Telephony degradation
    if apply_degradation:
        waveform_8k = apply_telephony_degradation(waveform, source_sr)
    else:
        waveform_8k = resample(waveform, source_sr, TELEPHONY_SR)

    # 3. Pad/trim to exactly 2 seconds at 8kHz
    waveform_8k = pad_or_trim(waveform_8k, WINDOW_SAMPLES_8K)

    # 4. Compute mel-spectrogram at 8kHz
    mel = compute_mel_spectrogram(waveform_8k, sr=TELEPHONY_SR)

    # 5. Upsample to 16kHz for wav2vec2 (it requires 16kHz input)
    waveform_16k = resample(waveform_8k, TELEPHONY_SR, MODEL_SR)
    waveform_16k = pad_or_trim(waveform_16k, WINDOW_SAMPLES_16K)

    # 6. VAD check
    energy = compute_rms_energy(waveform_8k)
    is_speech = energy > vad_threshold

    return ProcessedChunk(
        waveform_8k=waveform_8k,
        waveform_16k=waveform_16k,
        mel_spectrogram=mel,
        energy=energy,
        is_speech=is_speech,
    )


def preprocess_tensor(
    waveform: torch.Tensor,
    source_sr: int = 16000,
    apply_degradation: bool = False,
) -> ProcessedChunk:
    """
    Preprocess an already-loaded waveform tensor (for training / offline evaluation).
    Same pipeline as preprocess_chunk but skips the PCM byte conversion.
    """
    if apply_degradation:
        waveform_8k = apply_telephony_degradation(waveform, source_sr)
    else:
        waveform_8k = resample(waveform, source_sr, TELEPHONY_SR)

    waveform_8k = pad_or_trim(waveform_8k, WINDOW_SAMPLES_8K)
    mel = compute_mel_spectrogram(waveform_8k, sr=TELEPHONY_SR)
    waveform_16k = resample(waveform_8k, TELEPHONY_SR, MODEL_SR)
    waveform_16k = pad_or_trim(waveform_16k, WINDOW_SAMPLES_16K)
    energy = compute_rms_energy(waveform_8k)

    return ProcessedChunk(
        waveform_8k=waveform_8k,
        waveform_16k=waveform_16k,
        mel_spectrogram=mel,
        energy=energy,
        is_speech=energy > 0.005,
    )
