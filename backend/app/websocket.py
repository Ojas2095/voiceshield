import asyncio
import logging
import time
import uuid
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from backend.app.security.dependencies import validate_ws_token, verify_call_ownership
from backend.app.models.call import get_call_record, CallStatus
from backend.app.audio.pipeline import global_audio_pipeline
from backend.app.risk import global_risk_tracker, on_detection
from backend.app.config import settings

logger = logging.getLogger("voiceshield.websocket")

router = APIRouter(tags=["websocket"])

# ── Per-call intelligence state (Layers 2 & 3) ────────────────────────
_call_signal_cache: Dict[str, float] = {}   # Layer 3 risk, computed once per call
_intent_cache: Dict[str, float] = {}        # Layer 2 last intent risk
_asr_buffer: Dict[str, list] = {}           # accumulated speech for periodic ASR


def _compute_call_signal(call_record) -> float:
    """Layer 3: cheap metadata rules. Extend CallRecord with `number`/
    `claimed_entity` to light this up fully; today only the hour is available."""
    try:
        from intelligence.call_signals import score_call_signals
        meta = {}
        started = getattr(call_record, "started_at", None)
        if started is not None:
            meta["hour_local"] = started.hour
        for attr in ("number", "claimed_entity", "in_contacts"):
            if hasattr(call_record, attr):
                meta[attr] = getattr(call_record, attr)
        return float(score_call_signals(meta)["call_signal_risk"])
    except Exception as e:
        logger.debug(f"Layer3 call-signal skipped: {e}")
        return 0.0


def _compute_intent_risk(call_id: str, window) -> float:
    """Layer 2: accumulate speech, transcribe periodically (Whisper), score scam
    intent. Gated by settings.ENABLE_LAYER2_ASR; fully guarded so it can never
    stall or crash the realtime loop — returns the last cached value otherwise."""
    try:
        import numpy as np
        from intelligence.asr import global_transcriber
        from intelligence.intent_classifier import score_intent

        buf = _asr_buffer.setdefault(call_id, [])
        buf.append(np.asarray(window.audio_data, dtype="float32"))

        n = max(1, settings.ASR_EVERY_N_WINDOWS)
        if len(buf) % n != 0:
            return _intent_cache.get(call_id, 0.0)

        audio = np.concatenate(buf[-n:])
        out = global_transcriber.transcribe_array(audio, sample_rate=16000)
        if out.get("text"):
            _intent_cache[call_id] = float(score_intent(out["text"])["intent_risk"])
        return _intent_cache.get(call_id, 0.0)
    except Exception as e:
        logger.debug(f"Layer2 intent skipped: {e}")
        return _intent_cache.get(call_id, 0.0)


def _clear_intelligence_state(call_id: str) -> None:
    for cache in (_call_signal_cache, _intent_cache, _asr_buffer):
        cache.pop(call_id, None)

MAX_FRAME_SIZE_BYTES = 64 * 1024  # 64 KB
MAX_CONNECTIONS_PER_CALL = 1
GLOBAL_MAX_CONNECTIONS = 100
IDLE_TIMEOUT_SECONDS = 30.0
RATE_LIMIT_WINDOW_SECONDS = 1.0
MAX_MESSAGES_PER_SECOND = 60


class StreamConnectionManager:
    """
    Manages active WebSocket connections per call_id and global connection pool.
    """
    def __init__(self):
        self._active_connections: Dict[str, Set[WebSocket]] = {}
        self._global_count: int = 0

    def can_connect(self, call_id: str) -> tuple[bool, str]:
        if self._global_count >= GLOBAL_MAX_CONNECTIONS:
            return False, "Global connection capacity exceeded"
        
        current_call_conns = self._active_connections.get(call_id, set())
        if len(current_call_conns) >= MAX_CONNECTIONS_PER_CALL:
            return False, "Call streaming connection already active"
        
        return True, ""

    def register(self, call_id: str, websocket: WebSocket) -> None:
        if call_id not in self._active_connections:
            self._active_connections[call_id] = set()
        self._active_connections[call_id].add(websocket)
        self._global_count += 1

    def unregister(self, call_id: str, websocket: WebSocket) -> None:
        if call_id in self._active_connections:
            self._active_connections[call_id].discard(websocket)
            if not self._active_connections[call_id]:
                del self._active_connections[call_id]
        if self._global_count > 0:
            self._global_count -= 1

    def is_active(self, call_id: str) -> bool:
        return bool(self._active_connections.get(call_id))

    def cleanup_call_state(self, call_id: str) -> None:
        """Force cleanup state for a call_id."""
        if call_id in self._active_connections:
            del self._active_connections[call_id]
        global_audio_pipeline.cleanup_call(call_id)
        global_risk_tracker.cleanup_call(call_id)
        _clear_intelligence_state(call_id)


active_stream_manager = StreamConnectionManager()


