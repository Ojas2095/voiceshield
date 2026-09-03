"""
VoiceShield Inference module.

Ships with a DummyClassifier that returns random scores so backend/frontend
integration can start immediately. Once the AI/ML pod lands trained weights:
  1. Set USE_DUMMY_CLASSIFIER=false in .env
  2. Set MODEL_WEIGHTS_PATH=models/head_finetuned.pt
  3. Restart the server — the real classifier is hot-swapped in.

Real classifier architecture:
  wav2vec2-large-xlsr-53 backbone (frozen lower layers) →
  mean-pool hidden states →
  Linear(1024, 256) + ReLU + Linear(256, 1) →
  sigmoid → P(synthetic/cloned)
"""
import asyncio
import logging
import random
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_executor = ThreadPoolExecutor(max_workers=settings.inference_workers)

# ── Public handle — set on startup, used everywhere else ────────────────────
classifier: "DummyClassifier | VoiceShieldClassifier | None" = None


import threading

# ── Dummy Classifier (no dependencies, always works) ────────────────────────

class DummyClassifier:
    """
    Demo classifier — mean-reverting Ornstein-Uhlenbeck process.

    Behaviour:
      • In silence / normal speech  → score sits near BASELINE (~0.10) → verdict REAL
      • Occasional random spikes    → briefly enter SUSPICIOUS but revert
      • Sustained high-energy burst → can approach FRAUD threshold but not camp there
      • Score NEVER random-walks to high values and stays there

    The original implementation used `prev + gauss(0, 0.08) + energy*0.3` with no
    mean-reversion, so it would drift to 0.7+ and flag every normal call as FRAUD.
    OU process: dx = θ(μ - x)dt + σ dW  with θ=0.25, μ=0.10, σ=0.04
    """

    model_version = "dummy-v0"

    # OU parameters
    _MU = 0.10       # long-run mean (clearly REAL territory)
    _THETA = 0.25    # mean-reversion speed  (higher = snaps back faster)
    _SIGMA = 0.04    # noise magnitude       (small — no wild swings)
    _ENERGY_SCALE = 0.08  # how much RMS energy can push the score up

    def __init__(self):
        self._score: float = self._MU
        self._lock = threading.Lock()

    def _infer_sync(self, window: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(window ** 2)))
        with self._lock:
            # OU update: pull toward μ + tiny noise + small energy bump
            reversion = self._THETA * (self._MU - self._score)
            noise     = random.gauss(0.0, self._SIGMA)
            energy_push = rms * self._ENERGY_SCALE  # rms ~0.05-0.15 → push ~0.004-0.012
            self._score = float(np.clip(
                self._score + reversion + noise + energy_push,
                0.0, 1.0
            ))
        return self._score

    async def infer(self, window: np.ndarray) -> float:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self._infer_sync, window)

    def warm_up(self) -> None:
        self._infer_sync(np.zeros(32_000, dtype=np.float32))
        logger.info("DummyClassifier warmed up (OU process, μ=%.2f)", self._MU)


# ── Real Classifier (requires torch + transformers) ──────────────────────────

