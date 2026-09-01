"""
VoiceShield — Intent Classifier Benchmark & Evaluation (Task 2.4)
==================================================================
Evaluates Layer 2 conversation intent scoring across multilingual
English, Hinglish, and Hindi scam samples.

Usage:
    python -m intelligence.eval_intent
"""
import csv
import os
import sys
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from intelligence.intent_classifier import score_intent


def run_evaluation(csv_path: str = None, default_threshold: float = 0.35):
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "data", "intent_samples.csv")

    if not os.path.exists(csv_path):
        print(f"[ERROR] Dataset not found at: {csv_path}")
        return

    print("=" * 65)
    print("VoiceShield — Layer 2 Intent Classifier Benchmark")
    print("=" * 65)

    y_true = []
    y_scores = []
    texts = []
    langs = []
    categories = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row["text"].strip()
            label = int(row["label"].strip())
            lang = row.get("language", "unknown").strip()
            cat = row.get("category", "unknown").strip()

            result = score_intent(text)
            score = float(result.get("intent_risk", 0.0))

            texts.append(text)
            y_true.append(label)
            y_scores.append(score)
            langs.append(lang)
            categories.append(cat)

    y_true = np.array(y_true)
    y_scores = np.array(y_scores)

    total_samples = len(y_true)
    scam_count = int(np.sum(y_true == 1))
    benign_count = int(np.sum(y_true == 0))

    print(f"Total Samples: {total_samples} (Scam: {scam_count}, Benign: {benign_count})")
    print(f"Languages: {sorted(list(set(langs)))}")

    # ── Performance at default threshold ──
    y_pred = (y_scores >= default_threshold).astype(int)

    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))

    accuracy = (tp + tn) / max(total_samples, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * (precision * recall) / max(precision + recall, 1e-8)

    print("-" * 65)
    print(f"Metrics @ Threshold = {default_threshold:.2f}:")
    print(f"  Accuracy:  {accuracy * 100:.2f}%")
    print(f"  Precision: {precision * 100:.2f}%")
    print(f"  Recall:    {recall * 100:.2f}%")
    status_str = "[PASS] target >= 0.85" if f1 >= 0.85 else "[WARN] NEED TUNING"
    print(f"  F1 Score:  {f1:.4f}  ({status_str})")
    print(f"  Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")

    # ── Breakdown by Language ──
    print("-" * 65)
    print("Breakdown by Language:")
    for lang in sorted(list(set(langs))):
        idx = [i for i, l in enumerate(langs) if l == lang]
        l_true = y_true[idx]
        l_pred = y_pred[idx]
        l_acc = np.mean(l_true == l_pred) * 100
        print(f"  - {lang.upper():8s} ({len(idx):2d} samples): {l_acc:.1f}% accuracy")

    # ── Sweep for optimal threshold ──
    best_f1, best_t = 0.0, default_threshold
    for t in np.linspace(0.1, 0.9, 81):
        pred = (y_scores >= t).astype(int)
        p = np.sum((pred == 1) & (y_true == 1)) / max(np.sum(pred == 1), 1)
        r = np.sum((pred == 1) & (y_true == 1)) / max(np.sum(y_true == 1), 1)
        score_f1 = 2 * (p * r) / max(p + r, 1e-8)
        if score_f1 > best_f1:
            best_f1 = score_f1
            best_t = t

    print("-" * 65)
    print(f"Optimal Threshold: {best_t:.2f} (Yields Max F1: {best_f1:.4f})")
    print("=" * 65)


if __name__ == "__main__":
    run_evaluation()
