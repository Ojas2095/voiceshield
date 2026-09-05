"""
VoiceShield — Layer 1 Statistical Calibrator & OOD Detection Trainer (Track 2)
=============================================================================
Trains a logistic regression calibrator on [hf_ratio, jitter, raw_cnn] using:
1. Real Human Microphone & Clean Speech (Class 0: 0)
2. Synthetic / AI Neural Vocoder Clones (Class 1: 1)
3. Replayed / Telephony-Degraded Real Speech (Class 0: 0)

Computes:
- Calibrated logistic probability model
- Mahalanobis feature space distance (mean_vec, cov_inv)
- OOD threshold (95th percentile Mahalanobis distance)
- Expected Calibration Error (ECE) and Brier Score

Outputs:
    ai/models/calibrator.joblib
"""
import sys
import os
import glob
from pathlib import Path
import numpy as np
from scipy.io import wavfile
import scipy.signal
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from scipy.spatial.distance import mahalanobis
import joblib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend_v2"))
sys.path.insert(0, str(REPO_ROOT))

from app.inference import VoiceShieldClassifier
from ai.preprocessing import apply_telephony_degradation


def extract_features(chunk: np.ndarray, clf: VoiceShieldClassifier, sr: int = 16000) -> list[float]:
    n_samples = min(len(chunk), 32000)
    samples = chunk[:n_samples].astype(np.float32)

    # 1. HF/LF Ratio
    fft_mag = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(n_samples, 1.0 / float(sr))
    hf_mask = (freqs >= 2800) & (freqs <= 3400)
    lf_mask = (freqs >= 250) & (freqs <= 2200)
    hf_energy = float(np.mean(fft_mag[hf_mask] ** 2)) if np.any(hf_mask) else 0.0
    lf_energy = float(np.mean(fft_mag[lf_mask] ** 2)) + 1e-9
    hf_ratio = hf_energy / lf_energy

    # 2. Pitch Jitter
    frame_len, hop_len = int(0.040 * sr), int(0.015 * sr)
    periods = []
    for j in range(0, len(samples) - frame_len, hop_len):
        f = samples[j:j + frame_len] - np.mean(samples[j:j + frame_len])
        if np.sqrt(np.mean(f ** 2)) < 0.015:
            continue
        corr = np.correlate(f, f, mode='full')[len(f) - 1:]
        min_l, max_l = int(sr / 320), int(sr / 80)
        pl = np.argmax(corr[min_l:max_l]) + min_l
        if corr[pl] / (corr[0] + 1e-9) > 0.40:
            periods.append(pl)
    if len(periods) >= 8:
        jitter = float(np.mean(np.abs(np.diff(periods))) / (np.mean(periods) + 1e-9))
    else:
        jitter = 0.021

    # 3. MelCNN score
    w8 = clf._resample(torch.from_numpy(chunk).unsqueeze(0), 16000, 8000)
    w8 = clf._pad_or_trim(w8, 16000)
    mel = clf._compute_mel(w8, sr=8000).unsqueeze(0).to(clf.device)
    with torch.no_grad():
        raw_cnn = float(clf.mel_cnn(mel).squeeze().item())

    return [hf_ratio, jitter, raw_cnn]


def process_audio_file(file_path: Path, clf: VoiceShieldClassifier) -> list[list[float]]:
    sr, data = wavfile.read(str(file_path))
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    if sr != 16000:
        data = scipy.signal.resample(data, int(len(data) * 16000 / sr))

    chunk_len = 32000
    features = []
    for i in range(0, len(data), chunk_len):
        chunk = data[i:i + chunk_len]
        if len(chunk) < 16000:
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < 0.012:
            continue
        features.append(extract_features(chunk, clf, 16000))
    return features


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bin_limits = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total_samples = len(y_true)

    print(f"\n{'BIN RANGE':15} | {'COUNT':6} | {'AVG CONF':10} | {'ACCURACY':10} | {'CALIB ERROR'}")
    print("-" * 65)

    for i in range(n_bins):
        bin_low, bin_high = bin_limits[i], bin_limits[i + 1]
        mask = (y_prob >= bin_low) & (y_prob < bin_high) if i < n_bins - 1 else (y_prob >= bin_low) & (y_prob <= bin_high)
        bin_count = np.sum(mask)
        if bin_count == 0:
            continue

        bin_conf = np.mean(y_prob[mask])
        bin_acc = np.mean(y_true[mask])
        diff = abs(bin_conf - bin_acc)
        ece += (bin_count / total_samples) * diff
        print(f"[{bin_low:.1f} - {bin_high:.1f}]   | {bin_count:6d} | {bin_conf:10.4f} | {bin_acc:10.4f} | {diff:10.4f}")

    print("-" * 65)
    return float(ece)


