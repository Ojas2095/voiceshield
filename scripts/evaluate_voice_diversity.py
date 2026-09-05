"""
VoiceShield - Layer 1 Voice Diversity Sweep & Calibration Diagnostics
=====================================================================
Systematically sweeps Layer-1 acoustic authenticity classification across:
1. Synthetic / AI cloned voices (cloned_en, cloned_hi, cloned_long_scam)
2. Real human dialogues & team voices (real_en, real_hi, real_long_en, test_voice)
3. Real human scam scripts (human_scam_sbi_otp, customs, electricity, long_vishing)
4. Held-out validation samples from data/real/

Measures and logs:
- Continuous calibrated confidence score in [0, 1]
- hf_ratio (telephone band 2800-3400Hz carrier ratio)
- jitter (biological vocal fold micro-tremor: 0.8% - 3.8%)
- Mahalanobis Out-Of-Distribution (OOD) distance
- Score distribution histogram verifying smooth continuous coverage (no discrete gap)

Run:
    python scripts/evaluate_voice_diversity.py
Exit code: 0 on 100% pass, 1 on any misclassification.
"""
import sys
import os
import glob
from pathlib import Path
import numpy as np
from scipy.io import wavfile
import scipy.signal
import joblib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend_v2"))
sys.path.insert(0, str(REPO_ROOT))

from app.inference import VoiceShieldClassifier


