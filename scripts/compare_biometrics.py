import os
import tempfile
import subprocess
import numpy as np
import scipy.io.wavfile as wavfile
from gtts import gTTS

def analyze(samples, sr=16000):
    # 1. Pitch autocorrelation & jitter
    frame_len = int(0.040 * sr)
    hop_len = int(0.015 * sr)
    periods = []
    for i in range(0, len(samples) - frame_len, hop_len):
        f = samples[i:i+frame_len] - np.mean(samples[i:i+frame_len])
        if np.sqrt(np.mean(f**2)) < 0.015: continue
        corr = np.correlate(f, f, mode='full')
        corr = corr[len(corr)//2:]
        min_l, max_l = int(sr/320), int(sr/80)
        pl = np.argmax(corr[min_l:max_l]) + min_l
        if corr[pl]/(corr[0]+1e-9) > 0.40:
            periods.append(pl)
            
    jitter = (np.mean(np.abs(np.diff(periods))) / (np.mean(periods)+1e-9)) if len(periods) >= 4 else 0.0
    
    # 2. Spectral flux
    frames = [samples[j:j+512] for j in range(0, len(samples)-512, 256)]
    ffts = [np.abs(np.fft.rfft(fr * np.hanning(len(fr)))) for fr in frames if len(fr)==512]
    fluxes = []
    for k in range(1, len(ffts)):
        fluxes.append(np.sum((ffts[k]-ffts[k-1])**2) / (np.sum(ffts[k]**2)+1e-9))
    mean_flux = np.mean(fluxes) if fluxes else 0.0
    
    # 3. Spectral flatness
    fft_tot = np.abs(np.fft.rfft(samples[:16000])) + 1e-9
    geom = np.exp(np.mean(np.log(fft_tot)))
    arith = np.mean(fft_tot)
    flatness = geom / arith
    
    # 4. HF ratio
    freqs = np.fft.rfftfreq(len(samples[:16000]), 1.0/sr)
    hf = float(np.mean(fft_tot[(freqs>=2800)&(freqs<=3400)]**2))
    lf = float(np.mean(fft_tot[(freqs>=250)&(freqs<=2200)]**2)) + 1e-9
    hf_ratio = hf / lf
    
    return jitter, mean_flux, flatness, hf_ratio

print(f"{'TYPE / FILE':35} | {'JITTER':8} | {'FLUX':10} | {'FLATNESS':8} | {'HF/LF':8}")
print("-" * 75)

# Test real speech files
for name in ['real_long_en.wav', 'human_scam_long_vishing.wav']:
    p = os.path.join('frontend/public/demo', name)
    sr, d = wavfile.read(p)
    if d.ndim > 1: d = d[:, 0]
    s = d.astype(np.float32) / 32768.0
    j, fl, flat, r = analyze(s[:32000], sr)
    print(f"{name:35} | {j*100:6.2f}% | {fl:10.4f} | {flat:8.4f} | {r:8.4f}")

# Test cloned files
for name in ['cloned_long_scam.wav', 'cloned_en.wav']:
    p = os.path.join('frontend/public/demo', name)
    sr, d = wavfile.read(p)
    if d.ndim > 1: d = d[:, 0]
    s = d.astype(np.float32) / 32768.0
    j, fl, flat, r = analyze(s[:32000], sr)
    print(f"{name:35} | {j*100:6.2f}% | {fl:10.4f} | {flat:8.4f} | {r:8.4f}")