def main():
    print("=" * 75)
    print("VOICESHIELD: TRAINING STATISTICAL CALIBRATOR WITH OOD AWARENESS")
    print("=" * 75)

    clf = VoiceShieldClassifier()
    print(f"Initialized base classifier ({clf.model_version} on {clf.device}).\n")

    X, y, class_tags = [], [], []

    # 1. AI Synthetic Clones
    ai_paths = list((REPO_ROOT / "frontend/public/demo").glob("cloned_*.wav"))
    print(f"Processing {len(ai_paths)} AI clone audio files...")
    for p in ai_paths:
        feats = process_audio_file(p, clf)
        for f in feats:
            X.append(f)
            y.append(1)
            class_tags.append("ai_clone")

    # 2. Real Human Speech (Clean & Telephony)
    real_paths = (
        list((REPO_ROOT / "frontend/public/demo").glob("real_*.wav")) +
        list((REPO_ROOT / "frontend/public/demo").glob("human_scam_*.wav")) +
        [REPO_ROOT / "test_voice.wav"] +
        sorted(list((REPO_ROOT / "data/real").glob("*.wav")))[:40]
    )
    print(f"Processing {len(real_paths)} real human speech files...")
    for p in real_paths:
        if p.exists():
            feats = process_audio_file(p, clf)
            for f in feats:
                X.append(f)
                y.append(0)
                class_tags.append("real_human")

    # 3. Replayed / Acoustic Degraded Real Audio (YouTube / Speaker Re-recording pass)
    print("Generating replayed/degraded audio feature samples...")
    for p in list((REPO_ROOT / "frontend/public/demo").glob("real_*.wav")):
        sr, data = wavfile.read(str(p))
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        t_deg = apply_telephony_degradation(torch.from_numpy(data).unsqueeze(0), 16000).squeeze().numpy()
        chunk_len = 32000
        for i in range(0, len(t_deg), chunk_len):
            chunk = t_deg[i:i + chunk_len]
            if len(chunk) < 16000:
                continue
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if rms < 0.012:
                continue
            X.append(extract_features(chunk, clf, 16000))
            y.append(0)  # Replayed speech is NOT fake
            class_tags.append("replayed_human")

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int32)
    print(f"\nFeature matrix assembled: {X.shape[0]} samples x {X.shape[1]} features")
    print(f"  - Synthetic AI Clones: {np.sum(y == 1)}")
    print(f"  - Real & Replayed Human Speech: {np.sum(y == 0)}")

    # Fit Logistic Calibrator
    calibrator = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
    calibrator.fit(X, y)
    probs = calibrator.predict_proba(X)[:, 1]

    # Compute Mahalanobis Distribution for Out-of-Distribution (OOD) Detection
    mean_vec = np.mean(X, axis=0)
    cov = np.cov(X, rowvar=False)
    cov_inv = np.linalg.pinv(cov + 1e-6 * np.eye(X.shape[1]))

    distances = [mahalanobis(x, mean_vec, cov_inv) for x in X]
    ood_threshold = float(np.percentile(distances, 95))

    brier = brier_score_loss(y, probs)
    ece = compute_ece(y, probs)

    print("\nCALIBRATION DIAGNOSTICS:")
    print(f"  Logistic Weights [hf, jitter, cnn]: {calibrator.coef_[0].round(4)}")
    print(f"  Logistic Intercept:                {calibrator.intercept_[0]:.4f}")
    print(f"  Brier Score Loss:                  {brier:.6f} (lower is better, 0.00 is perfect)")
    print(f"  Expected Calibration Error (ECE):   {ece:.4f} ({ece*100:.2f}%)")
    print(f"  Mahalanobis 95th Percentile (OOD): {ood_threshold:.4f}")

    # Save Calibrator Artifact
    out_dir = REPO_ROOT / "ai" / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    calibrator_bundle = {
        "model": calibrator,
        "mean_vec": mean_vec,
        "cov_inv": cov_inv,
        "ood_threshold": ood_threshold,
        "brier_score": brier,
        "ece": ece,
    }
    joblib.dump(calibrator_bundle, str(out_dir / "calibrator.joblib"))
    print(f"\n✔ Successfully saved trained statistical calibrator to {out_dir / 'calibrator.joblib'}")


if __name__ == "__main__":
    main()
