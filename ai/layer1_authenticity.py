"""
VoiceShield — Layer 1: Voice Authenticity Detection (Production)
================================================================
Dual-branch architecture:
  Branch 1: wav2vec2-large-xlsr-53 → mean-pooled features → Linear classifier head
  Branch 2: Log-Mel Spectrogram → 4-layer CNN → classifier
  Fusion: Weighted combination → P(fake)

Usage:
    from ai.layer1_authenticity import Layer1Detector
    detector = Layer1Detector(device="cuda")
    detector.load_weights("ai/models/best_wav2vec_head.pt", "ai/models/best_mel_cnn.pt")
    score = detector.predict(chunk.waveform_16k, chunk.mel_spectrogram)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Branch 1: wav2vec2 Classification Head
# ──────────────────────────────────────────────────────────────────────

class Wav2Vec2ClassifierHead(nn.Module):
    """
    Lightweight MLP classifier head on top of mean-pooled wav2vec2 hidden states.
    Input: (batch, hidden_dim) where hidden_dim = 1024 for wav2vec2-large-xlsr-53.
    Output: (batch,) — P(fake) in [0, 1].
    """

    def __init__(self, input_dim: int = 1024, hidden_dim: int = 256, dropout: float = 0.3):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Args:
            hidden_states: (batch, seq_len, hidden_dim) from wav2vec2
        Returns:
            (batch,) probabilities via sigmoid
        """
        # Mean pooling over the time dimension
        pooled = hidden_states.mean(dim=1)  # (batch, hidden_dim)
        logits = self.classifier(pooled).squeeze(-1)  # (batch,)
        return torch.sigmoid(logits)


# ──────────────────────────────────────────────────────────────────────
# Branch 2: Mel-Spectrogram CNN
# ──────────────────────────────────────────────────────────────────────

