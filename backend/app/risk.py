import logging
from typing import Dict, List
from collections import deque

from backend.app.config import settings

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

    def update_risk(self, call_id: str, spoof_probability: float) -> tuple[float, bool]:
        """
        Updates rolling window history for call_id and computes fused risk score.
        """
        if call_id not in self._history:
            self._history[call_id] = deque(maxlen=self.window_history_size)
        
        history = self._history[call_id]
        history.append(spoof_probability)

        fused_score = sum(history) / len(history)
        fused_score = round(fused_score, 4)

        # Flagged if fused score exceeds config threshold (e.g. 0.70)
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
    
    TODO (Akshat Integration):
    - Persist risk score window to PostgreSQL table.
    - Append hash transaction to SHA-256 evidence hash-chain.
    - Trigger PREVENT hold flow if is_flagged is True.
    """
    logger.debug(
        f"on_detection hook fired for call_id={call_id}: "
        f"spoof_prob={detection_payload.get('spoof_probability')}, "
        f"fused_risk={detection_payload.get('fused_risk_score')}, "
        f"flagged={detection_payload.get('is_flagged')}"
    )
    # Akshat's DB / SHA-256 hash chain / PREVENT hold functions will attach here.
