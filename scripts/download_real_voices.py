"""
VoiceShield — Real Multi-Speaker Dataset Downloader
==================================================
Downloads clean, un-gated, multi-speaker real human speech datasets directly
to your local disk (under `data/real_raw/`) without requiring third-party logins
or HuggingFace tokens.

Default sources:
- CMU ARCTIC: High-quality, phonetically balanced phoneme recordings:
    * ksp: Indian English (Male) — 1,132 utterances
    * slt: General American (Female) — 1,132 utterances
    * bdl: General American (Male) — 1,132 utterances

Usage:
    # Download 300 Indian English clips (ksp)
    python scripts/download_real_voices.py --speakers ksp --limit 300

    # Download Indian English + US Female (300 clips each = 600 real voices)
    python scripts/download_real_voices.py --speakers ksp,slt --limit 300

    # Ingest directly into data/real/ for training
    python scripts/download_real_voices.py --speakers ksp --limit 200 --ingest
"""
import sys
import os
import time
import argparse
import urllib.request
import tarfile
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_RAW_DIR = REPO_ROOT / "data" / "real_raw"
REAL_DIR = REPO_ROOT / "data" / "real"

CMU_BASE_URL = "http://www.festvox.org/cmu_arctic/packed/"


def download_with_progress(url: str, dest_path: Path) -> bool:
    print(f"Connecting to {url}...")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VoiceShield-Dataset-Fetcher"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("content-length", 0))
            block_size = 1024 * 64  # 64 KB
            downloaded = 0
            t0 = time.time()
            last_print = t0

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as out_file:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_print > 2.0 or downloaded == total_size:
                        speed_mb = (downloaded / (1024 * 1024)) / max(0.1, now - t0)
                        pct = (downloaded / total_size * 100) if total_size else 0
                        print(f"  Downloaded: {downloaded / (1024 * 1024):.1f} MB / {total_size / (1024 * 1024):.1f} MB "
                              f"({pct:.1f}%) at {speed_mb:.2f} MB/s", end="\r", flush=True)
                        last_print = now

            print(f"\n✔ Finished download: {dest_path.name} ({dest_path.stat().st_size / (1024 * 1024):.1f} MB) in {time.time() - t0:.1f}s")
            return True
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        return False


def extract_wavs(archive_path: Path, target_dir: Path, limit: int | None = None) -> list[Path]:
    print(f"Extracting WAV files from {archive_path.name} to {target_dir}...")
    extracted_files = []
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:bz2") as tar:
        members = tar.getmembers()
        wav_members = [m for m in members if m.name.endswith(".wav") and not m.name.startswith("._")]
        print(f"Found {len(wav_members)} WAV files in archive.")

        if limit:
            wav_members = wav_members[:limit]
            print(f"Extracting selected {limit} files...")

        for m in wav_members:
            # Extract just the filename to target_dir
            filename = Path(m.name).name
            out_file = target_dir / filename
            with tar.extractfile(m) as source, open(out_file, "wb") as dest:
                shutil.copyfileobj(source, dest)
            extracted_files.append(out_file)

    print(f"✔ Extracted {len(extracted_files)} files into {target_dir}")
    return extracted_files


def main():
    parser = argparse.ArgumentParser(description="Download real multi-speaker human voice dataset")
    parser.add_argument("--speakers", type=str, default="ksp",
                        help="Comma-separated CMU ARCTIC speaker codes (e.g. ksp=Indian Male, slt=US Female, bdl=US Male)")
    parser.add_argument("--limit", type=int, default=250,
                        help="Max clips to extract per speaker (default: 250, use 0 for all ~1130)")
    parser.add_argument("--ingest", action="store_true",
                        help="Immediately run scripts/ingest_real_voices.py on extracted audio")
    parser.add_argument("--keep_archive", action="store_true",
                        help="Keep the downloaded .tar.bz2 archive (default: remove to save space)")
    args = parser.parse_args()

    speakers = [s.strip() for s in args.speakers.split(",") if s.strip()]
    limit = None if args.limit <= 0 else args.limit

    print("=" * 70)
    print("VoiceShield — Real Multi-Speaker Dataset Downloader")
    print(f"Target speakers: {speakers}")
    print(f"Limit per speaker: {limit if limit else 'All (~1,130)'}")
    print(f"Destination: {REAL_RAW_DIR}")
    print("=" * 70)

    archives_dir = REPO_ROOT / "data" / "downloads"
    archives_dir.mkdir(parents=True, exist_ok=True)

    total_extracted = 0
    all_extracted_dirs = []

    for spk in speakers:
        filename = f"cmu_us_{spk}_arctic.tar.bz2"
        url = f"{CMU_BASE_URL}{filename}"
        archive_dest = archives_dir / filename

        print(f"\n▶ Fetching speaker: '{spk}' ({url})")
        if not archive_dest.exists() or archive_dest.stat().st_size < 1000:
            success = download_with_progress(url, archive_dest)
            if not success:
                print(f"[SKIP] Failed to download {spk}")
                continue
        else:
            print(f"Using cached archive: {archive_dest.name}")

        spk_target_dir = REAL_RAW_DIR / spk
        extracted = extract_wavs(archive_dest, spk_target_dir, limit=limit)
        total_extracted += len(extracted)
        all_extracted_dirs.append(spk_target_dir)

        if not args.keep_archive and archive_dest.exists():
            print(f"Cleaning up archive {archive_dest.name} to conserve disk space...")
            archive_dest.unlink(missing_ok=True)

    print("\n" + "=" * 70)
    print(f"🎉 SUCCESS: Downloaded and extracted {total_extracted} real human voice clips!")
    print(f"Raw audio location: {REAL_RAW_DIR}")
    print("=" * 70)

    if args.ingest:
        print("\n▶ Running automated ingestion into data/real/...")
        import subprocess
        for edir in all_extracted_dirs:
            subprocess.run([sys.executable, "scripts/ingest_real_voices.py", str(edir)], cwd=str(REPO_ROOT))


if __name__ == "__main__":
    main()
