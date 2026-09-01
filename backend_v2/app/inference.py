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
    Production classifier — loads only when USE_DUMMY_CLASSIFIER=false.
    Wraps wav2vec2-XLSR backbone + lightweight CNN/linear head.
    """

    def __init__(
        self,
        checkpoint: str = settings.model_checkpoint,
        weights_path: str | None = settings.model_weights_path,
    ) -> None:
        # Lazy-import so the server can start without torch if using dummy mode
        import torch
        from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2Model

        self.model_version = "xlsr-v1"
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
            
        logger.info("Loading wav2vec2 backbone on %s …", self.device)

        self.extractor = Wav2Vec2FeatureExtractor.from_pretrained(checkpoint)
        self.backbone = Wav2Vec2Model.from_pretrained(checkpoint).to(self.device).eval()

        # Freeze all but the top 4 transformer layers
        for name, param in self.backbone.named_parameters():
            if not any(f"encoder.layers.{i}" in name for i in range(20, 24)):
                param.requires_grad = False

        self.head = torch.nn.Sequential(
            torch.nn.Linear(1024, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, 1),
        ).to(self.device)

        if weights_path:
            state = torch.load(weights_path, map_location=self.device, weights_only=True)
            self.head.load_state_dict(state)
            logger.info("Loaded head weights from %s", weights_path)
        else:
            logger.warning("No weights_path supplied — head is randomly initialised!")

        self._torch = torch

    def warm_up(self) -> None:
        """Pay the cold-start cost once at server boot, not on the first live request."""
        self._infer_sync(np.zeros(32_000, dtype=np.float32))
        logger.info("VoiceShieldClassifier warmed up on %s", self.device)

    def _infer_sync(self, window: np.ndarray) -> float:
        torch = self._torch

        inputs = self.extractor(
            window,
            sampling_rate=settings.sample_rate,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            feats = self.backbone(
                inputs.input_values.to(self.device)
            ).last_hidden_state.mean(dim=1)
            return float(torch.sigmoid(self.head(feats)).item())

    async def infer(self, window: np.ndarray) -> float:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self._infer_sync, window)


# ── Factory ──────────────────────────────────────────────────────────────────

def load_classifier() -> "DummyClassifier | VoiceShieldClassifier":
    """Called from FastAPI lifespan — picks the right classifier and warms it up."""
    if settings.use_dummy_classifier:
        clf: DummyClassifier | VoiceShieldClassifier = DummyClassifier()
    else:
        clf = VoiceShieldClassifier()
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
