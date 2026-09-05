import os
import glob
import numpy as np
import scipy.io.wavfile as wavfile

def evaluate_features(w, sr=16000):
    rms = float(np.sqrt(np.mean(w**2)))
    if rms < 0.012:
        return 0.02, "silence"

    fft_mag = np.abs(np.fft.rfft(w))
    freqs = np.fft.rfftfreq(len(w), 1.0/sr)
    
    # 1. HF/LF ratio in telephone band
    hf = float(np.mean(fft_mag[(freqs>=2800)&(freqs<=3400)]**2))
    lf = float(np.mean(fft_mag[(freqs>=250)&(freqs<=2200)]**2)) + 1e-9
    hf_ratio = hf / lf

    # 2. Spectral flux (frame-to-frame transition dynamic)
    frames = [w[j:j+512] for j in range(0, len(w)-512, 256)]
    ffts = [np.abs(np.fft.rfft(fr * np.hanning(len(fr)))) for fr in frames if len(fr)==512]
    fluxes = []
    for k in range(1, len(ffts)):
        fluxes.append(np.sum((ffts[k]-ffts[k-1])**2) / (np.sum(ffts[k]**2)+1e-9))
    flux = np.mean(fluxes) if fluxes else 10.0

    # 3. Pitch Jitter (period perturbation)
    frame_len, hop_len = int(0.040 * sr), int(0.015 * sr)
    periods = []
    for i in range(0, len(w) - frame_len, hop_len):
        f = w[i:i+frame_len] - np.mean(w[i:i+frame_len])
        if np.sqrt(np.mean(f**2)) < 0.015: continue
        corr = np.correlate(f, f, mode='full')
        corr = corr[len(corr)//2:]
        min_l, max_l = int(sr/320), int(sr/80)
        pl = np.argmax(corr[min_l:max_l]) + min_l
        if corr[pl]/(corr[0]+1e-9) > 0.40:
            periods.append(pl)
    jitter = (np.mean(np.abs(np.diff(periods))) / (np.mean(periods)+1e-9)) if len(periods) >= 4 else 0.02

    # Multi-Lens Forensic Fusion:
    # A. Vocoder carrier dispersion: hf_ratio > 0.25 -> strong synthetic
    # B. Frame transition flatness: flux < 1.5 -> synthetic smoothness
    # C. Pitch regularity/jitter: jitter > 0.035 or (jitter < 0.005 and voiced) -> synthetic
    
    synthetic_votes = 0.0
    
    # Check HF carrier
    if hf_ratio > 0.50:
        synthetic_votes += 0.85
    elif hf_ratio > 0.20:
        synthetic_votes += 0.40 + 0.45 * ((hf_ratio - 0.20) / 0.30)
        
    # Check Spectral Flux (human speech has dynamic articulation > 5.0, TTS < 1.5)
    if flux < 0.50:
        synthetic_votes = max(synthetic_votes, 0.88)
    elif flux < 1.80:
        synthetic_votes = max(synthetic_votes, 0.72)
        
    # Check Jitter
    if jitter > 0.038:
        synthetic_votes = max(synthetic_votes, 0.80)

    # Human baseline if all biometric markers indicate biological voice
    if synthetic_votes == 0.0:
        score = 0.02 + 0.04 * (hf_ratio / 0.15)
    else:
        score = synthetic_votes

    return round(float(np.clip(score, 0.0001, 0.9999)), 4), f"hf={hf_ratio:.3f}, flux={flux:.2f}, jit={jitter*100:.1f}%"

print("Evaluating all files with Multi-Lens Forensic Fusion...")
for p in sorted(glob.glob('frontend/public/demo/*.wav')):
    sr, d = wavfile.read(p)
    if d.ndim > 1: d = d[:, 0]
    s = d.astype(np.float32) / 32768.0
    scores = []
    for i in range(0, len(s)-32000, 16000):
        sc, dbg = evaluate_features(s[i:i+32000], sr)
        scores.append(sc)
    m = np.mean(scores)
    verdict = "FRAUD" if m >= 0.50 else "REAL"
    print(f"{os.path.basename(p):32} | Mean: {m:.4f} | Max: {np.max(scores):.4f} | {verdict}")