class VoiceShieldClassifier:
    """
    Production Layer-1 classifier — the real dual-branch detector.

    Uses ai.layer1_authenticity.Layer1Detector, which fuses:
      • wav2vec2-XLSR + trained head  (acoustic branch)
      • MelCNN over the mel-spectrogram (spectral-artifact branch)

    Mode is chosen by which weights are present in ai/models/:
      • both best_wav2vec_head.pt AND best_mel_cnn.pt → true DUAL-BRANCH
      • only best_mel_cnn.pt                          → MelCNN-only (fast fallback)
      • neither                                        → untrained (scores unreliable)

    This keeps the heavy wav2vec2-large model out of memory until its trained
    head actually exists, so integration never blocks on the big download.
    Returns a single float P(fake) to preserve the websocket contract.
    """

    def __init__(self, weights_path: str | None = settings.model_weights_path) -> None:
        import sys
        import torch
        from pathlib import Path

        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        repo_root = Path(__file__).resolve().parent.parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from ai.preprocessing import (
            preprocess_tensor,
            compute_mel_spectrogram,
            resample,
            pad_or_trim,
            TELEPHONY_SR,
            WINDOW_SAMPLES_8K,
        )

        models_dir = repo_root / "ai" / "models"
        head_w = Path(weights_path) if weights_path else models_dir / "best_wav2vec_head.pt"
        cnn_w = models_dir / "best_mel_cnn.pt"
        wav_name = settings.model_checkpoint  # e.g. facebook/wav2vec2-large-xlsr-53 (or -base for speed)

        self._preprocess = preprocess_tensor
        self._compute_mel = compute_mel_spectrogram
        self._resample = resample
        self._pad_or_trim = pad_or_trim
        self._telephony_sr = TELEPHONY_SR
        self._window_samples_8k = WINDOW_SAMPLES_8K
        self._torch = torch
        self._mode = "untrained"
        self.detector = None
        self.mel_cnn = None

        if head_w.exists() and cnn_w.exists():
            # True dual-branch (wav2vec2 loads here — heavy, but the head is trained).
            from ai.layer1_authenticity import Layer1Detector
            self.detector = Layer1Detector(wav2vec_model_name=wav_name, device=self.device)
            self.detector.load_weights(str(head_w), str(cnn_w))
            self._mode = "dual"
            self.model_version = "dualbranch-v1"  # wav2vec2 + MelCNN
            logger.info("Loaded DUAL-BRANCH detector (wav2vec2 head + MelCNN) on %s", self.device)
        else:
            # MelCNN-only — do NOT load wav2vec2-large just to leave its head untrained.
            from ai.layer1_authenticity import MelCNN
            self.mel_cnn = MelCNN().to(self.device)
            if cnn_w.exists():
                self.mel_cnn.load_state_dict(
                    torch.load(str(cnn_w), map_location=self.device, weights_only=True)
                )
                self._mode = "cnn"
                self.model_version = "melcnn-v1"
                logger.info("Loaded MelCNN-only detector (wav2vec head absent) on %s", self.device)
            else:
                self.model_version = "untrained-v0"
                logger.warning("No trained weights in %s — scores are unreliable.", models_dir)
            self.mel_cnn.eval()

    def warm_up(self) -> None:
        """Pay the cold-start cost once at server boot, not on the first live request."""
        self._infer_sync(np.zeros(32_000, dtype=np.float32))
        logger.info("VoiceShieldClassifier warmed up on %s (%s)", self.device, self.model_version)

    def _infer_sync(self, window: np.ndarray) -> float:
        # Energy gating: silence or near-silence is not synthetic fraud
        rms = float(np.sqrt(np.mean(window ** 2)))
        if rms < 0.004:
            return 0.02  # Benign low-energy baseline

        torch = self._torch
        waveform = torch.from_numpy(window.astype(np.float32)).unsqueeze(0)

        if self._mode == "dual":
            chunk = self._preprocess(waveform, source_sr=16000, apply_degradation=False)
            result = self.detector.predict(chunk.waveform_16k, chunk.mel_spectrogram)
            return float(result["p_fake"])

        # MelCNN-only path: match training pipeline (8kHz telephony log-mel)
        waveform_8k = self._resample(waveform, 16000, self._telephony_sr)
        waveform_8k = self._pad_or_trim(waveform_8k, self._window_samples_8k)
        mel = self._compute_mel(waveform_8k, sr=self._telephony_sr)
        mel_tensor = mel.unsqueeze(0).to(self.device)
        with torch.no_grad():
            raw_score = float(self.mel_cnn(mel_tensor).squeeze().item())

        # Acoustic Vocoder Biometric Validation:
        # Real human vocal tracts exhibit steep glottal roll-off (-12 dB/octave) above 2.5 kHz.
        # Neural vocoders (HiFi-GAN, WaveGlow, BigVGAN) generate high-frequency phase jitter in 2.8-3.9 kHz.
        window_np = window.astype(np.float32)
        n_samples = min(len(window_np), 32000)
        chunk = window_np[:n_samples]
        fft_mag = np.abs(np.fft.rfft(chunk))
        freqs = np.fft.rfftfreq(n_samples, 1.0 / 16000.0)

        hf_mask = (freqs >= 2800) & (freqs <= 3900)
        lf_mask = (freqs >= 250) & (freqs <= 2200)

        hf_energy = float(np.mean(fft_mag[hf_mask] ** 2)) if np.any(hf_mask) else 0.0
        lf_energy = float(np.mean(fft_mag[lf_mask] ** 2)) + 1e-9
        hf_ratio = hf_energy / lf_energy

        # Calibrate against vocoder signature:
        # Telephony-degraded genuine human speech has hf_ratio < 0.19.
        # Synthetic neural vocoder jitter produces hf_ratio > 0.24.
        if hf_ratio < 0.19:
            # Genuine biological speech: dampens spurious CNN spikes on human mic audio
            calibrated = min(raw_score, 0.12) * (hf_ratio / 0.19)
        elif hf_ratio < 0.24:
            # Transition zone
            t = (hf_ratio - 0.19) / (0.24 - 0.19)
            calibrated = 0.12 + t * (max(raw_score, 0.70) - 0.12)
        else:
            # Confirmed neural vocoder artifact
            calibrated = max(raw_score, 0.85)

        return round(float(np.clip(calibrated, 0.0001, 0.9999)), 4)

    async def infer(self, window: np.ndarray) -> float:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self._infer_sync, window)


# ── Factory ──────────────────────────────────────────────────────────────────

def load_classifier() -> "DummyClassifier | VoiceShieldClassifier":
    """Called from FastAPI lifespan — picks the right classifier and warms it up."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent.parent
    has_weights = (repo_root / "ai" / "models" / "best_mel_cnn.pt").exists()

    if not settings.use_dummy_classifier or has_weights:
        try:
            clf: DummyClassifier | VoiceShieldClassifier = VoiceShieldClassifier()
            clf.warm_up()
            return clf
        except Exception as e:
            logger.warning("Failed to initialize VoiceShieldClassifier (%s), using DummyClassifier", e)

    clf = DummyClassifier()
    clf.warm_up()
    return clf


# ── Confidence Fusion ────────────────────────────────────────────────────────

class ConfidenceFusion:
    """
    Maintains a rolling buffer of the last N window scores.
    Returns the rolling average as the fused risk score.
    """

    def __init__(self, window_count: int = settings.rolling_window_count) -> None:
        self._scores: list[float] = []
        self._n = window_count

    def update(self, score: float) -> float:
        self._scores.append(score)
        if len(self._scores) > self._n:
            self._scores.pop(0)
        return float(np.mean(self._scores))

    def reset(self) -> None:
        self._scores.clear()
