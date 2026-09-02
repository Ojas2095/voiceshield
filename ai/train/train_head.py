"""
VoiceShield — Training Script (for your friend)
================================================
Fine-tunes the wav2vec2 classifier head and MelCNN on the prepared dataset.

Usage:
    python -m ai.train.train_head --data_dir ./data --epochs 30 --batch_size 16
"""
import os
import sys
import json
import argparse
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torchaudio
from torch.utils.data import Dataset, DataLoader, random_split
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ai.preprocessing import (
    compute_mel_spectrogram, resample, pad_or_trim,
    TELEPHONY_SR, MODEL_SR, WINDOW_SAMPLES_8K, WINDOW_SAMPLES_16K
)
from ai.layer1_authenticity import Wav2Vec2ClassifierHead, MelCNN


# ──────────────────────────────────────────────────────────────────────
# Dataset
# ──────────────────────────────────────────────────────────────────────

class VoiceShieldDataset(Dataset):
    """PyTorch dataset loading from the manifest.json created by build_dataset.py."""

    def __init__(self, data_dir: str, exclude_generators=None, only_generators=None,
                 manifest_name: str = "manifest.json"):
        """
        exclude_generators: list of generator names to DROP (e.g. hold out a
            generator from training so it stays 'unseen' for cross-generator eval).
        only_generators: if set, keep ONLY these generators (reals are always kept).
        manifest_name: which manifest file to load (train uses manifest_train.json).
        """
        self.data_dir = Path(data_dir)
        manifest_path = self.data_dir / manifest_name

        if not manifest_path.exists():
            raise FileNotFoundError(f"{manifest_name} not found in {data_dir}")

        with open(manifest_path) as f:
            self.manifest = json.load(f)

        exclude = set(exclude_generators or [])
        only = set(only_generators or [])

        def keep(m):
            gen = m.get("generator", "human")
            if m["label"] == 0:
                return True  # always keep real speech
            if exclude and gen in exclude:
                return False
            if only and gen not in only:
                return False
            return True

        if exclude or only:
            before = len(self.manifest)
            self.manifest = [m for m in self.manifest if keep(m)]
            print(f"Generator filter: exclude={sorted(exclude)} only={sorted(only)} "
                  f"({before} -> {len(self.manifest)} samples)")

        print(f"Loaded dataset: {len(self.manifest)} samples")
        labels = [m["label"] for m in self.manifest]
        print(f"  Real: {labels.count(0)}, Fake: {labels.count(1)}")

    def __len__(self):
        return len(self.manifest)

    def __getitem__(self, idx) -> Tuple[torch.Tensor, torch.Tensor, int]:
        entry = self.manifest[idx]
        filepath = self.data_dir / entry["path"]
        label = entry["label"]

        # Load the pre-processed 8kHz audio with robust fallback
        try:
            waveform, sr = torchaudio.load(str(filepath))
        except Exception:
            from scipy.io import wavfile
            sr, data_np = wavfile.read(str(filepath))
            if data_np.dtype == np.int16:
                data_float = data_np.astype(np.float32) / 32768.0
            else:
                data_float = data_np.astype(np.float32)
            waveform = torch.from_numpy(data_float).unsqueeze(0)
            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)

        waveform = pad_or_trim(waveform, WINDOW_SAMPLES_8K)

        # Compute mel-spectrogram for CNN branch
        mel = compute_mel_spectrogram(waveform, sr=TELEPHONY_SR)

        # Upsample to 16kHz for wav2vec2 branch
        waveform_16k = resample(waveform, TELEPHONY_SR, MODEL_SR)
        waveform_16k = pad_or_trim(waveform_16k, WINDOW_SAMPLES_16K)

        return waveform_16k.squeeze(0), mel.squeeze(0), label


# ──────────────────────────────────────────────────────────────────────
# Training Loop
# ──────────────────────────────────────────────────────────────────────

