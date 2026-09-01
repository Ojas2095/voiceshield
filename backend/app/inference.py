"""
VoiceShield — Backend Inference Bridge (Production)
====================================================
Bridges the FastAPI backend with the ai/ engine.
Provides async-safe inference by offloading PyTorch to a ThreadPoolExecutor.

This replaces the old inference.py that had duplicate model classes.
Now it imports directly from ai/ so there's a single source of truth.
"""
import abc
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import os
import sys
import numpy as np

# Ensure ai/ module is importable from backend context
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import torch
    from ai.preprocessing import preprocess_chunk, ProcessedChunk
    from ai.layer1_authenticity import Layer1Detector
    from ai.gradcam import GradCAMGenerator
    HAS_TORCH = True
except ImportError as e:
    HAS_TORCH = False
    torch = None
    print(f"[WARNING] Could not import AI engine: {e}")

from backend.app.config import settings

logger = logging.getLogger("voiceshield.inference")


# ──────────────────────────────────────────────────────────────────────
# Abstract Interface
# ──────────────────────────────────────────────────────────────────────

class SpoofClassifier(abc.ABC):
    """
    Abstract interface for AI Voice Spoof Classifiers.
    Returns float probability score in range [0.0, 1.0] representing spoof confidence.
    """
    model_version: str = "base-interface"

    @abc.abstractmethod
    async def infer(self, window: np.ndarray, call_id: str = "") -> dict:
        """
        Asynchronously infer spoof probability for a given 2-second audio array.
        Returns dict with p_fake, p_wav2vec, p_cnn, verdict, gradcam_b64.
        """
        pass


# ──────────────────────────────────────────────────────────────────────
# Dummy Classifier (for development/testing without GPU)
# ──────────────────────────────────────────────────────────────────────

class DummyClassifier(SpoofClassifier):
    """
    Synthetic classifier generating plausible, slowly-varying fake scores.
    Use this when you don't have trained model weights yet.
    """
    model_version: str = "v0.1-dummy"

    def __init__(self):
        self._step_counter: dict[str, int] = {}
        logger.info("Initialized DummyClassifier (DUMMY MODE)")

    async def infer(self, window: np.ndarray, call_id: str = "") -> dict:
        await asyncio.sleep(0.01)

        step = self._step_counter.get(call_id, 0)
        self._step_counter[call_id] = step + 1

        base_score = 0.35 + 0.30 * math.sin(step * 0.4)
        noise = (hash(f"{call_id}-{step}") % 100) / 500.0
        score = min(max(base_score + noise, 0.05), 0.98)
        score = round(score, 4)

        if score >= 0.7:
            verdict = "FRAUD"
        elif score >= 0.4:
            verdict = "SUSPICIOUS"
        else:
            verdict = "REAL"

        return {
            "p_fake": score,
            "p_wav2vec": round(score * 0.9, 4),
            "p_cnn": round(score * 1.1, 4),
            "verdict": verdict,
            "gradcam_b64": None,
        }


# ──────────────────────────────────────────────────────────────────────
# Production Classifier (uses ai/ module)
# ──────────────────────────────────────────────────────────────────────

class ProductionClassifier(SpoofClassifier):
    """
    Real classifier using the trained dual-branch AI engine from ai/.
    Runs inference in a ThreadPoolExecutor to avoid blocking asyncio.
    """
    model_version: str = "v1.0-dual-branch"

    def __init__(self):
        if not HAS_TORCH:
            raise RuntimeError("PyTorch and ai/ module required for ProductionClassifier")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing ProductionClassifier on device: {self.device}")
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="inference")

        # Initialize the detector
        self.detector = Layer1Detector(device=self.device)

        # Load trained weights if they exist
        head_path = os.path.join(settings.MODEL_WEIGHTS_DIR, "best_wav2vec_head.pt")
        cnn_path = os.path.join(settings.MODEL_WEIGHTS_DIR, "best_mel_cnn.pt")

        if os.path.exists(head_path) and os.path.exists(cnn_path):
            self.detector.load_weights(head_path, cnn_path)
            logger.info(f"Loaded trained weights from {settings.MODEL_WEIGHTS_DIR}")
        else:
            logger.warning(
                f"Trained weights not found at {settings.MODEL_WEIGHTS_DIR}. "
                "Running with untrained heads (scores will be random)."
            )

        # Initialize Grad-CAM generator
        self.gradcam = GradCAMGenerator(self.detector.get_cnn_for_gradcam())
        logger.info("ProductionClassifier ready.")

    def _sync_infer(self, window: np.ndarray) -> dict:
        """Synchronous inference — runs inside ThreadPoolExecutor."""
        # Convert raw PCM to bytes for preprocessing
        pcm_bytes = (window * 32768).astype(np.int16).tobytes()
        chunk = preprocess_chunk(pcm_bytes, source_sr=16000, apply_degradation=False)

        if not chunk.is_speech:
            return {
                "p_fake": 0.0,
                "p_wav2vec": 0.0,
                "p_cnn": 0.0,
                "verdict": "REAL",
                "gradcam_b64": None,
            }

        # Run dual-branch inference
        result = self.detector.predict(chunk.waveform_16k, chunk.mel_spectrogram)

        # Generate Grad-CAM if suspicious or fraud
        gradcam_b64 = None
        if result["p_fake"] >= 0.4:
            try:
                gradcam_b64 = self.gradcam.generate(chunk.mel_spectrogram)
            except Exception as e:
                logger.warning(f"Grad-CAM generation failed: {e}")

        result["gradcam_b64"] = gradcam_b64
        return result

    async def infer(self, window: np.ndarray, call_id: str = "") -> dict:
        """Offloads synchronous PyTorch inference to ThreadPoolExecutor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._sync_infer, window)


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────

def get_classifier() -> SpoofClassifier:
    """
    Factory function. Toggle between Dummy and Production via settings.USE_DUMMY_MODEL.
    """
    if settings.USE_DUMMY_MODEL:
        return DummyClassifier()
    else:
        return ProductionClassifier()