class MelCNN(nn.Module):
    """
    Lightweight 2D CNN for detecting synthesis artifacts in mel-spectrograms.
    Input: (batch, 1, n_mels=80, time_frames)
    Output: (batch,) — P(fake) in [0, 1].

    Architecture:
      Conv2d(1→32) → BN → ReLU → MaxPool
      Conv2d(32→64) → BN → ReLU → MaxPool
      Conv2d(64→128) → BN → ReLU → MaxPool
      Conv2d(128→128) → BN → ReLU → AdaptiveAvgPool(4,4)
      Flatten → Linear(2048→256) → Linear(256→1) → Sigmoid
    """

    def __init__(self, dropout: float = 0.3):
        super().__init__()
        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            # Block 4
            nn.Conv2d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, 1),
        )

    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        """
        Args:
            mel: (batch, 1, n_mels, time_frames)
        Returns:
            (batch,) probabilities via sigmoid
        """
        x = self.features(mel)
        logits = self.classifier(x).squeeze(-1)
        return torch.sigmoid(logits)

    def forward_features(self, mel: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns both the feature maps (for Grad-CAM) and the final probability.
        """
        features = self.features(mel)
        logits = self.classifier(features).squeeze(-1)
        return features, torch.sigmoid(logits)


# ──────────────────────────────────────────────────────────────────────
# Unified Dual-Branch Detector
# ──────────────────────────────────────────────────────────────────────

class Layer1Detector:
    """
    Combined dual-branch voice authenticity detector.

    Branch 1 (wav2vec2): Catches acoustic-level anomalies in voice timbre
    Branch 2 (CNN): Catches synthesis artifacts in spectral patterns

    The two branches complement each other — if a sophisticated fake
    fools the acoustic model, the spectral CNN often still catches the
    telltale high-frequency artifacts that neural vocoders leave behind.

    Usage:
        detector = Layer1Detector(device="cuda")
        detector.load_weights("wav2vec_head.pt", "mel_cnn.pt")

        # From preprocessed chunk:
        score = detector.predict(chunk.waveform_16k, chunk.mel_spectrogram)
        # score > 0.5 → likely fake
    """

    def __init__(
        self,
        wav2vec_model_name: str = "facebook/wav2vec2-large-xlsr-53",
        device: str = "cpu",
        w1: float = 0.6,
        w2: float = 0.4,
    ):
        self.device = torch.device(device)
        self.w1 = w1  # wav2vec2 branch weight
        self.w2 = w2  # CNN branch weight

        # ── Load wav2vec2 backbone (frozen) ──
        try:
            from transformers import Wav2Vec2Model
            self.wav2vec2 = Wav2Vec2Model.from_pretrained(wav2vec_model_name)
            self.wav2vec2.eval()
            for param in self.wav2vec2.parameters():
                param.requires_grad = False
            self.wav2vec2.to(self.device)
            hidden_size = self.wav2vec2.config.hidden_size
        except Exception as e:
            print(f"[WARNING] Could not load wav2vec2 backbone: {e}")
            print("[WARNING] wav2vec2 branch will be disabled. CNN-only mode.")
            self.wav2vec2 = None
            hidden_size = 1024

        # ── Trainable heads ──
        self.wav2vec_head = Wav2Vec2ClassifierHead(input_dim=hidden_size).to(self.device)
        self.mel_cnn = MelCNN().to(self.device)

        self._weights_loaded = False

    def load_weights(self, wav2vec_head_path: str, cnn_path: str):
        """Load trained classifier weights from disk."""
        self.wav2vec_head.load_state_dict(
            torch.load(wav2vec_head_path, map_location=self.device, weights_only=True)
        )
        self.mel_cnn.load_state_dict(
            torch.load(cnn_path, map_location=self.device, weights_only=True)
        )
        self.wav2vec_head.eval()
        self.mel_cnn.eval()
        self._weights_loaded = True

    @torch.no_grad()
    def predict(
        self,
        waveform_16k: torch.Tensor,
        mel_spectrogram: torch.Tensor,
    ) -> dict:
        """
        Run dual-branch inference on a preprocessed chunk.

        Args:
            waveform_16k: (1, 32000) tensor at 16kHz for wav2vec2
            mel_spectrogram: (1, 80, T) log-mel tensor for CNN

        Returns:
            dict with keys:
                - p_fake: float, fused P(fake) in [0, 1]
                - p_wav2vec: float, Branch 1 score
                - p_cnn: float, Branch 2 score
                - verdict: str, "REAL" / "SUSPICIOUS" / "FRAUD"
        """
        waveform_16k = waveform_16k.to(self.device)
        mel_spectrogram = mel_spectrogram.to(self.device)

        # ── Branch 1: wav2vec2 ──
        if self.wav2vec2 is not None:
            # wav2vec2 expects (batch, samples) — squeeze channel dim if needed
            wav_input = waveform_16k.squeeze(0) if waveform_16k.dim() == 3 else waveform_16k
            hidden = self.wav2vec2(wav_input).last_hidden_state
            p_wav2vec = self.wav2vec_head(hidden).item()
        else:
            p_wav2vec = 0.0  # Branch disabled

        # ── Branch 2: CNN on mel-spectrogram ──
        # Ensure shape is (batch, 1, n_mels, time)
        mel_input = mel_spectrogram
        if mel_input.dim() == 2:
            mel_input = mel_input.unsqueeze(0).unsqueeze(0)
        elif mel_input.dim() == 3:
            mel_input = mel_input.unsqueeze(1)
        p_cnn = self.mel_cnn(mel_input).item()

        # ── Fusion ──
        if self.wav2vec2 is not None:
            p_fake = self.w1 * p_wav2vec + self.w2 * p_cnn
        else:
            p_fake = p_cnn  # CNN-only fallback

        # ── Verdict ──
        if p_fake >= 0.7:
            verdict = "FRAUD"
        elif p_fake >= 0.4:
            verdict = "SUSPICIOUS"
        else:
            verdict = "REAL"

        return {
            "p_fake": round(p_fake, 4),
            "p_wav2vec": round(p_wav2vec, 4),
            "p_cnn": round(p_cnn, 4),
            "verdict": verdict,
        }

    def get_cnn_for_gradcam(self) -> MelCNN:
        """Return the CNN model for Grad-CAM visualization."""
        return self.mel_cnn