def train_mel_cnn(
    dataset: VoiceShieldDataset,
    epochs: int = 30,
    batch_size: int = 16,
    lr: float = 1e-3,
    output_dir: str = "./ai/models",
    val_split: float = 0.2,
):
    """Train the MelCNN branch on mel-spectrograms."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n{'='*60}")
    print(f"Training MelCNN on {device}")
    print(f"{'='*60}")

    # Split dataset
    val_size = int(len(dataset) * val_split)
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # Model
    model = MelCNN().to(device)
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    os.makedirs(output_dir, exist_ok=True)

    for epoch in range(epochs):
        # ── Train ──
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0

        for waveform_16k, mel, labels in train_loader:
            mel = mel.unsqueeze(1).to(device)  # (B, 1, n_mels, T)
            labels = labels.float().to(device)

            optimizer.zero_grad()
            preds = model(mel)
            loss = criterion(preds, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * labels.size(0)
            train_correct += ((preds > 0.5).float() == labels).sum().item()
            train_total += labels.size(0)

        scheduler.step()

        # ── Validate ──
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for waveform_16k, mel, labels in val_loader:
                mel = mel.unsqueeze(1).to(device)
                labels = labels.float().to(device)
                preds = model(mel)
                loss = criterion(preds, labels)
                val_loss += loss.item() * labels.size(0)
                val_correct += ((preds > 0.5).float() == labels).sum().item()
                val_total += labels.size(0)

        train_acc = train_correct / max(train_total, 1) * 100
        val_acc = val_correct / max(val_total, 1) * 100

        print(
            f"Epoch {epoch+1:3d}/{epochs} | "
            f"Train Loss: {train_loss/max(train_total,1):.4f} Acc: {train_acc:.1f}% | "
            f"Val Loss: {val_loss/max(val_total,1):.4f} Acc: {val_acc:.1f}%"
        )

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_path = os.path.join(output_dir, "best_mel_cnn.pt")
            torch.save(model.state_dict(), save_path)
            print(f"  [OK] Saved best MelCNN (val_acc={val_acc:.1f}%) -> {save_path}")

    print(f"\nMelCNN training complete. Best val accuracy: {best_val_acc:.1f}%")
    return model


def train_wav2vec_head(
    dataset: VoiceShieldDataset,
    epochs: int = 20,
    batch_size: int = 8,
    lr: float = 5e-4,
    output_dir: str = "./ai/models",
    val_split: float = 0.2,
):
    """
    Train the wav2vec2 classifier head.
    The wav2vec2 backbone is FROZEN — only the head is trained.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n{'='*60}")
    print(f"Training wav2vec2 Classifier Head on {device}")
    print(f"{'='*60}")

    try:
        from transformers import Wav2Vec2Model
    except ImportError:
        print("[ERROR] transformers not installed. Run: pip install transformers")
        return None

    # Load backbone (frozen)
    print("Loading wav2vec2-large-xlsr-53 backbone (this may take a minute)...")
    backbone = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-large-xlsr-53")
    backbone.eval()
    for param in backbone.parameters():
        param.requires_grad = False
    backbone.to(device)
    hidden_size = backbone.config.hidden_size

    # Split dataset
    val_size = int(len(dataset) * val_split)
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # Head only
    head = Wav2Vec2ClassifierHead(input_dim=hidden_size).to(device)
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(head.parameters(), lr=lr, weight_decay=1e-4)

    best_val_acc = 0.0
    os.makedirs(output_dir, exist_ok=True)

    for epoch in range(epochs):
        head.train()
        train_loss, train_correct, train_total = 0.0, 0, 0

        for waveform_16k, mel, labels in train_loader:
            waveform_16k = waveform_16k.to(device)
            labels = labels.float().to(device)

            optimizer.zero_grad()

            with torch.no_grad():
                hidden_states = backbone(waveform_16k).last_hidden_state  # (B, seq, hidden)

            preds = head(hidden_states)
            loss = criterion(preds, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * labels.size(0)
            train_correct += ((preds > 0.5).float() == labels).sum().item()
            train_total += labels.size(0)

        # Validate
        head.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for waveform_16k, mel, labels in val_loader:
                waveform_16k = waveform_16k.to(device)
                labels = labels.float().to(device)
                hidden_states = backbone(waveform_16k).last_hidden_state
                preds = head(hidden_states)
                loss = criterion(preds, labels)
                val_loss += loss.item() * labels.size(0)
                val_correct += ((preds > 0.5).float() == labels).sum().item()
                val_total += labels.size(0)

        train_acc = train_correct / max(train_total, 1) * 100
        val_acc = val_correct / max(val_total, 1) * 100

        print(
            f"Epoch {epoch+1:3d}/{epochs} | "
            f"Train Loss: {train_loss/max(train_total,1):.4f} Acc: {train_acc:.1f}% | "
            f"Val Loss: {val_loss/max(val_total,1):.4f} Acc: {val_acc:.1f}%"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_path = os.path.join(output_dir, "best_wav2vec_head.pt")
            torch.save(head.state_dict(), save_path)
            print(f"  ✓ Saved best wav2vec head (val_acc={val_acc:.1f}%) → {save_path}")

    print(f"\nwav2vec2 head training complete. Best val accuracy: {best_val_acc:.1f}%")
    return head


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train VoiceShield classifiers")
    parser.add_argument("--data_dir", type=str, default="./data", help="Dataset directory")
    parser.add_argument("--output_dir", type=str, default="./ai/models", help="Where to save weights")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--cnn_only", action="store_true", help="Train only the MelCNN (skip wav2vec2)")
    parser.add_argument("--holdout_generator", type=str, default=None,
                        help="Generator to EXCLUDE from training (e.g. 'xtts_v2') so it stays "
                             "unseen — then evaluate on it to PROVE cross-generator generalization")
    args = parser.parse_args()

    exclude = [args.holdout_generator] if args.holdout_generator else None
    if exclude:
        print(f"\n[cross-generator] Holding out '{args.holdout_generator}' from training.\n"
              f"After training, run:\n"
              f"  python -m ai.train.evaluate --data_dir {args.data_dir} "
              f"--weights_dir {args.output_dir} --only_generator {args.holdout_generator}\n")
    # Prefer the held-out training split so evaluation stays honest.
    train_manifest = "manifest_train.json" if (Path(args.data_dir) / "manifest_train.json").exists() else "manifest.json"
    if train_manifest == "manifest.json":
        print("[WARN] manifest_train.json not found — training on full manifest "
              "(rebuild dataset to get an honest held-out test set).")
    dataset = VoiceShieldDataset(args.data_dir, exclude_generators=exclude, manifest_name=train_manifest)

    # Train CNN first (faster, no large backbone needed)
    train_mel_cnn(dataset, epochs=args.epochs, batch_size=args.batch_size, output_dir=args.output_dir)

    # Train wav2vec2 head (needs GPU ideally)
    if not args.cnn_only:
        train_wav2vec_head(dataset, epochs=min(args.epochs, 20), batch_size=8, output_dir=args.output_dir)
    else:
        print("\n[SKIP] wav2vec2 head training (--cnn_only flag)")

    print("\n[SUCCESS] All training complete! Weights saved to:", args.output_dir)
