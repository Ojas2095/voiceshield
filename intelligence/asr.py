"""
VoiceShield — Layer 2: Speech-to-Text (ASR)
===========================================
Transcribes call audio (Hindi / English / code-mixed) so the intent classifier
can read the *content* of the conversation.

Backend: faster-whisper (preferred) or openai-whisper. Both are lazy-imported so
the rest of the app runs even if ASR isn't installed — in that case `transcribe`
returns an empty transcript and the pipeline degrades gracefully to Layer 1 + 3.

Because ASR is heavier than the per-window Layer-1 model, run it LESS often
(e.g. once every few seconds of accumulated speech), not on every 2s window.

Usage
-----
    from intelligence.asr import Transcriber
    asr = Transcriber(model_size="small")     # loads lazily on first call
    out = asr.transcribe_array(float_pcm_16k, sample_rate=16000)
    # -> {"text": "...", "language": "hi", "available": True}
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("voiceshield.asr")


class Transcriber:
    """Lazy Whisper wrapper with a graceful no-op fallback."""

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._backend: Optional[str] = None   # "faster-whisper" | "whisper" | None
        self._tried_load = False

    # ── model loading ────────────────────────────────────────────────
    def _ensure_model(self) -> bool:
        """Load a Whisper backend on first use. Returns True if ASR is available."""
        if self._tried_load:
            return self._model is not None
        self._tried_load = True

        # Preferred: faster-whisper (fast, int8 on CPU)
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            self._backend = "faster-whisper"
            logger.info(f"ASR ready: faster-whisper ({self.model_size}, {self.device})")
            return True
        except Exception as e:
            logger.debug(f"faster-whisper unavailable: {e}")

        # Fallback: openai-whisper
        try:
            import whisper
            self._model = whisper.load_model(self.model_size, device=self.device)
            self._backend = "whisper"
            logger.info(f"ASR ready: openai-whisper ({self.model_size})")
            return True
        except Exception as e:
            logger.warning(f"No Whisper backend available — ASR disabled ({e}). "
                           "Install `faster-whisper` to enable Layer 2 transcription.")
            self._model = None
            return False

    @property
    def available(self) -> bool:
        return self._ensure_model()

    # ── transcription ────────────────────────────────────────────────
    def transcribe_array(self, audio, sample_rate: int = 16000) -> dict:
        """
        Transcribe a mono float32 numpy array / list at `sample_rate`.
        Whisper expects 16 kHz; caller should resample if needed.

        Returns: {"text": str, "language": str|None, "available": bool}
        """
        if not self._ensure_model():
            return {"text": "", "language": None, "available": False}

        try:
            import numpy as np
            audio = np.asarray(audio, dtype="float32")

            if self._backend == "faster-whisper":
                segments, info = self._model.transcribe(audio, beam_size=1)
                text = " ".join(seg.text for seg in segments).strip()
                lang = getattr(info, "language", None)
                return {"text": text, "language": lang, "available": True}

            # openai-whisper
            result = self._model.transcribe(audio, fp16=False)
            return {
                "text": (result.get("text") or "").strip(),
                "language": result.get("language"),
                "available": True,
            }
        except Exception as e:
            logger.warning(f"ASR transcription failed: {e}")
            return {"text": "", "language": None, "available": True}

    def transcribe_file(self, path: str) -> dict:
        """Transcribe an audio file on disk (for offline testing)."""
        if not self._ensure_model():
            return {"text": "", "language": None, "available": False}
        try:
            if self._backend == "faster-whisper":
                segments, info = self._model.transcribe(path, beam_size=1)
                text = " ".join(seg.text for seg in segments).strip()
                return {"text": text, "language": getattr(info, "language", None), "available": True}
            result = self._model.transcribe(path, fp16=False)
            return {"text": (result.get("text") or "").strip(),
                    "language": result.get("language"), "available": True}
        except Exception as e:
            logger.warning(f"ASR file transcription failed: {e}")
            return {"text": "", "language": None, "available": True}


_GLOBAL_TRANSCRIBER: Optional[Transcriber] = None


def get_transcriber(model_size: str = "base", device: str = "cpu", compute_type: str = "int8") -> Transcriber:
    """Returns the shared process-wide Whisper Transcriber instance."""
    global _GLOBAL_TRANSCRIBER
    if _GLOBAL_TRANSCRIBER is None:
        _GLOBAL_TRANSCRIBER = Transcriber(model_size=model_size, device=device, compute_type=compute_type)
    return _GLOBAL_TRANSCRIBER


# Module-level singleton
global_transcriber = get_transcriber()


if __name__ == "__main__":
    # Interface smoke test — works even with no Whisper installed.
    t = get_transcriber()
    print("ASR available:", t.available)
    print(t.transcribe_array([0.0] * 16000, sample_rate=16000))
