"""
Tests for the telephony simulation pipeline.
No audio files needed — uses synthetic signals.
"""
import numpy as np
import pytest

from app.telephony import simulate_telephony, _ulaw_encode_decode, _bandpass, TARGET_SR


def sine_wave(freq: float = 440.0, sr: int = 16_000, duration: float = 2.0) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


class TestTelephonyPipeline:
    def test_output_shape(self):
        audio = sine_wave()
        out = simulate_telephony(audio, input_sr=TARGET_SR)
        # Allow ±1% length deviation from resampling
        assert abs(len(out) - len(audio)) / len(audio) < 0.02

    def test_output_dtype(self):
        audio = sine_wave()
        out = simulate_telephony(audio)
        assert out.dtype == np.float32

    def test_output_clipped(self):
        """Output must be in [-1, 1] after telephony processing."""
        audio = sine_wave() * 0.9
        out = simulate_telephony(audio)
        assert float(np.max(np.abs(out))) <= 1.0

    def test_silence_stays_silent(self):
        """Zero input should produce near-zero output (only noise is added)."""
        silence = np.zeros(32_000, dtype=np.float32)
        out = simulate_telephony(silence, add_noise=False)
        rms = float(np.sqrt(np.mean(out ** 2)))
        assert rms < 0.05

    def test_ulaw_introduces_distortion(self):
        """μ-law round-trip should differ from the original (quantisation noise)."""
        signal = sine_wave(freq=1000.0)
        decoded = _ulaw_encode_decode(signal)
        assert not np.allclose(signal, decoded, atol=1e-4)

    def test_bandpass_attenuates_outside_pstn(self):
        """
        A 3800 Hz sine (above 3400 Hz PSTN cutoff, below Nyquist @ 8kHz)
        should be noticeably attenuated by the band-pass filter.
        Note: a 5th-order Butterworth won't give 80 dB rejection right at the
        cutoff — expect meaningful but not extreme attenuation in the transition band.
        """
        high_freq = sine_wave(freq=3_800.0, sr=8_000)
        filtered = _bandpass(high_freq, sr=8_000, low=300, high=3_400)
        original_rms = float(np.sqrt(np.mean(high_freq ** 2)))
        filtered_rms = float(np.sqrt(np.mean(filtered ** 2)))
        # At least 30% energy reduction — transition band of a 5th-order filter
        assert filtered_rms < original_rms * 0.70


class TestTelephonyNoNoise:
    def test_no_noise_flag(self):
        audio = np.zeros(32_000, dtype=np.float32)
        out = simulate_telephony(audio, add_noise=False)
        assert float(np.max(np.abs(out))) < 0.001
