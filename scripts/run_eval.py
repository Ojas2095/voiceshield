"""
VoiceShield - Unified Acceptance Evaluation Suite (Phase D)
============================================================
Single unified test gate that runs all acceptance test suites:
1. Stage 1: Layer 2 Scam-Intent Acceptance Suite (87 test cases, pair-completeness validation)
2. Stage 2: Layer 1 Voice Authenticity Diversity Sweep (AI clones, human dialogues, human scam scripts, held-out speech)
3. Stage 3: Live End-to-End Multi-Modal Integration Check (live WebSocket streaming, ASR, fusion, hold triggers)

Run:
    python scripts/run_eval.py
or
    make eval

Exit code: 0 if ALL stages pass, 1 if ANY stage fails.
"""
import sys
import subprocess
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_stage(title: str, cmd: list[str]) -> tuple[bool, float, str]:
    print("\n" + "=" * 80)
    print(f"▶ RUNNING {title}")
    print("=" * 80)
    t0 = time.time()
    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.time() - t0

    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    ok = (res.returncode == 0)
    status_str = "SUCCESS" if ok else f"FAILED (code {res.returncode})"
    print(f"✔ {title}: {status_str} in {elapsed:.2f}s")
    return ok, elapsed, res.stdout


def main():
    print("\n" + "#" * 80)
    print("# VOICESHIELD UNIFIED ACCEPTANCE & CONVERGENCE EVALUATION")
    print("#" * 80)

    stages = [
        ("STAGE 1: Layer 2 Scam-Intent Systematic Matrix & Hard Negatives", [sys.executable, "scripts/test_scam_intent.py"]),
        ("STAGE 2: Layer 1 Voice Authenticity Diversity Sweep", [sys.executable, "scripts/evaluate_voice_diversity.py"]),
        ("STAGE 3: Live End-to-End Multi-Modal Integration Check", [sys.executable, "tests/deep_check_all_modalities.py"]),
    ]

    results = []
    overall_start = time.time()

    for title, cmd in stages:
        ok, elapsed, _ = run_stage(title, cmd)
        results.append((title, ok, elapsed))
        if not ok:
            print(f"\n❌ Pipeline failed early at {title}!")
            break

    total_time = time.time() - overall_start

    print("\n" + "=" * 80)
    print("UNIFIED EVALUATION REPORT SUMMARY")
    print("=" * 80)
    all_passed = True
    for title, ok, elapsed in results:
        status_tag = "PASS" if ok else "FAIL"
        if not ok:
            all_passed = False
        print(f"  [{status_tag:4}] {title:<65} ({elapsed:.2f}s)")

    print("-" * 80)
    print(f"Total Evaluation Time: {total_time:.2f}s")

    if all_passed and len(results) == len(stages):
        print("\n🎉 ALL ACCEPTANCE GATES PASSED: SYSTEM FULLY CONVERGED AND READY FOR PRODUCTION/MERGE!\n")
        sys.exit(0)
    else:
        print("\n❌ GATING FAILED: RESOLVE FAILURES BEFORE MERGING OR DEPLOYING!\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
