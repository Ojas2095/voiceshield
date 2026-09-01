"""
WebSocket streaming endpoint — the real-time core of VoiceShield.

WS /ws/stream/{call_id}
  ← binary PCM frames (int16 LE, 20ms @ client SR, mono)
  → JSON messages: risk_update | vad_update | hold_triggered | error

Full pipeline per frame:
  raw bytes → VADPipeline (ring-buffer, telephony-sim, Silero VAD)
    → speech-active windows → classifier.infer()
      → ConfidenceFusion.update()
        → persist Detection + EvidenceLog
          → push risk_update JSON to client
            → if rolling score > hold_threshold → auto-trigger hold
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

import app.inference as inf
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.hash_chain import GENESIS_HASH, build_payload, compute_hash
from app.inference import ConfidenceFusion
from app.models import Call, Detection, EvidenceLog, TransactionHold
from app.schemas import HoldTriggered, RiskUpdate, VADUpdate, to_verdict
from app.vad import VADPipeline
from sqlalchemy import select, desc

# —— SECURITY INVARIANT ————————————————————————————————————————————————————————————————————————
# Raw audio is NEVER persisted to disk or DB (voice = biometric data, DPDP 2023).
# Audio frames exist only in memory for the duration of one 2-second window.
# Only hashes + verdicts + scores + metadata are stored.
# ——————————————————————————————————————————————————————————————————————————————

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/stream/{call_id}")
async def stream_audio(websocket: WebSocket, call_id: uuid.UUID) -> None:
    """
    Main WebSocket endpoint.
    Accepts binary PCM audio frames and pushes real-time risk updates.
    """
    await websocket.accept()
    logger.info("WS connected for call_id=%s", call_id)

    fusion = ConfidenceFusion()
    pipeline = VADPipeline(str(call_id))
    hold_already_triggered = False

    try:
        # Validate the call exists
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Call).where(Call.call_id == call_id))
            call: Call | None = result.scalar_one_or_none()
            if call is None:
                await websocket.send_json({"type": "error", "detail": f"Call {call_id} not found"})
                await websocket.close(code=4004)
                return
            if call.status not in ("active",):
                await websocket.send_json({"type": "error", "detail": f"Call is '{call.status}', cannot stream"})
                await websocket.close(code=4003)
                return

        while True:
            try:
                raw_frame = await asyncio.wait_for(websocket.receive_bytes(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            # Process through the VAD pipeline (runs synchronous telephony + VAD in threadpool)
            loop = asyncio.get_running_loop()
            windows = await loop.run_in_executor(
                inf._executor,
                pipeline.push,
                raw_frame,
            )

            for window, is_speech, start_ms, end_ms in windows:
                # Always push VAD state to the UI
                vad_msg = VADUpdate(vad_active=is_speech, timestamp_ms=start_ms)
                await _send_json(websocket, vad_msg.model_dump())

                if not is_speech:
                    continue  # Don't run inference on silence

                # Inference (in-process, off event loop)
                classifier = inf.classifier
                if classifier is None:
                    continue

                spoof_prob = await classifier.infer(window)
                fused_score = fusion.update(spoof_prob)
                is_flagged = spoof_prob >= settings.flag_threshold
                model_ver = getattr(classifier, "model_version", settings.model_version)

                # Persist detection + evidence in one DB session
                verdict = to_verdict(fused_score)

                detection_id, hold_data = await _persist_detection(
                    call_id=call_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    spoof_prob=spoof_prob,
                    fused_score=fused_score,
                    is_flagged=is_flagged,
                    verdict=verdict,
                    model_ver=model_ver,
                    auto_hold=(
                        fused_score >= settings.hold_threshold
                        and not hold_already_triggered
                    ),
                )

                if hold_data:
                    hold_already_triggered = True
                    hold_msg = HoldTriggered(
                        hold_id=hold_data["hold_id"],
                        triggered_at=hold_data["triggered_at"],
                        mock_reference=hold_data["mock_reference"],
                        verdict=verdict,
                    )
                    await _send_json(websocket, hold_msg.model_dump())

                # Push risk update with canonical verdict field
                risk_msg = RiskUpdate(
                    window_start_ms=start_ms,
                    window_end_ms=end_ms,
                    spoof_probability=round(spoof_prob, 4),
                    fused_risk_score=round(fused_score, 4),
                    is_flagged=is_flagged,
                    verdict=verdict,
                    vad_active=is_speech,
                    model_version=model_ver,
                    # language_detected will be populated by Layer 2 (ASR) later
                )
                await _send_json(websocket, risk_msg.model_dump())

    except WebSocketDisconnect:
        logger.info("WS disconnected for call_id=%s", call_id)
    except Exception as exc:
        logger.exception("WS error for call_id=%s: %s", call_id, exc)
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass
    finally:
        logger.info("WS handler exiting for call_id=%s", call_id)


async def _persist_detection(
    call_id: uuid.UUID,
    start_ms: int,
    end_ms: int,
    spoof_prob: float,
    fused_score: float,
    is_flagged: bool,
    verdict: str,
    model_ver: str,
    auto_hold: bool,
) -> tuple[int, dict | None]:
    """
    Writes one Detection row, one EvidenceLog row, and optionally a
    TransactionHold row, all in a single DB transaction.
    Returns (detection_id, hold_data_or_None).
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Detection row
            detection = Detection(
                call_id=call_id,
                window_start_ms=start_ms,
                window_end_ms=end_ms,
                spoof_probability=spoof_prob,
                fused_risk_score=fused_score,
                is_flagged=is_flagged,
                verdict=verdict,
                model_version=model_ver,
            )
            db.add(detection)
            await db.flush()
            await db.refresh(detection)

            # 2. Hash-chain evidence entry
            now = datetime.now(timezone.utc)
            payload = build_payload(
                call_id=call_id,
                detection_id=detection.detection_id,
                window_start_ms=start_ms,
                window_end_ms=end_ms,
                spoof_probability=spoof_prob,
                fused_risk_score=fused_score,
                is_flagged=is_flagged,
                model_version=model_ver,
                server_timestamp=now,
            )

            # Get previous hash for this call
            prev_result = await db.execute(
                select(EvidenceLog.entry_hash)
                .where(EvidenceLog.call_id == call_id)
                .order_by(desc(EvidenceLog.entry_id))
                .limit(1)
            )
            prev_hash: str = prev_result.scalar_one_or_none() or GENESIS_HASH
            entry_hash = compute_hash(prev_hash, payload)

            evidence = EvidenceLog(
                call_id=call_id,
                detection_id=detection.detection_id,
                payload=payload,
                entry_hash=entry_hash,
                prev_hash=prev_hash,
            )
            db.add(evidence)

            # 3. Optional auto-hold
            hold_data: dict | None = None
            if auto_hold:
                hold = TransactionHold(
                    call_id=call_id,
                    triggered_by=detection.detection_id,
                    mock_reference=f"HOLD-{now.strftime('%Y%m%d')}-{str(call_id)[:8]}",
                )
                db.add(hold)
                await db.flush()
                await db.refresh(hold)

                # Update call status to held
                call_result = await db.execute(select(Call).where(Call.call_id == call_id))
                call = call_result.scalar_one_or_none()
                if call:
                    call.status = "held"

                hold_data = {
                    "hold_id": hold.hold_id,
                    "triggered_at": hold.triggered_at,
                    "mock_reference": hold.mock_reference,
                }

            await db.commit()
            return detection.detection_id, hold_data

        except Exception:
            await db.rollback()
            raise


async def _send_json(ws: WebSocket, data: dict) -> None:
    """Send JSON, converting datetime objects to ISO strings."""
    await ws.send_text(
        json.dumps(data, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o))
    )
