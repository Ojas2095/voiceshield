import logging
import os
import sys
from typing import Dict, List
from collections import deque

from backend.app.config import settings

# Ensure repo root is importable so the top-level `intelligence` package resolves
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    from intelligence.fusion import fuse_layers
except Exception:  # never let a missing import crash the realtime loop
    def fuse_layers(voice_authenticity, intent_risk=0.0, call_signal_risk=0.0, **_):
        return round(max(0.0, min(1.0, float(voice_authenticity))), 4)

logger = logging.getLogger("voiceshield.risk")


class RiskTracker:
    """
    Per-call risk score fusion engine.
    Computes a rolling average of spoof probabilities over recent windows.
    Outputs fused_risk_score (0.0 to 1.0 scale) and is_flagged indicator.
    """
    def __init__(self, window_history_size: int = 5):
        self.window_history_size = window_history_size
        self._history: Dict[str, deque] = {}

    def update_risk(
        self,
        call_id: str,
        spoof_probability,
        intent_risk: float = 0.0,
        call_signal_risk: float = 0.0,
    ) -> tuple[float, bool]:
        """
        Fuse the three fraud layers for this window, append to the rolling
        history, and return the smoothed risk + flag.

        `spoof_probability` is Layer 1 P(fake). It may also arrive as the full
        classifier dict ({"p_fake": ...}); we coerce defensively so the realtime
        loop never crashes on a shape mismatch. `intent_risk` (Layer 2) and
        `call_signal_risk` (Layer 3) default to 0.0 for backward compatibility.
        """
        if call_id not in self._history:
            self._history[call_id] = deque(maxlen=self.window_history_size)

        if isinstance(spoof_probability, dict):
            spoof_probability = spoof_probability.get("p_fake", 0.0)
        try:
            spoof_probability = float(spoof_probability)
        except (TypeError, ValueError):
            spoof_probability = 0.0

        # 3-layer fusion for THIS window, then rolling-average for stability.
        window_risk = fuse_layers(spoof_probability, intent_risk, call_signal_risk)

        history = self._history[call_id]
        history.append(window_risk)

        fused_score = round(sum(history) / len(history), 4)
        is_flagged = fused_score >= settings.RISK_THRESHOLD

        return fused_score, is_flagged

    def cleanup_call(self, call_id: str) -> None:
        """Cleanup per-call risk tracker state."""
        if call_id in self._history:
            del self._history[call_id]


# Global RiskTracker instance
global_risk_tracker = RiskTracker()


async def on_detection(call_id: str, detection_payload: dict) -> None:
    """
    Integration Seam Hook:
    Fired on every processed window's evaluation (flagged or unflagged).
    Atomically persists detection record and appends SHA-256 evidence log entry in DB.
    """
    logger.debug(
        f"on_detection hook fired for call_id={call_id}: "
        f"spoof_prob={detection_payload.get('spoof_probability')}, "
        f"fused_risk={detection_payload.get('fused_risk_score')}, "
        f"flagged={detection_payload.get('is_flagged')}"
    )

    try:
        from backend.app.db.session import async_session_maker
        from backend.app.services.detections import insert_detection
        from backend.app.inference import get_classifier

        model_version = detection_payload.get("model_version")
        if not model_version:
            try:
                classifier = get_classifier()
                model_version = getattr(classifier, "model_version", "v0.1-dummy")
            except Exception:
                model_version = "v0.1-dummy"

        async with async_session_maker() as db:
            await insert_detection(
                db=db,
                call_id=call_id,
                window_start_ms=int(detection_payload.get("window_start_ms", 0)),
                window_end_ms=int(detection_payload.get("window_end_ms", 2000)),
                spoof_probability=float(detection_payload.get("spoof_probability", 0.0)),
                fused_risk_score=float(detection_payload.get("fused_risk_score", 0.0)),
                is_flagged=bool(detection_payload.get("is_flagged", False)),
                model_version=str(model_version),
            )
    except Exception as e:
        logger.warning(f"Error persisting detection/evidence in on_detection hook for call {call_id}: {e}")

