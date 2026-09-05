"""
VoiceShield — OpenSLR SLR103 Hindi Speech Dataset Downloader
===========================================================
Downloads the OpenSLR SLR103 crowdsourced native Hindi speech test set (247 MB),
extracts diverse real native Hindi recordings to `data/real_raw/hindi_slr103/`,
and ingests them into `data/real/` using `scripts/ingest_real_voices.py`.
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
REAL_RAW_DIR = REPO_ROOT / "data" / "real_raw" / "hindi_slr103"
REAL_DIR = REPO_ROOT / "data" / "real"
DOWNLOAD_URL = "https://www.openslr.org/resources/103/Hindi_test.tar.gz"


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


def extract_wavs(archive_path: Path, target_dir: Path, limit: int = 150) -> list[Path]:
    print(f"Extracting up to {limit} WAV files from {archive_path.name} to {target_dir}...")
    extracted_files = []
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()
        wav_members = [
            m for m in members
            if m.name.lower().endswith(".wav") and not Path(m.name).name.startswith("._")
        ]
        print(f"Found {len(wav_members)} total WAV files in SLR103 archive.")

        if limit > 0:
            wav_members = wav_members[:limit]

        for m in wav_members:
            filename = Path(m.name).name
            out_file = target_dir / filename
            with tar.extractfile(m) as source, open(out_file, "wb") as dest:
                shutil.copyfileobj(source, dest)
            extracted_files.append(out_file)

    print(f"✔ Extracted {len(extracted_files)} Hindi WAV files into {target_dir}")
    return extracted_files


def main():
    parser = argparse.ArgumentParser(description="Download OpenSLR SLR103 native Hindi speech dataset")
    parser.add_argument("--limit", type=int, default=150,
                        help="Max clips to extract (default: 150, use 0 for all)")
    parser.add_argument("--ingest", action="store_true", default=True,
                        help="Immediately run scripts/ingest_real_voices.py on extracted audio")
    parser.add_argument("--keep_archive", action="store_true",
                        help="Keep the downloaded .tar.gz archive (default: delete to save disk space)")
    args = parser.parse_args()

    print("=" * 75)
    print("VoiceShield — OpenSLR SLR103 Native Hindi Speech Fetcher")
    print(f"Extract limit: {args.limit if args.limit > 0 else 'All'}")
    print(f"Destination: {REAL_RAW_DIR}")
    print("=" * 75)

    archive_dest = REPO_ROOT / "data" / "downloads" / "Hindi_test.tar.gz"

    if not archive_dest.exists() or archive_dest.stat().st_size < 1000:
        success = download_with_progress(DOWNLOAD_URL, archive_dest)
        if not success:
            sys.exit(1)
    else:
        print(f"Using existing archive: {archive_dest}")

    extracted = extract_wavs(archive_dest, REAL_RAW_DIR, limit=args.limit)

    if not args.keep_archive and archive_dest.exists():
        print("Cleaning up archive to save disk space...")
        archive_dest.unlink(missing_ok=True)

    if args.ingest and extracted:
        print("\n▶ Running automated ingestion into data/real/...")
        import subprocess
        subprocess.run([sys.executable, "scripts/ingest_real_voices.py", str(REAL_RAW_DIR)], cwd=str(REPO_ROOT))

    print("\n🎉 Done! Real native Hindi speech successfully populated.")


if __name__ == "__main__":
    main()
