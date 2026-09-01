"""
VoiceShield — Model Evaluation Script
======================================
Computes EER (Equal Error Rate), ROC-AUC, and inference latency benchmarks.
These numbers are GOLD during judge Q&A.

Usage:
    python -m ai.train.evaluate --data_dir ./data --weights_dir ./ai/models
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import torch
import torchaudio
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ai.preprocessing import preprocess_tensor, TELEPHONY_SR, WINDOW_SAMPLES_8K
from ai.layer1_authenticity import Layer1Detector


def load_evaluation_data(data_dir: str, only_generator: str = None) -> Tuple[List[torch.Tensor], List[torch.Tensor], List[int]]:
    """
    Load audio files and labels from the manifest.

    only_generator: if set, keep only fakes from THIS generator (reals always
        kept). Use it to measure cross-generator generalization on a generator
        that was held out of training.
    """
    data_path = Path(data_dir)
    manifest_path = data_path / "manifest.json"

    with open(manifest_path) as f:
        manifest = json.load(f)

    if only_generator:
        manifest = [m for m in manifest
                    if m["label"] == 0 or m.get("generator") == only_generator]

    waveforms_16k = []
    mels = []
    labels = []

    for entry in manifest:
        filepath = data_path / entry["path"]
        if not filepath.exists():
            continue

        waveform, sr = torchaudio.load(str(filepath))
        chunk = preprocess_tensor(waveform, source_sr=sr, apply_degradation=False)

        waveforms_16k.append(chunk.waveform_16k)
        mels.append(chunk.mel_spectrogram)
        labels.append(entry["label"])

    return waveforms_16k, mels, labels


def compute_eer(y_true: np.ndarray, y_scores: np.ndarray) -> Tuple[float, float]:
    """
    Compute Equal Error Rate (EER).
    EER is where False Acceptance Rate == False Rejection Rate.
    Lower EER = better model.
    """
    from sklearn.metrics import roc_curve

    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    fnr = 1 - tpr

    # Find the threshold where FPR ≈ FNR
    eer_index = np.nanargmin(np.abs(fpr - fnr))
    eer = float((fpr[eer_index] + fnr[eer_index]) / 2)
    eer_threshold = float(thresholds[eer_index])

    return eer, eer_threshold


def evaluate(data_dir: str, weights_dir: str, device: str = "cpu", only_generator: str = None):
    """Run full evaluation and print results."""
    print("=" * 60)
    print("VoiceShield — Model Evaluation")
    if only_generator:
        print(f"CROSS-GENERATOR mode: fakes limited to unseen generator '{only_generator}'")
    print("=" * 60)

    # Load model
    detector = Layer1Detector(device=device)

    head_path = os.path.join(weights_dir, "best_wav2vec_head.pt")
    cnn_path = os.path.join(weights_dir, "best_mel_cnn.pt")

    if os.path.exists(head_path) and os.path.exists(cnn_path):
        detector.load_weights(head_path, cnn_path)
        print(f"✓ Loaded weights from {weights_dir}")
    else:
        print(f"⚠ Weights not found at {weights_dir}, evaluating with untrained model")

    # Load data
    print(f"\nLoading evaluation data from {data_dir}...")
    waveforms_16k, mels, labels = load_evaluation_data(data_dir, only_generator=only_generator)
    print(f"  Loaded {len(labels)} samples (Real: {labels.count(0)}, Fake: {labels.count(1)})")

    if len(labels) == 0:
        print("[ERROR] No evaluation data found")
        return

    # Run inference
    print("\nRunning inference...")
    scores = []
    latencies = []

    for i, (waveform_16k, mel) in enumerate(zip(waveforms_16k, mels)):
        start = time.perf_counter()
        result = detector.predict(waveform_16k, mel)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        scores.append(result["p_fake"])
        latencies.append(elapsed)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(labels)} samples")

    y_true = np.array(labels)
    y_scores = np.array(scores)

    # ── Metrics ──
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    # Accuracy at threshold 0.5
    y_pred = (y_scores >= 0.5).astype(int)
    accuracy = (y_pred == y_true).mean() * 100
    print(f"\n  Accuracy (threshold=0.5): {accuracy:.1f}%")

    # Precision, Recall, F1
    tp = ((y_pred == 1) & (y_true == 1)).sum()
    fp = ((y_pred == 1) & (y_true == 0)).sum()
    fn = ((y_pred == 0) & (y_true == 1)).sum()
    precision = tp / max(tp + fp, 1) * 100
    recall = tp / max(tp + fn, 1) * 100
    f1 = 2 * precision * recall / max(precision + recall, 1)
    print(f"  Precision: {precision:.1f}%")
    print(f"  Recall: {recall:.1f}%")
    print(f"  F1 Score: {f1:.1f}%")

    # ROC-AUC
    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(y_true, y_scores)
        print(f"  ROC-AUC: {auc:.4f}")
    except ImportError:
        print("  ROC-AUC: (install scikit-learn for this metric)")

    # EER
    eer, eer_threshold = None, None
    try:
        eer, eer_threshold = compute_eer(y_true, y_scores)
        print(f"  EER: {eer*100:.2f}% (threshold={eer_threshold:.4f})")
    except ImportError:
        print("  EER: (install scikit-learn for this metric)")

    # E5 — calibrate the operating threshold from the standard (mixed) eval and
    # persist it so the detector can replace its hardcoded 0.7/0.4 cut-offs.
    if eer_threshold is not None and not only_generator:
        try:
            thr_path = os.path.join(weights_dir, "threshold.json")
            with open(thr_path, "w") as f:
                json.dump({
                    "eer_threshold": round(float(eer_threshold), 4),
                    "eer": round(float(eer), 4),
                    "n_samples": int(len(labels)),
                    "note": "Operating threshold at Equal Error Rate; use in Layer1Detector verdict.",
                }, f, indent=2)
            print(f"  ✓ Saved calibrated threshold -> {thr_path}")
        except Exception as e:
            print(f"  [WARN] could not save threshold.json: {e}")

    # Latency
    latencies_np = np.array(latencies)
    print(f"\n  Inference Latency:")
    print(f"    Mean:   {latencies_np.mean():.1f} ms")
    print(f"    Median: {np.median(latencies_np):.1f} ms")
    print(f"    P95:    {np.percentile(latencies_np, 95):.1f} ms")
    print(f"    P99:    {np.percentile(latencies_np, 99):.1f} ms")

    target = 500
    under_target = (latencies_np < target).mean() * 100
    print(f"    Under {target}ms: {under_target:.1f}%")

    # ── Summary for Judges ──
    print(f"\n{'='*60}")
    print("JUDGE Q&A CHEAT SHEET (memorize these numbers)")
    print(f"{'='*60}")
    print(f'  "Our model achieves {accuracy:.0f}% accuracy with an EER of', end="")
    try:
        print(f' {eer*100:.1f}%"')
    except:
        print(' [pending]"')
    print(f'  "Inference latency is {latencies_np.mean():.0f}ms per 2-second window"')
    print(f'  "We tested on {len(labels)} audio samples ({labels.count(0)} real, {labels.count(1)} fake)"')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate VoiceShield model")
    parser.add_argument("--data_dir", type=str, default="./data", help="Dataset directory")
    parser.add_argument("--weights_dir", type=str, default="./ai/models", help="Model weights directory")
    parser.add_argument("--device", type=str, default="cpu", help="cpu or cuda")
    parser.add_argument("--only_generator", type=str, default=None,
                        help="Evaluate only on fakes from this (held-out) generator to measure "
                             "cross-generator generalization, e.g. --only_generator xtts_v2")
    args = parser.parse_args()

    evaluate(args.data_dir, args.weights_dir, args.device, only_generator=args.only_generator)
