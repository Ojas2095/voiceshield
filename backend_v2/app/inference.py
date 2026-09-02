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
    Production classifier — loads only when USE_DUMMY_CLASSIFIER=false (or auto-detected).
    Wraps trained MelCNN / Layer1Detector from ai/models.
    """

    def __init__(
        self,
        checkpoint: str = settings.model_checkpoint,
        weights_path: str | None = settings.model_weights_path,
    ) -> None:
        import torch
        from pathlib import Path

        self.model_version = "melcnn-v1"
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        # Check for trained MelCNN weights
        repo_root = Path(__file__).resolve().parent.parent.parent
        default_weights = repo_root / "ai" / "models" / "best_mel_cnn.pt"
        default_threshold = repo_root / "ai" / "models" / "threshold.json"

        target_weights = weights_path or (str(default_weights) if default_weights.exists() else None)

        try:
            import sys
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            from ai.layer1_authenticity import MelCNN
            from ai.preprocessing import compute_mel_spectrogram, TELEPHONY_SR

            self.mel_cnn = MelCNN().to(self.device)
            if target_weights and Path(target_weights).exists():
                self.mel_cnn.load_state_dict(torch.load(target_weights, map_location=self.device, weights_only=True))
                logger.info("Loaded trained MelCNN weights from %s on %s", target_weights, self.device)
            else:
                logger.warning("Trained weights not found, using initialized MelCNN on %s", self.device)

            self.mel_cnn.eval()
            self._compute_mel = compute_mel_spectrogram
            self._use_mel_cnn = True
        except Exception as e:
            logger.warning("Could not load MelCNN: %s. Falling back to wav2vec2 if configured.", e)
            self._use_mel_cnn = False

        self._torch = torch

    def warm_up(self) -> None:
        """Pay the cold-start cost once at server boot, not on the first live request."""
        self._infer_sync(np.zeros(32_000, dtype=np.float32))
        logger.info("VoiceShieldClassifier warmed up on %s", self.device)

    def _infer_sync(self, window: np.ndarray) -> float:
        torch = self._torch
        if self._use_mel_cnn:
            waveform = torch.from_numpy(window.astype(np.float32)).unsqueeze(0)
            mel = self._compute_mel(waveform, sr=16000)
            mel_tensor = mel.unsqueeze(0).to(self.device)
            with torch.no_grad():
                prob = self.mel_cnn(mel_tensor).squeeze().item()
                return float(prob)
        return 0.10

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
