import os
import glob
import numpy as np
import scipy.io.wavfile as wavfile

def compute_pitch_jitter(waveform, sr=16000):
    frame_len = int(0.040 * sr) # 40ms = 640 samples
    hop_len = int(0.015 * sr)   # 15ms = 240 samples
    
    periods = []
    for i in range(0, len(waveform) - frame_len, hop_len):
        frame = waveform[i:i+frame_len]
        frame = frame - np.mean(frame)
        rms = np.sqrt(np.mean(frame**2))
        if rms < 0.02:
            continue
        
        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr)//2:]
        
        min_lag, max_lag = int(sr / 320), int(sr / 80)
        peak_lag = np.argmax(corr[min_lag:max_lag]) + min_lag
        peak_val = corr[peak_lag] / (corr[0] + 1e-9)
        
        if peak_val > 0.45:
            periods.append(peak_lag)
            
    if len(periods) < 4:
        return 0.0, 0.0
        
    diffs = np.abs(np.diff(periods))
    mean_period = np.mean(periods)
    jitter = np.mean(diffs) / (mean_period + 1e-9)
    period_std = np.std(periods)
    return jitter, period_std

print(f"{'FILE':35} | {'JITTER':12} | {'WINDOWS'}")
print("-" * 60)
for p in sorted(glob.glob('frontend/public/demo/*.wav')):
    sr, data = wavfile.read(p)
    if data.ndim > 1:
        data = data[:, 0]
    samples = data.astype(np.float32) / 32768.0
    jitters = []
    for i in range(0, len(samples)-32000, 16000):
        w = samples[i:i+32000]
        j, std = compute_pitch_jitter(w, sr)
        if j > 0:
            jitters.append(j)
    mean_j = np.mean(jitters) if jitters else 0.0
    name = os.path.basename(p)
    print(f"{name:35} | {mean_j*100:6.2f}%      | {len(jitters)}")
