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


def load_evaluation_data(data_dir: str, only_generator: str = None,
                         manifest_name: str = "manifest.json") -> Tuple[List[torch.Tensor], List[torch.Tensor], List[int]]:
    """
    Load audio files and labels from the manifest.

    manifest_name: which manifest to score (use manifest_test.json — the held-out
        split — for an honest EER; scoring manifest.json includes training data).
    only_generator: if set, keep only fakes from THIS generator (reals always
        kept). Use it to measure cross-generator generalization on a generator
        that was held out of training.
    """
    data_path = Path(data_dir)
    manifest_path = data_path / manifest_name

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

        chunk = preprocess_tensor(waveform, source_sr=sr, apply_degradation=False)

        waveforms_16k.append(chunk.waveform_16k)
        mels.append(chunk.mel_spectrogram)
        labels.append(entry["label"])

    return waveforms_16k, mels, labels


def load_asvspoof_data(asvspoof_dir: str, max_samples: int = 2000) -> Tuple[List[torch.Tensor], List[torch.Tensor], List[int]]:
    """
    Load ASVspoof 2019 / 2021 LA evaluation or development trial data.
    Looks for protocol metadata file (e.g. *.trl.txt or trial_metadata.txt) and flac/wav files.
    """
    asv_path = Path(asvspoof_dir)
    protocol_files = list(asv_path.rglob("*.txt"))

    protocol_file = None
    for pf in protocol_files:
        if "eval" in pf.name.lower() or "keys" in str(pf).lower() or "trial" in pf.name.lower():
            protocol_file = pf
            break
    if protocol_file is None and protocol_files:
        protocol_file = protocol_files[0]

    waveforms_16k = []
    mels = []
    labels = []

    if protocol_file:
        print(f"  Parsing ASVspoof protocol: {protocol_file.name}")
        with open(protocol_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        audio_files = {p.stem: p for p in asv_path.rglob("*.flac")}
        audio_files.update({p.stem: p for p in asv_path.rglob("*.wav")})

        count = 0
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            # Typical format: SPEAKER_ID AUDIO_FILE_NAME - - KEY (bonafide / spoof)
            file_id = parts[1]
            key = parts[-1].lower()

            if file_id in audio_files:
                label = 0 if key == "bonafide" else 1
                audio_path = audio_files[file_id]
                try:
                    waveform, sr = torchaudio.load(str(audio_path))
                    chunk = preprocess_tensor(waveform, source_sr=sr, apply_degradation=False)
                    waveforms_16k.append(chunk.waveform_16k)
                    mels.append(chunk.mel_spectrogram)
                    labels.append(label)
                    count += 1
                    if count >= max_samples:
                        break
                except Exception as e:
                    continue
    else:
        # Fallback: discover any flac/wav files in directories named 'bonafide' or 'spoof'
        for f in asv_path.rglob("*.*"):
            if f.suffix.lower() in [".flac", ".wav"]:
                label = 0 if "bonafide" in str(f).lower() or "real" in str(f).lower() else 1
                try:
                    waveform, sr = torchaudio.load(str(f))
                    chunk = preprocess_tensor(waveform, source_sr=sr, apply_degradation=False)
                    waveforms_16k.append(chunk.waveform_16k)
                    mels.append(chunk.mel_spectrogram)
                    labels.append(label)
                    if len(labels) >= max_samples:
                        break
                except Exception:
                    continue

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


def evaluate(data_dir: str = None, weights_dir: str = "./ai/models", device: str = "cpu", only_generator: str = None, asvspoof_dir: str = None, cnn_only: bool = False):
    """Run full evaluation and print results."""
    print("=" * 60)
    print("VoiceShield — Model Evaluation")
    if asvspoof_dir:
        print(f"ASVSPOOF BENCHMARK mode: loading ASVspoof dataset from '{asvspoof_dir}'")
    elif only_generator:
        print(f"CROSS-GENERATOR mode: fakes limited to unseen generator '{only_generator}'")
    print("=" * 60)

    # Load model
    wav2vec_name = None if cnn_only else "facebook/wav2vec2-large-xlsr-53"
    detector = Layer1Detector(wav2vec_model_name=wav2vec_name, device=device)

    head_path = os.path.join(weights_dir, "best_wav2vec_head.pt")
    cnn_path = os.path.join(weights_dir, "best_mel_cnn.pt")

    if os.path.exists(cnn_path):
        if os.path.exists(head_path) and not cnn_only:
            detector.load_weights(head_path, cnn_path)
            print(f"[OK] Loaded dual-branch weights from {weights_dir}")
        else:
            detector.mel_cnn.load_state_dict(torch.load(cnn_path, map_location=device, weights_only=True))
            detector.mel_cnn.eval()
            detector._weights_loaded = True
            print(f"[OK] Loaded MelCNN weights from {cnn_path}")
    else:
        print(f"[WARN] Weights not found at {weights_dir}, evaluating with untrained model")

    # Load data
    if asvspoof_dir:
        print(f"\nLoading ASVspoof evaluation data from {asvspoof_dir}...")
        waveforms_16k, mels, labels = load_asvspoof_data(asvspoof_dir)
    else:
        # Prefer the held-out test split so EER is NOT measured on training data.
        manifest_name = ("manifest_test.json"
                         if os.path.exists(os.path.join(data_dir, "manifest_test.json"))
                         else "manifest.json")
        if manifest_name == "manifest.json":
            print("[WARN] manifest_test.json not found — evaluating on the FULL manifest "
                  "(includes training data → EER will look near-0%. Rebuild the dataset.)")
        print(f"\nLoading evaluation data from {data_dir} ({manifest_name})...")
        waveforms_16k, mels, labels = load_evaluation_data(
            data_dir, only_generator=only_generator, manifest_name=manifest_name
        )

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
            print(f"  [OK] Saved calibrated threshold -> {thr_path}")
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
    parser.add_argument("--asvspoof_dir", type=str, default=None,
                        help="Path to ASVspoof 2019/2021 LA dataset folder containing protocols and audio files")
    parser.add_argument("--cnn_only", action="store_true",
                        help="Evaluate using only MelCNN branch without loading wav2vec2 backbone")
    args = parser.parse_args()

    evaluate(
        data_dir=args.data_dir,
        weights_dir=args.weights_dir,
        device=args.device,
        only_generator=args.only_generator,
        asvspoof_dir=args.asvspoof_dir,
        cnn_only=args.cnn_only,
    )
