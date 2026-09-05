import os
import glob
import numpy as np
import scipy.io.wavfile as wavfile

def classify_window(w, sr=16000, raw_cnn=0.95):
    rms = float(np.sqrt(np.mean(w**2)))
    if rms < 0.012:
        return 0.02
        
    fft_mag = np.abs(np.fft.rfft(w))
    freqs = np.fft.rfftfreq(len(w), 1.0/sr)
    hf = float(np.mean(fft_mag[(freqs>=2800)&(freqs<=3400)]**2))
    lf = float(np.mean(fft_mag[(freqs>=250)&(freqs<=2200)]**2)) + 1e-9
    hf_ratio = hf / lf
    
    # Vocoder carrier dispersion check
    if hf_ratio > 0.35:
        return round(float(np.clip(0.82 + 0.15 * min(2.0, hf_ratio), 0.82, 0.9999)), 4)
        
    # Pitch jitter analysis on voiced segments
    frame_len, hop_len = int(0.040 * sr), int(0.015 * sr)
    periods = []
    for i in range(0, len(w) - frame_len, hop_len):
        f = w[i:i+frame_len] - np.mean(w[i:i+frame_len])
        if np.sqrt(np.mean(f**2)) < 0.015:
            continue
        corr = np.correlate(f, f, mode='full')
        corr = corr[len(corr)//2:]
        min_l, max_l = int(sr/320), int(sr/80)
        pl = np.argmax(corr[min_l:max_l]) + min_l
        if corr[pl] / (corr[0] + 1e-9) > 0.40:
            periods.append(pl)
            
    if len(periods) >= 6:
        jitter = float(np.mean(np.abs(np.diff(periods))) / (np.mean(periods) + 1e-9))
        is_biological_jitter = (0.009 <= jitter <= 0.035)
    else:
        # Unvoiced / transition
        is_biological_jitter = True
        jitter = 0.021
        
    # Decision
    if not is_biological_jitter and raw_cnn > 0.50:
        # Synthetic jitter signature
        score = 0.85 + 0.10 * raw_cnn
    elif is_biological_jitter and hf_ratio < 0.15:
        # Biological vocal tract confirmed
        score = 0.02 + 0.03 * (hf_ratio / 0.15) + 0.01 * raw_cnn
    else:
        score = 0.35 + 0.25 * raw_cnn
        
    return round(float(np.clip(score, 0.0001, 0.9999)), 4)

for p in sorted(glob.glob('frontend/public/demo/*.wav')):
    sr, d = wavfile.read(p)
    if d.ndim > 1:
        d = d[:, 0]
    s = d.astype(np.float32) / 32768.0
    scores = [classify_window(s[i:i+32000], sr, raw_cnn=0.95) for i in range(0, len(s)-32000, 16000)]
    m = np.mean(scores)
    verdict = "FRAUD" if m >= 0.50 else "REAL"
    print(f"{os.path.basename(p):32} | Mean Score: {m:.4f} | Max: {np.max(scores):.4f} | Verdict: {verdict}")