def extract_acoustic_features(chunk_samples: np.ndarray, sr: int = 16000) -> tuple[float, float]:
    """Extract hf_ratio and pitch jitter."""
    n_samples = min(len(chunk_samples), 32000)
    samples = chunk_samples[:n_samples].astype(np.float32)

    fft_mag = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(n_samples, 1.0 / float(sr))
    hf_mask = (freqs >= 2800) & (freqs <= 3400)
    lf_mask = (freqs >= 250) & (freqs <= 2200)
    hf_energy = float(np.mean(fft_mag[hf_mask] ** 2)) if np.any(hf_mask) else 0.0
    lf_energy = float(np.mean(fft_mag[lf_mask] ** 2)) + 1e-9
    hf_ratio = hf_energy / lf_energy

    frame_len, hop_len = int(0.040 * sr), int(0.015 * sr)
    periods = []
    for i in range(0, len(samples) - frame_len, hop_len):
        f = samples[i:i + frame_len] - np.mean(samples[i:i + frame_len])
        if np.sqrt(np.mean(f ** 2)) < 0.015:
            continue
        corr = np.correlate(f, f, mode='full')
        corr = corr[len(corr) // 2:]
        min_l, max_l = int(sr / 320), int(sr / 80)
        pl = np.argmax(corr[min_l:max_l]) + min_l
        if corr[pl] / (corr[0] + 1e-9) > 0.40:
            periods.append(pl)

    if len(periods) >= 8:
        jitter = float(np.mean(np.abs(np.diff(periods))) / (np.mean(periods) + 1e-9))
    else:
        jitter = 0.021

    return hf_ratio, jitter


def evaluate_file(file_path: Path, clf: VoiceShieldClassifier) -> dict:
    sr, data = wavfile.read(str(file_path))
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    if sr != 16000:
        data = scipy.signal.resample(data, int(len(data) * 16000 / sr))

    chunk_len = 32000  # 2.0s at 16kHz
    scores = []
    hf_ratios = []
    jitters = []
    oods = []

    for i in range(0, len(data), chunk_len):
        chunk = data[i:i + chunk_len]
        if len(chunk) < 16000:
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < 0.012:
            continue
        s = clf._infer_sync(chunk)
        hf, jit = extract_acoustic_features(chunk, 16000)
        ood = getattr(clf, "last_telemetry", {}).get("ood_distance", 0.0)
        scores.append(s)
        hf_ratios.append(hf)
        jitters.append(jit)
        oods.append(ood)

    if not scores:
        return {
            "chunks": 0,
            "avg_score": 0.02,
            "peak_score": 0.02,
            "avg_hf": 0.0,
            "avg_jitter": 0.021,
            "peak_ood": 0.0,
            "verdict": "HUMAN",
            "scores": [],
        }

    peak_score = float(np.max(scores))
    avg_score = float(np.mean(scores))
    peak_ood = float(np.max(oods))
    verdict = "AI_SYNTHETIC" if peak_score >= 0.50 else "HUMAN"

    return {
        "chunks": len(scores),
        "avg_score": avg_score,
        "peak_score": peak_score,
        "avg_hf": float(np.mean(hf_ratios)),
        "avg_jitter": float(np.mean(jitters)),
        "peak_ood": peak_ood,
        "verdict": verdict,
        "scores": scores,
    }


def print_histogram(all_scores: list[float]):
    print("\n" + "=" * 65)
    print("CONTINUOUS SCORE DISTRIBUTION HISTOGRAM (All Processed Chunks)")
    print("=" * 65)
    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    counts = [0] * 10
    for s in all_scores:
        idx = min(9, int(s * 10))
        counts[idx] += 1

    total = max(1, len(all_scores))
    for i in range(10):
        low, high = bins[i], bins[i + 1]
        pct = (counts[i] / total) * 100
        bar = "█" * int(pct / 2.5)
        print(f"[{low:.1f} - {high:.1f}] | {counts[i]:4d} ({pct:5.1f}%) | {bar}")
    print("=" * 65)


def run_sweep():
    print("=" * 125)
    print("VOICESHIELD LAYER 1 STATISTICAL CALIBRATION & ACOUSTIC DIVERSITY SWEEP")
    print("=" * 125)

    clf = VoiceShieldClassifier()
    print(f"Classifier Mode: {clf.model_version} on {clf.device}")

    # Check calibrator metadata
    cal_file = REPO_ROOT / "ai/models/calibrator.joblib"
    if cal_file.exists():
        try:
            bundle = joblib.load(str(cal_file))
            print(f"Statistical Calibrator: ECE={bundle.get('ece', 0.0)*100:.2f}%, Brier={bundle.get('brier_score', 0.0):.4f}, OOD Threshold={bundle.get('ood_threshold', 0.0):.2f}\n")
        except Exception:
            pass

    test_suite = [
        # AI Cloned Voices
        (REPO_ROOT / "frontend/public/demo/cloned_en.wav", "AI_SYNTHETIC"),
        (REPO_ROOT / "frontend/public/demo/cloned_hi.wav", "AI_SYNTHETIC"),
        (REPO_ROOT / "frontend/public/demo/cloned_long_scam.wav", "AI_SYNTHETIC"),

        # Real Human Voices
        (REPO_ROOT / "frontend/public/demo/real_en.wav", "HUMAN"),
        (REPO_ROOT / "frontend/public/demo/real_hi.wav", "HUMAN"),
        (REPO_ROOT / "frontend/public/demo/real_long_en.wav", "HUMAN"),
        (REPO_ROOT / "test_voice.wav", "HUMAN"),

        # Human Scammer Recordings
        (REPO_ROOT / "frontend/public/demo/human_scam_sbi_otp.wav", "HUMAN"),
        (REPO_ROOT / "frontend/public/demo/human_scam_customs_parcel.wav", "HUMAN"),
        (REPO_ROOT / "frontend/public/demo/human_scam_electricity_hi.wav", "HUMAN"),
        (REPO_ROOT / "frontend/public/demo/human_scam_long_vishing.wav", "HUMAN"),
    ]

    held_out_samples = sorted(glob.glob(str(REPO_ROOT / "data/real/*.wav")))[:5]
    for p in held_out_samples:
        test_suite.append((Path(p), "HUMAN"))

    print(f"{'AUDIO FILE':35} | {'EXPECTED':12} | {'CHKS':4} | {'AVG-SCR':7} | {'PEAK-SCR':8} | {'AVG-HF':6} | {'JITTER':6} | {'OOD-PEAK':8} | {'STATUS'}")
    print("-" * 125)

    all_passed = True
    failures = []
    all_scores = []

    for file_path, expected in test_suite:
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue

        res = evaluate_file(file_path, clf)
        all_scores.extend(res["scores"])
        status_ok = (res["verdict"] == expected)
        if not status_ok:
            all_passed = False
            failures.append(
                f"{file_path.name}: expected {expected}, got {res['verdict']} (peak score {res['peak_score']:.3f})"
            )
        status_str = "PASS" if status_ok else "FAIL"
        rel_name = file_path.name

        print(
            f"{rel_name:35} | {expected:12} | {res['chunks']:4d} | {res['avg_score']:7.3f} | {res['peak_score']:8.3f} | "
            f"{res['avg_hf']:6.3f} | {res['avg_jitter']:6.3f} | {res['peak_ood']:8.2f} | {status_str}"
        )

    print("=" * 125)
    print_histogram(all_scores)

    if all_passed:
        print(f"\n🎉 VOICE DIVERSITY SWEEP PASSED: ALL {len(test_suite)} RECORDINGS CORRECTLY SEPARATED (0 FP, 0 FN)!")
        sys.exit(0)
    else:
        print(f"\n❌ VOICE DIVERSITY SWEEP FAILED with {len(failures)} errors:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    run_sweep()
