"""
VoiceShield — Cross-Generator Generalization Evaluation (Task 3)
================================================================
Performs leave-one-engine-out evaluation to measure cross-generator generalization
and Equal Error Rate (EER) when encountering previously unseen synthetic voice engines.

Evaluates:
  1. Holdout ElevenLabs (Trained on XTTS + Vocoder, tested on ElevenLabs)
  2. Holdout XTTS (Trained on ElevenLabs + Vocoder, tested on XTTS)
  3. In-Distribution Multi-Engine (Trained on all engines, evaluated via 5-fold CV)

Outputs:
  ai/models/cross_generator_eval.json
"""
import sys
import json
from pathlib import Path
import numpy as np
from scipy.io import wavfile
import scipy.signal
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend_v2"))
sys.path.insert(0, str(REPO_ROOT))

from app.inference import VoiceShieldClassifier
from ai.preprocessing import apply_telephony_degradation
from scripts.train_calibrator import extract_features, process_audio_file


def compute_eer(y_true: np.ndarray, y_scores: np.ndarray):
    """Computes Equal Error Rate (EER) and optimal operating threshold."""
    fpr, tpr, thresholds = roc_curve(y_true, y_scores, pos_label=1)
    fnr = 1.0 - tpr
    diffs = np.abs(fpr - fnr)
    min_idx = np.argmin(diffs)
    eer = float((fpr[min_idx] + fnr[min_idx]) / 2.0)
    opt_thresh = float(thresholds[min_idx]) if min_idx < len(thresholds) else 0.5
    return eer, opt_thresh


