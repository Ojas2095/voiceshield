"""
VoiceShield — Audio Preprocessing Module
Handles: resampling to 8kHz, VAD gating, 2-second windowing, mel-spectrogram generation.
"""
import torch
import torchaudio
import numpy as np


def resample_to_8khz(waveform: torch.Tensor, orig_sr: int) -> torch.Tensor:
    """Resample audio to 8kHz to simulate telephony conditions."""
    if orig_sr == 8000:
        return waveform
    resampler = torchaudio.transforms.Resample(orig_freq=orig_sr, new_freq=8000)
    return resampler(waveform)


def pad_or_trim(waveform: torch.Tensor, target_length: int = 16000) -> torch.Tensor:
    """Pad or trim waveform to exactly `target_length` samples (2s at 8kHz = 16000)."""
    length = waveform.shape[-1]
    if length >= target_length:
        return waveform[..., :target_length]
    padding = target_length - length
    return torch.nn.functional.pad(waveform, (0, padding))


def generate_mel_spectrogram(waveform: torch.Tensor, sr: int = 8000) -> torch.Tensor:
    """Convert a waveform to a Mel spectrogram tensor."""
    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=sr,
        n_fft=512,
        hop_length=160,
        n_mels=80,
    )
    mel = mel_transform(waveform)
    # Log scale
    mel = torch.log(mel + 1e-9)
    return mel


def preprocess_chunk(raw_pcm_bytes: bytes, source_sr: int = 16000) -> dict:
    """
    Full preprocessing pipeline for one audio chunk.
    Returns dict with 'waveform_8k' and 'mel_spectrogram' ready for inference.
    """
    # Convert raw PCM Int16 bytes to tensor
    audio_np = np.frombuffer(raw_pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    waveform = torch.from_numpy(audio_np).unsqueeze(0)  # (1, samples)
    
    # Resample to 8kHz
    waveform_8k = resample_to_8khz(waveform, source_sr)
    
    # Pad/trim to exactly 2 seconds
    waveform_8k = pad_or_trim(waveform_8k, target_length=16000)
    
    # Generate mel spectrogram
    mel = generate_mel_spectrogram(waveform_8k)
    
    return {
        "waveform_8k": waveform_8k,
        "mel_spectrogram": mel,
    }
