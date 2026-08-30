"""
VoiceShield — Layer 1: Voice Authenticity Detection
Dual-branch: wav2vec2 (acoustic features) + CNN (mel-spectrogram) → fused fake/real probability.
"""
import torch
import torch.nn as nn
from transformers import Wav2Vec2Model


class Wav2Vec2ClassifierHead(nn.Module):
    """Lightweight classifier head on top of frozen wav2vec2 features."""
    
    def __init__(self, input_dim: int = 1024, hidden_dim: int = 256):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )
    
    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        # Pool over time dimension
        pooled = hidden_states.mean(dim=1)  # (batch, hidden_dim)
        return self.classifier(pooled).squeeze(-1)  # (batch,)


class MelCNN(nn.Module):
    """Lightweight CNN operating on mel-spectrograms for artifact detection."""
    
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 4 * 4, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
    
    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        # mel: (batch, 1, n_mels, time)
        x = self.features(mel)
        return self.classifier(x).squeeze(-1)


class Layer1Detector:
    """
    Combined Layer 1 detector.
    Usage:
        detector = Layer1Detector()
        detector.load_weights("path/to/wav2vec_head.pt", "path/to/cnn.pt")
        p_fake = detector.predict(waveform_8k, mel_spectrogram)
    """
    
    def __init__(self, device: str = "cpu"):
        self.device = torch.device(device)
        
        # wav2vec2 backbone (frozen)
        self.wav2vec2 = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-large-xlsr-53")
        self.wav2vec2.eval()
        for param in self.wav2vec2.parameters():
            param.requires_grad = False
        self.wav2vec2.to(self.device)
        
        # Trainable heads
        self.wav2vec_head = Wav2Vec2ClassifierHead(input_dim=1024).to(self.device)
        self.mel_cnn = MelCNN().to(self.device)
        
        # Fusion weights
        self.w1 = 0.6  # wav2vec2 branch
        self.w2 = 0.4  # CNN branch
    
    def load_weights(self, wav2vec_head_path: str, cnn_path: str):
        """Load trained classifier weights."""
        self.wav2vec_head.load_state_dict(torch.load(wav2vec_head_path, map_location=self.device))
        self.mel_cnn.load_state_dict(torch.load(cnn_path, map_location=self.device))
        self.wav2vec_head.eval()
        self.mel_cnn.eval()
    
    @torch.no_grad()
    def predict(self, waveform_8k: torch.Tensor, mel_spectrogram: torch.Tensor) -> float:
        """
        Run dual-branch inference.
        Returns: P(fake) as a float between 0.0 and 1.0.
        """
        waveform_8k = waveform_8k.to(self.device)
        mel_spectrogram = mel_spectrogram.to(self.device)
        
        # Branch 1: wav2vec2
        # wav2vec2 expects 16kHz — resample up from 8kHz for the model
        import torchaudio
        upsampler = torchaudio.transforms.Resample(8000, 16000).to(self.device)
        waveform_16k = upsampler(waveform_8k)
        hidden = self.wav2vec2(waveform_16k.squeeze(0) if waveform_16k.dim() == 3 else waveform_16k).last_hidden_state
        p_wav2vec = self.wav2vec_head(hidden).item()
        
        # Branch 2: CNN on mel-spectrogram
        if mel_spectrogram.dim() == 2:
            mel_spectrogram = mel_spectrogram.unsqueeze(0).unsqueeze(0)  # (1, 1, n_mels, time)
        elif mel_spectrogram.dim() == 3:
            mel_spectrogram = mel_spectrogram.unsqueeze(0)
        p_cnn = self.mel_cnn(mel_spectrogram).item()
        
        # Fusion
        p_fake = self.w1 * p_wav2vec + self.w2 * p_cnn
        return p_fake