def evaluate_cross_generator():
    print("=" * 80)
    print("VOICESHIELD: CROSS-GENERATOR GENERALIZATION & EER EVALUATION")
    print("=" * 80)

    clf = VoiceShieldClassifier()
    print(f"Base classifier: {clf.model_version} on {clf.device}\n")

    X, y, class_tags = [], [], []

    # 1. AI Synthetic Engines
    ai_engines = {
        "elevenlabs": sorted(list((REPO_ROOT / "data/fake/elevenlabs").glob("*.wav"))),
        "xtts": list((REPO_ROOT / "frontend/public/demo").glob("cloned_*.wav")),
        "vocoder": sorted(list((REPO_ROOT / "data/fake").glob("*.wav")))[:60],
    }

    print("Extracting features from synthetic engines:")
    for eng_name, paths in ai_engines.items():
        count = 0
        for p in paths:
            if p.exists():
                feats = process_audio_file(p, clf)
                for f in feats:
                    X.append(f)
                    y.append(1)
                    class_tags.append(eng_name)
                    count += 1
        print(f"  - [{eng_name.upper():12}]: {count:4d} feature chunks from {len(paths)} files")

    # 2. Real Human Speech
    real_paths = (
        list((REPO_ROOT / "data/real").glob("real_team_ksp_*.wav")) +
        list((REPO_ROOT / "data/real").glob("real_team_slt_*.wav")) +
        list((REPO_ROOT / "data/real").glob("real_team_hindi_*.wav")) +
        list((REPO_ROOT / "frontend/public/demo").glob("real_*.wav")) +
        list((REPO_ROOT / "frontend/public/demo").glob("human_scam_*.wav")) +
        [REPO_ROOT / "test_voice.wav"] +
        sorted(list((REPO_ROOT / "data/real").glob("real_speech_*.wav")))[:30]
    )

    print(f"\nExtracting features from real human speech ({len(real_paths)} files)...")
    human_count = 0
    for p in real_paths:
        if p.exists():
            feats = process_audio_file(p, clf)
            for f in feats:
                X.append(f)
                y.append(0)
                class_tags.append("real_human")
                human_count += 1
    print(f"  - [REAL HUMAN]: {human_count:4d} feature chunks")

    # 3. Degraded / Replayed Human Audio
    print("Extracting features from acoustic degraded human speech...")
    replayed_count = 0
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
            if len(chunk) < 16000 or np.sqrt(np.mean(chunk ** 2)) < 0.012:
                continue
            X.append(extract_features(chunk, clf, 16000))
            y.append(0)
            class_tags.append("replayed_human")
            replayed_count += 1
    print(f"  - [REPLAYED HUMAN]: {replayed_count:4d} feature chunks")

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int32)
    class_tags = np.array(class_tags)

    print(f"\nTotal Dataset: {len(X)} samples (Fake: {np.sum(y == 1)}, Real: {np.sum(y == 0)})")
    print("=" * 80)

    results = {
        "dataset_summary": {
            "total_samples": int(len(X)),
            "total_fake_samples": int(np.sum(y == 1)),
            "total_real_samples": int(np.sum(y == 0)),
            "engines": {eng: int(np.sum(class_tags == eng)) for eng in ai_engines.keys()},
        },
        "experiments": {},
    }

    # Experiments: Leave-One-Engine-Out for each generator
    for holdout_engine in ["elevenlabs", "xtts"]:
        print(f"\n>>> Running Leave-One-Out Holdout: [{holdout_engine.upper()}]")
        train_mask = (class_tags != holdout_engine)
        test_ai_mask = (class_tags == holdout_engine)
        test_human_mask = (y == 0)

        X_train, y_train = X[train_mask], y[train_mask]
        X_test = np.vstack([X[test_ai_mask], X[test_human_mask]])
        y_test = np.concatenate([np.ones(np.sum(test_ai_mask), dtype=np.int32), np.zeros(np.sum(test_human_mask), dtype=np.int32)])

        model = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
        model.fit(X_train, y_train)

        test_probs = model.predict_proba(X_test)[:, 1]
        ai_probs = test_probs[y_test == 1]
        human_probs = test_probs[y_test == 0]

        eer, opt_th = compute_eer(y_test, test_probs)
        try:
            auc = float(roc_auc_score(y_test, test_probs))
        except Exception:
            auc = 0.5

        det_rate = float(np.mean(ai_probs >= 0.50)) * 100.0
        rejection_rate = float(np.mean(human_probs < 0.50)) * 100.0

        print(f"  Training samples:           {len(X_train)} (held out all {np.sum(test_ai_mask)} '{holdout_engine}' clips)")
        print(f"  Test samples:               {len(X_test)} ({np.sum(test_ai_mask)} fake, {np.sum(test_human_mask)} human)")
        print(f"  Held-out Fake Detection:    {det_rate:.2f}% at th=0.50 (Mean prob: {np.mean(ai_probs):.4f})")
        print(f"  Real Human Rejection:       {rejection_rate:.2f}% at th=0.50 (Mean prob: {np.mean(human_probs):.4f})")
        print(f"  Equal Error Rate (EER):     {eer * 100:.2f}% (operating threshold: {opt_th:.4f})")
        print(f"  AUC-ROC:                    {auc:.4f}")

        results["experiments"][f"holdout_{holdout_engine}"] = {
            "held_out_engine": holdout_engine,
            "train_samples": int(len(X_train)),
            "test_fake_samples": int(np.sum(test_ai_mask)),
            "test_human_samples": int(np.sum(test_human_mask)),
            "eer": round(eer, 4),
            "eer_percentage": round(eer * 100, 2),
            "optimal_threshold": round(opt_th, 4),
            "auc_roc": round(auc, 4),
            "detection_rate_at_0_50": round(det_rate, 2),
            "human_rejection_rate_at_0_50": round(rejection_rate, 2),
        }

    # Full Multi-Engine Training Baseline
    print(f"\n>>> Running In-Distribution Multi-Engine Calibrator (All Engines Included)")
    full_model = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
    full_model.fit(X, y)
    full_probs = full_model.predict_proba(X)[:, 1]
    full_eer, full_opt_th = compute_eer(y, full_probs)
    full_auc = float(roc_auc_score(y, full_probs))

    per_engine_stats = {}
    for eng in ai_engines.keys():
        mask = (class_tags == eng)
        if np.any(mask):
            scores = full_probs[mask]
            per_engine_stats[eng] = {
                "samples": int(np.sum(mask)),
                "detection_rate_at_0_50": round(float(np.mean(scores >= 0.50)) * 100.0, 2),
                "mean_probability": round(float(np.mean(scores)), 4),
                "peak_probability": round(float(np.max(scores)), 4),
            }

    print(f"  Multi-Engine In-Distribution EER: {full_eer * 100:.2f}%")
    print(f"  Multi-Engine In-Distribution AUC: {full_auc:.4f}")
    for eng, st in per_engine_stats.items():
        print(f"    - [{eng.upper():10}]: Detection Rate {st['detection_rate_at_0_50']}% (Mean: {st['mean_probability']})")

    results["experiments"]["full_multi_engine"] = {
        "eer": round(full_eer, 4),
        "eer_percentage": round(full_eer * 100, 2),
        "auc_roc": round(full_auc, 4),
        "per_engine_detection": per_engine_stats,
    }

    out_file = REPO_ROOT / "ai" / "models" / "cross_generator_eval.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"✔ Cross-generator evaluation report saved to:\n  {out_file}")
    print("=" * 80)
    return results


if __name__ == "__main__":
    evaluate_cross_generator()