@router.websocket("/ws/stream/{call_id}")
async def websocket_stream_endpoint(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint for real-time PCM audio streaming and risk updates.
    """
    # 1. Auth via JWT query parameter ?token=...
    token = websocket.query_params.get("token")
    user_id = validate_ws_token(token)
    if not user_id:
        logger.warning(f"WS connection rejected: invalid/missing token for call_id={call_id}")
        await websocket.close(code=4401, reason="Unauthorized")
        return

    # 3. Validate call_id is a valid UUID and call is active
    try:
        uuid.UUID(call_id)
    except (ValueError, TypeError):
        logger.warning(f"WS connection rejected: malformed UUID call_id={call_id}")
        await websocket.close(code=4400, reason="Invalid call_id format")
        return

    call_record = get_call_record(call_id)
    if not call_record or call_record.status != CallStatus.ACTIVE:
        logger.warning(f"WS connection rejected: call_id={call_id} not found or not active")
        await websocket.close(code=4404, reason="Call not active")
        return

    # 2. Authorize call ownership
    if not verify_call_ownership(user_id, call_id):
        logger.warning(f"WS connection rejected: user {user_id} does not own call_id={call_id}")
        await websocket.close(code=4403, reason="Forbidden")
        return

    # 5. Connection capacity limits
    can_conn, reason = active_stream_manager.can_connect(call_id)
    if not can_conn:
        logger.warning(f"WS connection rejected for call_id={call_id}: {reason}")
        await websocket.close(code=4429, reason=reason)
        return

    # Accept handshake
    await websocket.accept()
    active_stream_manager.register(call_id, websocket)
    _call_signal_cache[call_id] = _compute_call_signal(call_record)  # Layer 3 (once per call)
    logger.info(f"WS connection established for user={user_id}, call_id={call_id}")

    message_timestamps = []

    try:
        classifier = getattr(websocket.app.state, "classifier", None)
        if classifier is None:
            from backend.app.inference import get_classifier
            classifier = get_classifier()
            websocket.app.state.classifier = classifier

        while True:
            # 7. Idle timeout 30s
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=IDLE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logger.info(f"WS connection idle timeout for call_id={call_id}")
                await websocket.close(code=1000, reason="Idle timeout")
                break

            # Check for disconnect frame
            if message.get("type") == "websocket.disconnect":
                break

            # Expect binary PCM frame
            bytes_data = message.get("bytes")
            if not bytes_data:
                continue

            # 4. Max frame size check (64KB)
            if len(bytes_data) > MAX_FRAME_SIZE_BYTES:
                logger.warning(f"Oversized WS frame ({len(bytes_data)} bytes) on call_id={call_id}")
                await websocket.close(code=1009, reason="Message too large")
                break

            # 6. Per-connection message rate limiting (sliding window flood guard)
            now = time.time()
            message_timestamps.append(now)
            message_timestamps = [t for t in message_timestamps if now - t <= RATE_LIMIT_WINDOW_SECONDS]
            if len(message_timestamps) > MAX_MESSAGES_PER_SECOND:
                logger.warning(f"WS message rate exceeded for call_id={call_id}")
                await websocket.close(code=4429, reason="Rate limit exceeded")
                break

            # 10. Process audio frame non-blockingly
            speech_windows = global_audio_pipeline.process_frame(call_id, bytes_data)

            for window in speech_windows:
                # ── Layer 1: voice authenticity (classifier returns a dict) ──
                result = await classifier.infer(window.audio_data, call_id=call_id)
                if isinstance(result, dict):
                    p_fake = float(result.get("p_fake", 0.0))
                    gradcam_b64 = result.get("gradcam_b64")
                else:  # defensive: older classifiers may return a bare float
                    p_fake = float(result)
                    gradcam_b64 = None

                # ── Layer 2: conversation intent (gated — heavy ASR) ──
                intent_risk = (
                    _compute_intent_risk(call_id, window)
                    if settings.ENABLE_LAYER2_ASR else 0.0
                )
                # ── Layer 3: call signals (precomputed per call) ──
                call_signal_risk = _call_signal_cache.get(call_id, 0.0)

                # ── 3-layer fusion (rolling-smoothed) ──
                fused_risk, is_flagged = global_risk_tracker.update_risk(
                    call_id, p_fake,
                    intent_risk=intent_risk,
                    call_signal_risk=call_signal_risk,
                )
                verdict = (
                    "FRAUD" if fused_risk >= 0.70
                    else "SUSPICIOUS" if fused_risk >= 0.40
                    else "REAL"
                )

                # Internal payload for persistence / SHA-256 hash-chain (keys unchanged)
                detection_payload = {
                    "window_start_ms": window.window_start_ms,
                    "window_end_ms": window.window_end_ms,
                    "spoof_probability": round(p_fake, 4),
                    "fused_risk_score": fused_risk,
                    "is_flagged": is_flagged,
                    "model_version": getattr(classifier, "model_version", None),
                }
                await on_detection(call_id, detection_payload)

                # Client payload — matches the frontend ShieldResponse contract
                client_payload = {
                    "verdict": verdict,
                    "risk_score": round(fused_risk * 100, 1),
                    "layers": {
                        "voice_authenticity": round(p_fake * 100, 1),
                        "intent_risk": round(intent_risk * 100, 1),
                        "call_signal_risk": round(call_signal_risk * 100, 1),
                    },
                    "gradcam_png_b64": gradcam_b64,
                }
                await websocket.send_json(client_payload)

    except WebSocketDisconnect:
        logger.info(f"WS client disconnected gracefully for call_id={call_id}")
    except Exception as exc:
        # 9. No raw exceptions reach client - log server side
        logger.exception(f"Unhandled WS exception for call_id={call_id}: {exc}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        # 8. Clean disconnect handling releasing state
        active_stream_manager.unregister(call_id, websocket)
        active_stream_manager.cleanup_call_state(call_id)
        logger.info(f"Cleaned up state for WS stream call_id={call_id}")
