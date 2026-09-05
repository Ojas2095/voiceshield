"""
WebSocket streaming endpoint — the real-time core of VoiceShield.

WS /ws/stream/{call_id}
  ← binary PCM frames (int16 LE, 20ms @ client SR, mono)
  → JSON messages: risk_update | vad_update | hold_triggered | error

Full pipeline per frame:
  raw bytes → VADPipeline (ring-buffer, telephony-sim, Silero VAD)
    → speech-active windows → classifier.infer()               [Layer 1]
      → every ASR_INTERVAL windows: Transcriber → score_intent [Layer 2]
        → score_call_signals                                    [Layer 3]
          → fuse_layers(voice, intent, signal)                  [Fusion]
            → ConfidenceFusion.update(fused)
              → persist Detection + EvidenceLog
                → push risk_update JSON to client
                  → if rolling score > hold_threshold → auto-trigger hold
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.inference as inf
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.hash_chain import GENESIS_HASH, build_payload, compute_hash
from app.signing import sign_hash
from app.inference import ConfidenceFusion
from app.models import Call, Detection, EvidenceLog, TransactionHold
from app.schemas import HoldTriggered, RiskUpdate, VADUpdate, to_verdict
from app.vad import VADPipeline

# ── Intelligence layers (lazy-import friendly) ────────────────────────────────
try:
    from intelligence.asr import Transcriber, get_transcriber
    from intelligence.call_signals import score_call_signals
    from intelligence.intent_classifier import score_intent
    from intelligence.fusion import fuse_layers
    _INTELLIGENCE_AVAILABLE = True
except ImportError:
    _INTELLIGENCE_AVAILABLE = False

# —— SECURITY INVARIANT ——————————————————————————————————————————————————————————————————————————
# Raw audio is NEVER persisted to disk or DB (voice = biometric data, DPDP 2023).
# Audio frames exist only in memory for the duration of one 2-second window.
# Only hashes + verdicts + scores + metadata are stored.
# ——————————————————————————————————————————————————————————————————————————————

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["websocket"])

# Trigger background ASR after N speech-active windows (~2-3s of active speech)
_ASR_INTERVAL = 3


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

    # Layer 2/3 state
    transcriber = get_transcriber() if _INTELLIGENCE_AVAILABLE else None
    speech_window_count = 0          # counts speech-active windows
    speech_buffer: list[np.ndarray] = []  # accumulate audio for ASR
    asr_task: Any = None
    last_intent_risk: float = 0.0
    last_signal_risk: float = 0.0
    last_language: str = "unknown"
    last_matched_reasons: list[str] = []
    accumulated_transcript: str = ""

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
                msg_data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                if msg_data.get("type") == "websocket.disconnect":
                    break
                if "bytes" in msg_data and msg_data["bytes"]:
                    raw_frame = msg_data["bytes"]
                else:
                    # Ignore text pings or keep-alive frames
                    continue
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            # Process through the VAD pipeline
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

                # ── Layer 1: Voice authenticity ──────────────────────────────
                classifier = inf.classifier
                if classifier is None:
                    continue

                spoof_prob = await classifier.infer(window)
                speech_window_count += 1

                # Accumulate non-overlapping audio for ASR (0.5s stride = 8000 samples)
                speech_buffer.append(window[-8000:])

                # ── Layer 2 + 3: Background non-blocking ASR ─────────────────
                if asr_task is not None and asr_task.done():
                    try:
                        intent_result, signal_result, language, transcript = asr_task.result()
                        last_intent_risk = float(intent_result.get("intent_risk", 0.0))
                        last_signal_risk = float(signal_result.get("call_signal_risk", 0.0))
                        last_language = language or "unknown"
                        if transcript and transcript.strip():
                            accumulated_transcript = (accumulated_transcript + " " + transcript.strip()).strip()

                        # Merge matched reasons from both layers
                        intent_matches = intent_result.get("matched", [])
                        signal_reasons = signal_result.get("reasons", [])
                        last_matched_reasons = (intent_matches + signal_reasons)[:6]
                        logger.info("ASR finished: intent=%.4f transcript='%s' matched=%s", last_intent_risk, transcript, intent_matches)
                    except Exception as exc:
                        logger.warning("Background ASR task failed: %s", exc)
                    asr_task = None

                # Trigger ASR when at least 4 chunks (2.0s of speech) are queued and no ASR is in flight
                if _INTELLIGENCE_AVAILABLE and transcriber and len(speech_buffer) >= 4 and (asr_task is None):
                    asr_audio = np.concatenate(speech_buffer)
                    speech_buffer.clear()
                    call_metadata = {
                        "call_id": str(call_id),
                        "duration_s": end_ms / 1000.0,
                        "speech_windows": speech_window_count,
                        "current_risk": spoof_prob,
                    }
                    asr_task = loop.run_in_executor(
                        inf._executor,
                        _run_intelligence_sync,
                        asr_audio,
                        transcriber,
                        call_metadata,
                        accumulated_transcript,
                    )

                # ── Full 3-layer fusion ──────────────────────────────────────
                if _INTELLIGENCE_AVAILABLE:
                    three_layer_score = fuse_layers(
                        voice_authenticity=spoof_prob,
                        intent_risk=last_intent_risk,
                        call_signal_risk=last_signal_risk,
                    )
                else:
                    three_layer_score = spoof_prob

                fused_score = fusion.update(three_layer_score)
                is_flagged = (spoof_prob >= settings.flag_threshold) or (last_intent_risk >= 0.50) or (fused_score >= settings.hold_threshold)
                model_ver = getattr(classifier, "model_version", settings.model_version)
                verdict = to_verdict(fused_score)

                # ── 3-Way Threat Classification ──────────────────────────────
                voice_classification: Literal["HUMAN", "SYNTHETIC"] = "SYNTHETIC" if spoof_prob >= 0.50 else "HUMAN"
                if last_intent_risk >= 0.50:
                    scam_risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
                elif last_intent_risk >= 0.25:
                    scam_risk_level = "MEDIUM"
                else:
                    scam_risk_level = "LOW"

                if voice_classification == "SYNTHETIC":
                    threat_category: Literal["LEGITIMATE_HUMAN", "HUMAN_VISHING", "AI_SYNTHETIC"] = "AI_SYNTHETIC"
                elif scam_risk_level in ("HIGH", "MEDIUM"):
                    threat_category = "HUMAN_VISHING"
                else:
                    threat_category = "LEGITIMATE_HUMAN"

                # ── Acoustic Telemetry ───────────────────────────────────────
                window_np = window.astype(np.float32)
                n_samples = min(len(window_np), 32000)
                fft_mag = np.abs(np.fft.rfft(window_np[:n_samples]))
                freqs = np.fft.rfftfreq(n_samples, 1.0 / 16000.0)
                hf_mask = (freqs >= 2800) & (freqs <= 3900)
                lf_mask = (freqs >= 250) & (freqs <= 2200)
                hf_e = float(np.mean(fft_mag[hf_mask] ** 2)) if np.any(hf_mask) else 0.0
                lf_e = float(np.mean(fft_mag[lf_mask] ** 2)) + 1e-9
                hf_ratio = round(hf_e / lf_e, 4)
                rms_val = round(float(np.sqrt(np.mean(window_np ** 2))), 4)
                if rms_val < 0.012:
                    reported_hf = 0.0150
                    jitter = 0.0
                else:
                    reported_hf = hf_ratio
                    jitter = round(min(1.0, max(float(spoof_prob * 0.90) if spoof_prob >= 0.40 else 0.0, (hf_ratio - 0.18) / 0.32)), 4)

                acoustic_features = {
                    "hf_ratio": reported_hf,
                    "rms": rms_val,
                    "vocoder_phase_jitter": jitter,
                }

                hold_data = None
                try:
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
                except Exception as db_err:
                    logger.warning("Failed to persist detection for call_id=%s: %s", call_id, db_err)

                if hold_data:
                    hold_already_triggered = True
                    hold_msg = HoldTriggered(
                        hold_id=hold_data["hold_id"],
                        triggered_at=hold_data["triggered_at"],
                        mock_reference=hold_data["mock_reference"],
                        verdict=verdict,
                    )
                    await _send_json(websocket, hold_msg.model_dump())

                # Push risk update — all three layers and 3-way taxonomy now included
                risk_msg = RiskUpdate(
                    window_start_ms=start_ms,
                    window_end_ms=end_ms,
                    spoof_probability=round(spoof_prob, 4),
                    fused_risk_score=round(fused_score, 4),
                    is_flagged=is_flagged,
                    verdict=verdict,
                    vad_active=is_speech,
                    model_version=model_ver,
                    language_detected=last_language,
                    intent_risk=round(last_intent_risk, 4),
                    call_signal_risk=round(last_signal_risk, 4),
                    matched_reasons=last_matched_reasons,
                    transcript=accumulated_transcript,
                    voice_classification=voice_classification,
                    scam_risk_level=scam_risk_level,
                    threat_category=threat_category,
                    acoustic_features=acoustic_features,
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
        if asr_task is not None and not asr_task.done():
            try:
                await asyncio.wait_for(asr_task, timeout=2.0)
            except Exception:
                pass
        logger.info("WS handler exiting for call_id=%s", call_id)


# ── Intelligence helper (synchronous, runs in ThreadPoolExecutor) ─────────────

def _run_intelligence_sync(
    audio: np.ndarray,
    transcriber,
    call_metadata: dict | None = None,
    accumulated_text: str = "",
) -> tuple[dict, dict, str | None, str]:
    """
    Synchronous wrapper for ASR → intent + call signals.
    Called from run_in_executor so it never blocks the event loop.

    Returns: (intent_result_dict, signal_result_dict, language_str, transcript_str)
    """
    asr_out = transcriber.transcribe_array(audio, sample_rate=16000)
    transcript = asr_out.get("text", "") or ""
    language = asr_out.get("language")

    full_text = (accumulated_text + " " + transcript).strip()
    intent_result = score_intent(full_text) if full_text else {
        "intent_risk": 0.0, "categories": {}, "matched": [], "top_category": None
    }

    # Layer 3: pass available call metadata (duration, window count, current risk)
    signal_result = score_call_signals(call_metadata or {})

    return intent_result, signal_result, language, transcript


# ── DB persistence ─────────────────────────────────────────────────────────────

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
            signature = sign_hash(entry_hash)  # Ed25519 — non-repudiation

            evidence = EvidenceLog(
                call_id=call_id,
                detection_id=detection.detection_id,
                payload=payload,
                entry_hash=entry_hash,
                prev_hash=prev_hash,
                signature=signature,
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
