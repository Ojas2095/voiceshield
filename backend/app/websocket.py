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

logger = logging.getLogger("voiceshield.websocket")

router = APIRouter(tags=["websocket"])

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
                # Async AI inference
                spoof_prob = await classifier.infer(window.audio_data, call_id=call_id)
                
                # Risk fusion rolling calculation
                fused_risk, is_flagged = global_risk_tracker.update_risk(call_id, spoof_prob)

                payload = {
                    "type": "risk_update",
                    "window_start_ms": window.window_start_ms,
                    "window_end_ms": window.window_end_ms,
                    "spoof_probability": spoof_prob,
                    "fused_risk_score": fused_risk,
                    "is_flagged": is_flagged,
                }

                # Fire on_detection integration hook for Akshat's persistence/hash-chain
                await on_detection(call_id, payload)

                # Send risk update JSON frame
                await websocket.send_json(payload)

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
