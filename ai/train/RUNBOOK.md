# AI Training Runbook — Layer 1 (checklist A1–A4)

Goal: turn the (already-written) model code into **trained weights + real EER numbers**, so the
backend can switch off the dummy classifier. Run the whole thing **in Google Colab (free GPU)** —
`wav2vec2-large-xlsr-53` is far too slow to train on a laptop CPU.

> Branch: `ai/data-and-training`. Nothing here commits datasets or weights (see `.gitignore`);
> share the trained `.pt` files via Drive/USB.

---

## 0. Prerequisites (once)
```bash
pip install -r ai/requirements.txt
# fetch_data also needs:  pip install datasets soundfile
```
For Common Voice (optional, gated): make a free HuggingFace account, open the
Common Voice 17 dataset page, click **Agree/Access**, then `huggingface-cli login`.

---

## A1 — Fetch real speech (a subset, not the whole corpus)
Uses streaming, so you download exactly what you ask for.
```bash
# Hindi + English starter set (300 clips each ≈ a few hundred MB)
python -m ai.train.fetch_data --langs hi_in,en_us --per_lang 300 --out data/real_raw
# (optional) add Tamil + Bengali
python -m ai.train.fetch_data --langs ta_in,bn_in --per_lang 200 --out data/real_raw
```
Output: `data/real_raw/<lang>/*.wav`.
**Start small (300/lang) to get an end-to-end run working; scale up later for accuracy.**

---

## A2 — Build the training set (real + AI-fakes + telephony augmentation)
`build_dataset.py` telephony-degrades the real clips and generates AI-fake clips.

- **In Colab (GPU):** enable XTTS for realistic clones — best quality.
  ```bash
  pip install TTS            # Coqui XTTS (large; GPU recommended)
  python -m ai.train.build_dataset --real_dir data/real_raw --output_dir data --num_fake 2
  ```
- **Quick/offline-ish (CPU):** gTTS-only fakes (weaker, but unblocks a first run):
  ```bash
  python -m ai.train.build_dataset --real_dir data/real_raw --output_dir data --num_fake 2 --no_xtts
  ```
Output: `data/real/`, `data/fake/`, `data/manifest.json`.

> ⚠️ Known limitation to fix later (checklist E2/E3): fakes are generated in English only,
> and gTTS is an *easy* fake. For the Hindi claim + robustness, prefer XTTS with `language="hi"`.

---

## A3 — Train (GPU)
```bash
# Trains MelCNN first (fast), then the wav2vec2 head (needs GPU)
python -m ai.train.train_head --data_dir data --epochs 30 --batch_size 16
# CPU-only smoke test (CNN branch only, skips the heavy wav2vec2 head):
python -m ai.train.train_head --data_dir data --epochs 5 --cnn_only
```
Output: `ai/models/best_mel_cnn.pt` and `ai/models/best_wav2vec_head.pt`.

---

## A4 — Evaluate (get the numbers judges ask for)
```bash
python -m ai.train.evaluate --data_dir data --weights_dir ai/models --device cuda
```
Record from the printout: **EER, ROC-AUC, accuracy, mean/P95 latency**.
These are your Q&A cheat-sheet numbers.

---

## A5 — Ship the weights into the app
1. Copy `ai/models/best_mel_cnn.pt` + `best_wav2vec_head.pt` to each machine that runs the backend
   (they're git-ignored — use Drive/USB).
2. In `.env`, set **`USE_DUMMY_MODEL=false`** (backend then loads `ProductionClassifier`).
3. Smoke test: start the backend, speak into the frontend mic, confirm a **real** verdict +
   Grad-CAM (not the sine-wave dummy).

---

## Colab quick-path (recommended end-to-end)
```python
!git clone -b ai/data-and-training https://github.com/Ojas2095/voiceshield.git
%cd voiceshield
!pip install -r ai/requirements.txt datasets soundfile TTS
!python -m ai.train.fetch_data --langs hi_in,en_us --per_lang 300 --out data/real_raw
!python -m ai.train.build_dataset --real_dir data/real_raw --output_dir data --num_fake 2
!python -m ai.train.train_head --data_dir data --epochs 30
!python -m ai.train.evaluate --data_dir data --weights_dir ai/models --device cuda
# then download ai/models/*.pt from the Colab file browser
```

---

## Troubleshooting
- **`No audio files found`** → run A1 first; check `data/real_raw/<lang>/` has `.wav`s.
- **XTTS OOM / too slow** → use `--no_xtts` for the first run, or lower `--num_fake`.
- **wav2vec2 download slow** → it's ~1.2 GB; on Colab it caches. Pre-download once.
- **Latency > 500 ms in A4** (checklist E4) → switch to `wav2vec2-base` or quantize (ONNX/int8),
  or run the wav2vec2 branch less often than the CNN.
- **Val accuracy ~100% but demo fails** → train/test are too similar (gTTS-only, no held-out
  generator). Do the generator-held-out split (checklist E1) before trusting the numbers.
