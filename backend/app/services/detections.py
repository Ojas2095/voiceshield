import uuid
from datetime import datetime, timezone
from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Detection
from backend.app.services.calls import get_call
from backend.app.services.evidence_chain import append_evidence


async def insert_detection(
    db: AsyncSession,
    call_id: Union[str, uuid.UUID],
    window_start_ms: int,
    window_end_ms: int,
    spoof_probability: float,
    fused_risk_score: float,
    is_flagged: bool,
    model_version: str,
) -> Detection:
    """
    Validates and persists a detection record, and atomically appends
    its corresponding SHA-256 evidence log entry in the same transaction.
    """
    if isinstance(call_id, str):
        call_id = uuid.UUID(call_id)

    # 1. Validate call exists and is active
    call = await get_call(db, call_id)
    if not call:
        raise ValueError(f"Call with id {call_id} does not exist.")
    if call.status != "active":
        raise ValueError(f"Call with id {call_id} is not active (status: {call.status}).")

    # 2. Validate value ranges
    if not (0.0 <= spoof_probability <= 1.0):
        raise ValueError(f"spoof_probability ({spoof_probability}) must be in range [0.0, 1.0].")

    if not (0.0 <= fused_risk_score <= 1.0):
        raise ValueError(f"fused_risk_score ({fused_risk_score}) must be in range [0.0, 1.0].")

    if window_end_ms <= window_start_ms:
        raise ValueError(f"window_end_ms ({window_end_ms}) must be greater than window_start_ms ({window_start_ms}).")

    # 3. Create Detection record
    detection = Detection(
        call_id=call_id,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        spoof_probability=spoof_probability,
        fused_risk_score=fused_risk_score,
        is_flagged=is_flagged,
        model_version=model_version,
        created_at=datetime.now(timezone.utc),
    )
    db.add(detection)
    await db.flush()  # Generates detection.detection_id and created_at

    # 4. Build exact evidence payload and append to SHA-256 hash-chain
    evidence_payload = {
        "call_id": str(call_id),
        "detection_id": detection.detection_id,
        "window_start_ms": int(window_start_ms),
        "window_end_ms": int(window_end_ms),
        "spoof_probability": float(spoof_probability),
        "fused_risk_score": float(fused_risk_score),
        "is_flagged": bool(is_flagged),
        "model_version": str(model_version),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await append_evidence(
        db=db,
        call_id=call_id,
        detection_id=detection.detection_id,
        payload=evidence_payload,
    )

    await db.commit()
    await db.refresh(detection)
    return detection
