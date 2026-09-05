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

        # ── Statistical Calibrator & OOD Detection (Track 2) ──────────────────
        self.calibrator = None
        self.mean_vec = None
        self.cov_inv = None
        self.ood_threshold = 2.95
        self.last_telemetry = {"is_low_confidence": 0.0, "ood_distance": 0.0}
        cal_path = models_dir / "calibrator.joblib"
        if cal_path.exists():
            try:
                import joblib
                bundle = joblib.load(str(cal_path))
                self.calibrator = bundle.get("model")
                self.mean_vec = bundle.get("mean_vec")
                self.cov_inv = bundle.get("cov_inv")
                self.ood_threshold = float(bundle.get("ood_threshold", 2.95))
                logger.info(
                    "Loaded statistical calibrator (ECE=%.2f%%, Brier=%.4f, OOD=%.2f)",
                    bundle.get("ece", 0.0) * 100,
                    bundle.get("brier_score", 0.0),
                    self.ood_threshold,
                )
            except Exception as exc:
                logger.warning("Could not load calibrator.joblib: %s", exc)

    def warm_up(self) -> None:
        """Pay the cold-start cost once at server boot, not on the first live request."""
        self._infer_sync(np.zeros(32_000, dtype=np.float32))
        logger.info("VoiceShieldClassifier warmed up on %s (%s)", self.device, self.model_version)

    def _infer_sync(self, window: np.ndarray) -> float:
        # Energy gating: silence, room ambient noise, or word pauses are not synthetic fraud
        rms = float(np.sqrt(np.mean(window ** 2)))
        if rms < 0.012:
            return 0.02  # Benign low-energy baseline

        torch = self._torch
        waveform = torch.from_numpy(window.astype(np.float32)).unsqueeze(0)

        if self._mode == "dual":
            chunk = self._preprocess(waveform, source_sr=16000, apply_degradation=False)
            result = self.detector.predict(chunk.waveform_16k, chunk.mel_spectrogram)
            return float(result["p_fake"])

        # MelCNN branch
        raw_cnn = 0.0
        if self.mel_cnn is not None:
            waveform_8k = self._resample(waveform, 16000, self._telephony_sr)
            waveform_8k = self._pad_or_trim(waveform_8k, self._window_samples_8k)
            mel = self._compute_mel(waveform_8k, sr=self._telephony_sr)
            mel_tensor = mel.unsqueeze(0).to(self.device)
            with torch.no_grad():
                raw_cnn = float(self.mel_cnn(mel_tensor).squeeze().item())

        window_np = window.astype(np.float32)
        n_samples = min(len(window_np), 32000)
        chunk_samples = window_np[:n_samples]

        # ── Feature 1: Telephone-band HF/LF carrier ratio ─────────────────────
        fft_mag = np.abs(np.fft.rfft(chunk_samples))
        freqs = np.fft.rfftfreq(n_samples, 1.0 / 16000.0)

        hf_mask = (freqs >= 2800) & (freqs <= 3400)
        lf_mask = (freqs >= 250) & (freqs <= 2200)

        hf_energy = float(np.mean(fft_mag[hf_mask] ** 2)) if np.any(hf_mask) else 0.0
        lf_energy = float(np.mean(fft_mag[lf_mask] ** 2)) + 1e-9
        hf_ratio = hf_energy / lf_energy

        # ── Feature 2: Pitch Jitter (Biological Vocal Cord Tremor) ─────────────
        # Human vocal folds have natural muscle micro-jitter: 0.8% to 3.8%.
        # AI/TTS models have mathematical period regularity (< 0.8%) or phase jitter (> 3.8%).
        frame_len, hop_len = int(0.040 * 16000), int(0.015 * 16000)
        periods = []
        for i in range(0, len(chunk_samples) - frame_len, hop_len):
            f = chunk_samples[i:i+frame_len] - np.mean(chunk_samples[i:i+frame_len])
            if np.sqrt(np.mean(f ** 2)) < 0.015:
                continue
            corr = np.correlate(f, f, mode='full')
            corr = corr[len(corr)//2:]
            min_l, max_l = int(16000 / 320), int(16000 / 80)
            pl = np.argmax(corr[min_l:max_l]) + min_l
            if corr[pl] / (corr[0] + 1e-9) > 0.40:
                periods.append(pl)

        if len(periods) >= 8:
            # Filter octave jumps and syllable transitions: only consecutive periods within 25% of each other
            valid_diffs = []
            for idx in range(len(periods) - 1):
                d = abs(periods[idx + 1] - periods[idx])
                if d / min(periods[idx], periods[idx + 1]) <= 0.25:
                    valid_diffs.append(d)
            if len(valid_diffs) >= 4:
                jitter = float(np.mean(valid_diffs) / (np.mean(periods) + 1e-9))
                is_biological_jitter = (0.008 <= jitter <= 0.038)
            else:
                jitter = float(np.mean(np.abs(np.diff(periods))) / (np.mean(periods) + 1e-9))
                is_biological_jitter = (0.008 <= jitter <= 0.038)
        else:
            # Unvoiced / pause / insufficient periods for pitch tracking
            is_biological_jitter = True
            jitter = 0.021

        # ── Statistical Calibrated Scoring (Track 2) ──────────────────────────
        feat_vec = np.array([hf_ratio, jitter, raw_cnn], dtype=np.float32)
        if self.calibrator is not None:
            calibrated = float(self.calibrator.predict_proba([feat_vec])[0, 1])
        else:
            # Continuous mathematical sigmoid blend fallback
            z = -4.23 + 4.17 * hf_ratio + 0.21 * jitter + 1.49 * raw_cnn
            calibrated = 1.0 / (1.0 + np.exp(-z))

        # Biological Vocal Tract Invariant Protection:
        # Natural human vocal fold micro-tremor and deep glottal rolloff guard against noise spikes
        if is_biological_jitter and (hf_ratio < 0.25):
            calibrated = min(calibrated, 0.15)
        elif hf_ratio >= 1.50:
            calibrated = max(calibrated, 0.85)

        calibrated = float(np.clip(calibrated, 0.0001, 0.9999))

        # ── OOD Telemetry ────────────────────────────────────────────────────
        is_low_confidence = False
        ood_dist = 0.0
        if self.mean_vec is not None and self.cov_inv is not None:
            try:
                from scipy.spatial.distance import mahalanobis
                feat_vec = np.array([hf_ratio, jitter, raw_cnn], dtype=np.float32)
                ood_dist = float(mahalanobis(feat_vec, self.mean_vec, self.cov_inv))
                # Only flag low confidence when prediction is genuinely borderline (0.25 <= calibrated <= 0.65)
                is_low_confidence = bool((ood_dist > self.ood_threshold) and (0.25 <= calibrated <= 0.65))
            except Exception:
                pass

        self.last_telemetry = {
            "is_low_confidence": 1.0 if is_low_confidence else 0.0,
            "ood_distance": round(ood_dist, 4),
        }

        logger.info(
            "Acoustic metrics: hf_ratio=%.3f jitter=%.3f raw_cnn=%.3f -> score=%.4f (ood=%.2f low_conf=%s)",
            hf_ratio, jitter, raw_cnn, calibrated, ood_dist, is_low_confidence,
        )

        return round(calibrated, 4)

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
