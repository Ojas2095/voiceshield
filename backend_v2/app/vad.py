"""
VAD (Voice Activity Detection) + Sliding Window Buffer.

Uses Silero VAD (loaded via torch.hub) to gate which 2-second windows
actually reach the inference pipeline — silence is cheap to skip.

Design:
  - RingBuffer accumulates raw 20ms PCM frames at 16 kHz
  - Every `hop_ms` a new 2s window is extracted
  - Silero VAD runs on the window; if speech-active the window goes to inference
  - VADPipeline.process() is synchronous — called from the WS handler inside
    the ThreadPoolExecutor just like inference

Silero VAD citation:
  Silero Team (2021). Silero VAD: pre-trained enterprise-grade Voice Activity
  Detector (VAD), Number Detector and Language Classifier.
  https://github.com/snakers4/silero-vad
"""
import logging
from collections import deque

import numpy as np

from app.config import get_settings
from app.telephony import simulate_telephony

logger = logging.getLogger(__name__)
settings = get_settings()


class RingBuffer:
    """Thread-safe ring buffer that accumulates float32 PCM samples."""

    def __init__(self, max_samples: int) -> None:
        self._buf: deque[float] = deque(maxlen=max_samples)

    def push(self, samples: np.ndarray) -> None:
        self._buf.extend(samples.tolist())

    def as_array(self) -> np.ndarray:
        return np.array(self._buf, dtype=np.float32)

    def __len__(self) -> int:
        return len(self._buf)


class SileroVAD:
    """
    Lazy-loaded Silero VAD wrapper.
    Falls back to an energy-based heuristic if torch.hub is unavailable
    (no-internet venue, etc.) so the pipeline never hard-fails.
    """

    _model = None
    _utils = None
    _loaded: bool = False

    def load(self) -> None:
        try:
            import torch

            self._model, self._utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self._loaded = True
            logger.info("Silero VAD loaded from torch.hub")
        except Exception as exc:
            logger.warning("Silero VAD unavailable (%s) — using energy fallback", exc)
            self._loaded = False

    def is_speech(self, window: np.ndarray, sr: int = 16_000, threshold: float = 0.5) -> bool:
        """Returns True if the window contains speech."""
        if not self._loaded or self._model is None:
            return self._energy_fallback(window)
        try:
            import torch

            with torch.no_grad():
                tensor = torch.tensor(window).unsqueeze(0)
                confidence: float = self._model(tensor, sr).item()
            return confidence >= threshold
        except Exception:
            return self._energy_fallback(window)

    @staticmethod
    def _energy_fallback(window: np.ndarray, threshold: float = 0.01) -> bool:
        """RMS energy heuristic — crude but robust."""
        if window.size == 0:
            return False
        rms = float(np.sqrt(np.mean(window ** 2)))
        return rms > threshold


_silero_vad: SileroVAD | None = None


def get_vad() -> SileroVAD:
    global _silero_vad
    if _silero_vad is None:
        _silero_vad = SileroVAD()
        _silero_vad.load()
    return _silero_vad


class VADPipeline:
    """
    Accumulates raw PCM frames and emits (window, is_speech) pairs every hop.

    Usage inside the WebSocket handler:
        pipeline = VADPipeline(call_id)
        for frame_bytes in frames:
            for window, is_speech in pipeline.push(frame_bytes):
                if is_speech:
                    score = await inference.classifier.infer(window)
    """

    def __init__(self, call_id: str) -> None:
        self.call_id = call_id
        sr = settings.sample_rate
        self._window_samples = int(sr * settings.window_duration_ms / 1_000)
        self._hop_samples = int(sr * settings.hop_duration_ms / 1_000)
        self._buf = RingBuffer(self._window_samples * 4)
        self._samples_since_last_hop: int = 0
        self._elapsed_samples: int = 0
        self._vad = get_vad()

    def push(
        self, raw_bytes: bytes, bytes_per_sample: int = 2
    ) -> list[tuple[np.ndarray, bool, int, int]]:
        """
        Accepts a raw binary frame (int16 PCM at client sample rate, 20ms).
        Returns a list of (window_16k, vad_active, start_ms, end_ms) tuples.
        """
        # Guard against odd byte length from network fragmentation
        rem = len(raw_bytes) % 2
        if rem != 0:
            raw_bytes = raw_bytes[:-rem]
        if not raw_bytes:
            return []

        # Convert raw bytes → float32 (assumes int16 little-endian from AudioWorklet)
        int16_arr = np.frombuffer(raw_bytes, dtype="<i2").astype(np.float32) / 32768.0
        self._buf.push(int16_arr)
        self._samples_since_last_hop += len(int16_arr)

        results: list[tuple[np.ndarray, bool, int, int]] = []
        while self._samples_since_last_hop >= self._hop_samples:
            self._samples_since_last_hop -= self._hop_samples
            buf_arr = self._buf.as_array()
            if len(buf_arr) < self._window_samples:
                continue

            window_raw = buf_arr[-self._window_samples :]
            start_ms = max(0, (self._elapsed_samples - self._window_samples) * 1_000 // settings.sample_rate)
            end_ms = self._elapsed_samples * 1_000 // settings.sample_rate

            # Telephony simulation runs on every window
            window_degraded = simulate_telephony(window_raw, input_sr=settings.sample_rate)

            # VAD on the degraded window
            is_speech = self._vad.is_speech(window_degraded)

            results.append((window_degraded, is_speech, start_ms, end_ms))
            self._elapsed_samples += self._hop_samples

        return results
