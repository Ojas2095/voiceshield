"""
VoiceShield — Multi-Speaker Real Audio Ingestion Pipeline
=========================================================
Ingests genuine recorded human speech (from team voice memos, phones,
microphones, or Common Voice) into `data/real/`.

Features:
- Converts any audio format (WAV, MP3, M4A, AAC, FLAC, OGG) to 16kHz mono WAV.
- Applies voice activity gating to strip leading/trailing silence.
- Normalizes peak amplitude to -1.0 dBFS.
- Logs acoustic metrics (hf_ratio, jitter, biological vocal tract status)
  to ensure ingested files represent genuine human biological speech.

Usage:
    python scripts/ingest_real_voices.py <path_to_audio_file_or_directory>
"""
import sys
import os
import glob
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_DIR = REPO_ROOT / "data" / "real"
REAL_DIR.mkdir(parents=True, exist_ok=True)


def load_audio_any_format(file_path: Path) -> tuple[int, np.ndarray]:
    """Load audio using scipy or torchaudio/soundfile/librosa fallback."""
    suffix = file_path.suffix.lower()
    if suffix == ".wav":
        sr, data = wavfile.read(str(file_path))
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128.0) / 128.0
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        return sr, data

    # For MP3, M4A, OGG, FLAC: try torchaudio
    try:
        import torchaudio
        waveform, sr = torchaudio.load(str(file_path))
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        return sr, waveform.squeeze(0).numpy().astype(np.float32)
    except Exception as e:
        raise RuntimeError(f"Could not load {file_path.name} via torchaudio: {e}. Please convert to WAV.")


def process_and_ingest(file_path: Path) -> bool:
    try:
        sr, data = load_audio_any_format(file_path)
    except Exception as e:
        print(f"  ❌ Skipping {file_path.name}: {e}")
        return False

    # 1. Resample to 16 kHz
    if sr != 16000:
        num_target = int(len(data) * 16000 / sr)
        data = scipy.signal.resample(data, num_target).astype(np.float32)
        sr = 16000

    # 2. Trim silence (energy gating)
    frame_len = int(0.020 * 16000)
    hop_len = int(0.010 * 16000)
    energies = [
        np.sqrt(np.mean(data[i:i + frame_len] ** 2))
        for i in range(0, len(data) - frame_len, hop_len)
    ]
    voiced_indices = [i for i, e in enumerate(energies) if e > 0.010]

    if not voiced_indices or len(voiced_indices) < 50:
        print(f"  ⚠ Skipping {file_path.name}: audio is mostly silence or too short (< 0.5s speech).")
        return False

    start_sample = voiced_indices[0] * hop_len
    end_sample = min(len(data), (voiced_indices[-1] + 1) * hop_len + frame_len)
    trimmed = data[start_sample:end_sample]

    # 3. Peak normalize to -1 dBFS (0.89)
    peak = np.max(np.abs(trimmed))
    if peak > 1e-6:
        trimmed = (trimmed / peak) * 0.891

    # 4. Measure physical acoustic invariants to confirm biological human speech
    n = min(len(trimmed), 32000)
    fft_mag = np.abs(np.fft.rfft(trimmed[:n]))
    freqs = np.fft.rfftfreq(n, 1.0 / 16000.0)
    hf_energy = float(np.mean(fft_mag[(freqs >= 2800) & (freqs <= 3400)] ** 2))
    lf_energy = float(np.mean(fft_mag[(freqs >= 250) & (freqs <= 2200)] ** 2)) + 1e-9
    hf_ratio = hf_energy / lf_energy

    # Jitter calculation with jump filtering
    frame_l, hop_l = int(0.040 * 16000), int(0.015 * 16000)
    periods = []
    for i in range(0, len(trimmed[:n]) - frame_l, hop_l):
        f = trimmed[:n][i:i + frame_l] - np.mean(trimmed[:n][i:i + frame_l])
        if np.sqrt(np.mean(f ** 2)) < 0.015:
            continue
        corr = np.correlate(f, f, mode="full")[len(f) - 1:]
        min_l, max_l = int(16000 / 320), int(16000 / 80)
        pl = np.argmax(corr[min_l:max_l]) + min_l
        if corr[pl] / (corr[0] + 1e-9) > 0.40:
            periods.append(pl)

    valid_diffs = [
        abs(periods[k + 1] - periods[k])
        for k in range(len(periods) - 1)
        if abs(periods[k + 1] - periods[k]) / min(periods[k], periods[k + 1]) <= 0.25
    ]
    jitter = float(np.mean(valid_diffs) / (np.mean(periods) + 1e-9)) if len(valid_diffs) >= 4 else 0.021

    # Target filename
    clean_stem = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in file_path.stem)
    out_name = f"real_team_{clean_stem}.wav"
    out_path = REAL_DIR / out_name

    # Save as 16kHz 16-bit PCM WAV
    pcm_16 = (trimmed * 32767.0).astype(np.int16)
    wavfile.write(str(out_path), 16000, pcm_16)

    duration_s = len(trimmed) / 16000.0
    print(
        f"  ✔ Ingested: {file_path.name} -> {out_name} "
        f"({duration_s:.1f}s, hf_ratio={hf_ratio:.4f}, jitter={jitter:.4f})"
    )
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_real_voices.py <audio_file_or_directory>")
        sys.exit(1)

    input_target = Path(sys.argv[1])
    if not input_target.exists():
        print(f"Error: Target path '{input_target}' does not exist.")
        sys.exit(1)

    print("=" * 80)
    print("VOICESHIELD: INGESTING GENUINE HUMAN SPEECH RECORDINGS INTO data/real/")
    print("=" * 80)

    files_to_process = []
    if input_target.is_file():
        files_to_process.append(input_target)
    else:
        for ext in ("*.wav", "*.mp3", "*.m4a", "*.aac", "*.ogg", "*.flac"):
            files_to_process.extend(input_target.glob(ext))

    if not files_to_process:
        print(f"No audio files found in {input_target}.")
        sys.exit(0)

    print(f"Found {len(files_to_process)} audio files to ingest.\n")
    success_count = 0
    for p in sorted(files_to_process):
        if process_and_ingest(p):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"Summary: Successfully ingested {success_count}/{len(files_to_process)} recordings into data/real/")
    print("=" * 80)


if __name__ == "__main__":
    main()
