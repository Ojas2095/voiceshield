# Demo audio for Replay Demo Call

The **Replay Demo Call** button streams these files through the *real* backend
pipeline (WebSocket → telephony → VAD → windows → model). They are NOT scripted
results — the backend produces the verdict.

Place four 16 kHz mono WAV files here (the UI references these exact names):

| File | What it should be |
|---|---|
| `real_en.wav`   | A **genuine human** voice, English (consented recording) |
| `cloned_en.wav` | An **AI-cloned** voice, English (XTTS of a consented voice) |
| `real_hi.wav`   | A genuine human voice, Hindi/Hinglish |
| `cloned_hi.wav` | An AI-cloned voice, Hindi/Hinglish |

Keep each clip ~6–15 seconds of clear speech.

## Generate them
Record the two real clips yourself (with consent), then:

```bash
python scripts/prepare_demo_audio.py \
  --real_en path/to/real_english.wav \
  --real_hi path/to/real_hindi.wav \
  --out frontend/public/demo
```

The script converts the real clips to 16 kHz mono and generates the cloned
counterparts with Coqui XTTS. See that script for details.

> For the primary demo story, `cloned_en.wav` / `cloned_hi.wav` should drive the
> risk **up** (→ HIGH RISK → transaction hold), while `real_*.wav` stay LOW.
