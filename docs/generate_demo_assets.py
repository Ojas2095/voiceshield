"""
Generate Pitch Deck Assets & Grad-CAM Heatmap Comparison
"""
import os
import sys
import base64
import torch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai.layer1_authenticity import MelCNN
from ai.gradcam import GradCAMGenerator
from ai.preprocessing import compute_mel_spectrogram, TELEPHONY_SR
from ai.train.synthetic_seed import generate_human_like_audio, generate_ai_fake_like_audio, apply_telephony_degradation


def generate_assets():
    os.makedirs("docs", exist_ok=True)
    weights_path = "ai/models/best_mel_cnn.pt"
    
    model = MelCNN()
    if os.path.exists(weights_path):
        model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
        print(f"Loaded trained model from {weights_path}")
    model.eval()

    # Generate test audio
    real_audio = apply_telephony_degradation(generate_human_like_audio(), 16000)
    fake_audio = apply_telephony_degradation(generate_ai_fake_like_audio(), 16000)

    real_mel = compute_mel_spectrogram(real_audio, sr=TELEPHONY_SR)
    fake_mel = compute_mel_spectrogram(fake_audio, sr=TELEPHONY_SR)

    generator = GradCAMGenerator(model)
    b64_png = generator.generate_comparison(real_mel, fake_mel)

    out_path = "docs/gradcam_comparison.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64_png))

    print(f"[SUCCESS] Exported Grad-CAM demo visualization to: {out_path}")


if __name__ == "__main__":
    generate_assets()
