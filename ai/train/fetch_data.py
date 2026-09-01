"""
VoiceShield — Real-Speech Fetcher  (Checklist item A1)
======================================================
Downloads a CONTROLLABLE SUBSET of real human speech to train on, using
HuggingFace `datasets` **streaming** so you never pull the full multi-GB corpus —
you get exactly `--per_lang` clips per language.

Sources
-------
  fleurs        Google FLEURS (CC-BY-4.0, NON-gated, 16kHz)  ← default, easiest
                Indian configs: hi_in, ta_in, bn_in, gu_in, mr_in, pa_in,
                                te_in, kn_in, ml_in, ur_pk ; English: en_us
  commonvoice   Mozilla Common Voice 17 (GATED — needs `huggingface-cli login`
                and accepting the dataset terms on the HF website first).
                Language codes: hi, ta, bn, en, ...

Output
------
  <out>/<lang>/<lang>_00000.wav , ...     (mono, native sample rate)
  These feed straight into `build_dataset.py --real_dir <out>`.

Examples
--------
  # Hindi + English, 300 clips each (good starter set)
  python -m ai.train.fetch_data --langs hi_in,en_us --per_lang 300 --out data/real_raw

  # Add Tamil + Bengali
  python -m ai.train.fetch_data --langs ta_in,bn_in --per_lang 200 --out data/real_raw

  # Common Voice Hindi (after `huggingface-cli login`)
  python -m ai.train.fetch_data --source commonvoice --langs hi --per_lang 300 --out data/real_raw
"""
import argparse
import sys
from pathlib import Path


def _lazy_imports():
    """Import heavy deps lazily with a friendly error if missing."""
    try:
        from datasets import load_dataset  # noqa
        import soundfile as sf  # noqa
        import numpy as np  # noqa
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("Install with:  pip install datasets soundfile numpy")
        sys.exit(1)
    return load_dataset, sf, np


# FLEURS uses BCP-47-ish region configs; Common Voice uses bare ISO codes.
FLEURS_HINT = "hi_in, ta_in, bn_in, gu_in, mr_in, pa_in, te_in, kn_in, ml_in, ur_pk, en_us"
CV_HINT = "hi, ta, bn, gu, mr, pa, te, kn, ml, en"


def fetch_language(load_dataset, sf, np, source, lang, per_lang, out_dir, split, hf_token):
    """Stream `per_lang` clips of one language and write them as WAV files."""
    lang_dir = Path(out_dir) / lang
    lang_dir.mkdir(parents=True, exist_ok=True)

    if source == "fleurs":
        ds = load_dataset("google/fleurs", lang, split=split, streaming=True)
    elif source == "commonvoice":
        ds = load_dataset(
            "mozilla-foundation/common_voice_17_0", lang,
            split=split, streaming=True, token=hf_token or True,
        )
    else:
        raise ValueError(f"Unknown source: {source}")

    written = 0
    for sample in ds:
        if written >= per_lang:
            break
        audio = sample.get("audio")
        if audio is None or audio.get("array") is None:
            continue
        arr = np.asarray(audio["array"], dtype="float32")
        sr = int(audio["sampling_rate"])
        if arr.size == 0:
            continue
        out_path = lang_dir / f"{lang}_{written:05d}.wav"
        sf.write(str(out_path), arr, sr)
        written += 1
        if written % 50 == 0:
            print(f"  [{source}:{lang}] {written}/{per_lang}")

    print(f"[{source}:{lang}] wrote {written} clips -> {lang_dir}")
    return written


def main():
    p = argparse.ArgumentParser(description="Fetch a subset of real speech for VoiceShield training")
    p.add_argument("--source", choices=["fleurs", "commonvoice"], default="fleurs",
                   help="Dataset source (default: fleurs, non-gated)")
    p.add_argument("--langs", type=str, default="hi_in,en_us",
                   help=f"Comma-separated language configs.\n  fleurs: {FLEURS_HINT}\n  commonvoice: {CV_HINT}")
    p.add_argument("--per_lang", type=int, default=300, help="Clips to fetch per language")
    p.add_argument("--out", type=str, default="data/real_raw", help="Output directory")
    p.add_argument("--split", type=str, default="train", help="Dataset split (train/validation/test)")
    p.add_argument("--hf_token", type=str, default=None, help="HF token (Common Voice only; or use huggingface-cli login)")
    args = p.parse_args()

    load_dataset, sf, np = _lazy_imports()

    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    print(f"Source={args.source}  langs={langs}  per_lang={args.per_lang}  out={args.out}\n")

    total = 0
    for lang in langs:
        try:
            total += fetch_language(load_dataset, sf, np, args.source, lang,
                                    args.per_lang, args.out, args.split, args.hf_token)
        except Exception as e:
            print(f"[SKIP:{lang}] {e}")

    print(f"\n=== Done: {total} real clips in {args.out} ===")
    print(f"Next:  python -m ai.train.build_dataset --real_dir {args.out} --output_dir data --num_fake 2")


if __name__ == "__main__":
    main()
