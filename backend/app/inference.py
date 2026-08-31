import abc
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import time
import numpy as np
try:
    import torch
    import torch.nn as nn
    from transformers import Wav2Vec2Model, Wav2Vec2FeatureExtractor
except ImportError:
    torch = None
    nn = None
    Wav2Vec2Model = None
    Wav2Vec2FeatureExtractor = None

from backend.app.config import settings

logger = logging.getLogger("voiceshield.inference")


class SpoofClassifier(abc.ABC):
    """
    Abstract interface for AI Voice Spoof Classifiers.
    Returns float probability score in range [0.0, 1.0] representing spoof confidence.
    """
    model_version: str = "base-interface"

    @abc.abstractmethod
    async def infer(self, window: np.ndarray, call_id: str = "") -> float:
        """
        Asynchronously infer spoof probability for a given 2-second audio array.
        Must not block the main asyncio event loop.
        """
        pass


class DummyClassifier(SpoofClassifier):
    """
    # DUMMY
    Synthetic classifier generating plausible, slowly-varying fake spoof risk scores per call_id.
    """
    model_version: str = "v0.1-dummy"

    def __init__(self):
        self._step_counter: dict[str, int] = {}
        logger.info("Initialized DummyClassifier (# DUMMY)")

    async def infer(self, window: np.ndarray, call_id: str = "") -> float:
        # Simulate slight processing latency (e.g. 10ms)
        await asyncio.sleep(0.01)

        step = self._step_counter.get(call_id, 0)
        self._step_counter[call_id] = step + 1

        # Smooth sine-based oscillation around 0.35 with random variation between 0.15 and 0.85
        base_score = 0.35 + 0.30 * math.sin(step * 0.4)
        noise = (hash(f"{call_id}-{step}") % 100) / 500.0  # deterministic float 0.0 - 0.2
        score = min(max(base_score + noise, 0.05), 0.98)
        
        return round(score, 4)


_BaseModule = nn.Module if nn is not None else object


class VoiceShieldClassificationHead(_BaseModule):
    """
    Linear classification head operating on pooled wav2vec2 hidden states.
    """
    def __init__(self, hidden_size: int = 1024):
        super().__init__()
        if nn is not None:
            self.classifier = nn.Sequential(
                nn.Linear(hidden_size, 256),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(256, 1),
                nn.Sigmoid()
            )
        else:
            self.classifier = None

    def forward(self, x):
        if self.classifier is not None:
            return self.classifier(x)
        return x


class VoiceShieldClassifier(SpoofClassifier):
    """
    Real-shaped PyTorch Classifier loading wav2vec2-XLSR backbone + classification head.
    Executes inference inside a ThreadPoolExecutor to prevent blocking the asyncio event loop.
    """
    model_version: str = "v1.0-wav2vec2-xlsr-stub"

    def __init__(self, model_name: str = settings.WAV2VEC_MODEL_NAME):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Initializing VoiceShieldClassifier on device: {self.device}")

        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="inference_worker")
        
        # Load feature extractor and model backbone once at construction
        try:
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
            self.backbone = Wav2Vec2Model.from_pretrained(model_name).to(self.device)
            self.backbone.eval()
            hidden_size = self.backbone.config.hidden_size
            self.head = VoiceShieldClassificationHead(hidden_size=hidden_size).to(self.device)
            self.head.eval()
            
            # Warm-load model with a zero tensor frame
            warm_input = np.zeros(32000, dtype=np.float32)
            self._sync_infer(warm_input)
            logger.info("VoiceShieldClassifier backbone and head loaded & warm-tested successfully.")
        except Exception as e:
            logger.warning(f"Could not load full wav2vec2 model ({e}). Using CPU fallback classification head.")
            self.feature_extractor = None
            self.backbone = None
            self.head = VoiceShieldClassificationHead(hidden_size=1024).to(self.device)

    def _sync_infer(self, window: np.ndarray) -> float:
        """
        Synchronous PyTorch inference execution. Run inside threadpool executor.
        """
        with torch.no_grad():
            if self.backbone is not None and self.feature_extractor is not None:
                inputs = self.feature_extractor(
                    window,
                    sampling_rate=16000,
                    return_tensors="pt"
                ).input_values.to(self.device)
                
                outputs = self.backbone(inputs)
                # Mean pooling over sequence length
                pooled = outputs.last_hidden_state.mean(dim=1)
                prob = self.head(pooled).item()
            else:
                # Fallback score if weights not downloaded locally
                tensor_in = torch.from_numpy(window).unsqueeze(0).to(self.device)
                features = tensor_in.mean(dim=-1, keepdim=True).repeat(1, 1024)
                prob = self.head(features).item()

            return float(prob)

    async def infer(self, window: np.ndarray, call_id: str = "") -> float:
        """
        Offloads synchronous PyTorch inference to ThreadPoolExecutor.
        """
        loop = asyncio.get_running_loop()
        score = await loop.run_in_executor(self.executor, self._sync_infer, window)
        return round(score, 4)


def get_classifier() -> SpoofClassifier:
    """
    Factory function instantiating classifier based on settings.USE_DUMMY_MODEL.
    Swapping model implementation is a single configuration toggle.
    """
    if settings.USE_DUMMY_MODEL:
        return DummyClassifier()
    else:
        return VoiceShieldClassifier()
