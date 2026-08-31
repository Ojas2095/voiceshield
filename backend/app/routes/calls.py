import uuid
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.security.dependencies import (
    get_current_user,
    register_call_ownership,
    verify_call_ownership,
)
from backend.app.middleware import apply_rate_limit
from backend.app.models.call import (
    CallStartRequest,
    CallStartResponse,
    CallStopResponse,
    CallStatusResponse,
    CallStatus,
    create_call_record,
    get_call_record,
    update_call_ended,
)

router = APIRouter(prefix="/api/calls", tags=["calls"])


def validate_uuid(call_id: str) -> uuid.UUID:
    """
    Validates call_id is a valid UUID string before performing queries.
    Raises HTTP 400 if invalid.
    """
    try:
        return uuid.UUID(call_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid call_id format. Must be a valid UUID."
        )


@router.post("/start", response_model=CallStartResponse, dependencies=[Depends(apply_rate_limit)])
async def start_call(
    payload: CallStartRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Starts a new call session. Rate limited.
    """
    call_uuid = str(uuid.uuid4())
    record = create_call_record(call_id=call_uuid, user_id=current_user, source=payload.source)
    register_call_ownership(call_id=call_uuid, user_id=current_user)

    return CallStartResponse(
        call_id=record.call_id,
        started_at=record.started_at.isoformat()
    )


@router.post("/{call_id}/stop", response_model=CallStopResponse)
async def stop_call(
    call_id: str,
    current_user: str = Depends(get_current_user)
):
    """
    Stops an active call session and cleans up streaming state.
    """
    validate_uuid(call_id)

    record = get_call_record(call_id)
    if not record or not verify_call_ownership(current_user, call_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    if record.status == CallStatus.ENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call is already ended"
        )

    from backend.app.websocket import active_stream_manager
    active_stream_manager.cleanup_call_state(call_id)

    updated_record = update_call_ended(call_id)

    return CallStopResponse(
        call_id=updated_record.call_id,
        status=updated_record.status,
        ended_at=updated_record.ended_at.isoformat()
    )


@router.get("/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(
    call_id: str,
    current_user: str = Depends(get_current_user)
):
    """
    Retrieves status of a call session.
    """
    validate_uuid(call_id)

    record = get_call_record(call_id)
    if not record or not verify_call_ownership(current_user, call_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    from backend.app.websocket import active_stream_manager
    is_stream_active = active_stream_manager.is_active(call_id)

    return CallStatusResponse(
        call_id=record.call_id,
        status=record.status,
        source=record.source,
        started_at=record.started_at.isoformat(),
        ended_at=record.ended_at.isoformat() if record.ended_at else None,
        is_stream_active=is_stream_active
    )


# --- STUBBED ROUTES FOR AKSHAT INTEGRATION ---

@router.post("/{call_id}/hold", dependencies=[Depends(apply_rate_limit)])
async def hold_call(
    call_id: str,
    current_user: str = Depends(get_current_user)
):
    """
    # TODO (Akshat Integration): PREVENT hold persistence logic.
    Rate limited route stub.
    """
    validate_uuid(call_id)
    record = get_call_record(call_id)
    if not record or not verify_call_ownership(current_user, call_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    return {"call_id": call_id, "hold_status": "initiated", "note": "Akshat PREVENT hold stub"}


@router.get("/{call_id}/evidence", dependencies=[Depends(apply_rate_limit)])
async def get_call_evidence(
    call_id: str,
    current_user: str = Depends(get_current_user)
):
    """
    # TODO (Akshat Integration): SHA-256 evidence hash-chain verification & extraction logic.
    Rate limited route stub.
    """
    validate_uuid(call_id)
    record = get_call_record(call_id)
    if not record or not verify_call_ownership(current_user, call_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    return {"call_id": call_id, "evidence_chain": [], "note": "Akshat evidence hash-chain stub"}
