import uuid
from typing import Optional
from enum import Enum
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.services.calls import (
    create_call,
    get_call,
    end_call,
)
from backend.app.security.dependencies import (
    get_current_user,
    register_call_ownership,
    verify_call_ownership,
)
from backend.app.middleware import apply_rate_limit

router = APIRouter(prefix="/api/calls", tags=["calls"])


class CallSourceEnum(str, Enum):
    MIC = "mic"
    PHONE_SIM = "phone_sim"
    REPLAY = "replay"


class CallStatusEnum(str, Enum):
    ACTIVE = "active"
    STOPPED = "stopped"


class CallStartRequest(BaseModel):
    source: CallSourceEnum


class CallStartResponse(BaseModel):
    call_id: str
    started_at: str


class CallStopResponse(BaseModel):
    call_id: str
    status: str
    ended_at: str


class CallStatusResponse(BaseModel):
    call_id: str
    status: str
    source: str
    started_at: str
    ended_at: Optional[str] = None
    is_stream_active: bool


def parse_call_uuid(call_id: str) -> uuid.UUID:
    """
    Validates call_id as a UUID.
    Raises HTTP 400 if malformed.
    """
    try:
        return uuid.UUID(str(call_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid call_id format. Must be a valid UUID."
        )


@router.post("/start", response_model=CallStartResponse, dependencies=[Depends(apply_rate_limit)])
async def start_call_endpoint(
    payload: CallStartRequest,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Starts a new call session persisted in PostgreSQL. Rate limited.
    """
    call = await create_call(db, source=payload.source.value)
    register_call_ownership(call_id=str(call.call_id), user_id=current_user)
    
    # Keep in-memory store synchronized for fast WS / ownership lookups
    from backend.app.models.call import create_call_record, CallSource
    try:
        create_call_record(call_id=str(call.call_id), user_id=current_user, source=CallSource(payload.source.value))
    except Exception:
        pass

    return CallStartResponse(
        call_id=str(call.call_id),
        started_at=call.started_at.isoformat(),
    )


@router.post("/{call_id}/stop", response_model=CallStopResponse)
async def stop_call_endpoint(
    call_id: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stops an active call session in PostgreSQL and cleans up streaming state.
    """
    call_uuid = parse_call_uuid(call_id)

    call = await get_call(db, call_uuid)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    if not verify_call_ownership(current_user, str(call_uuid)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    if call.status in ["stopped", "ended"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call is already ended"
        )

    try:
        from backend.app.websocket import active_stream_manager
        active_stream_manager.cleanup_call_state(str(call_uuid))
    except Exception:
        pass

    updated_call = await end_call(db, call_uuid)
    if not updated_call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    return CallStopResponse(
        call_id=str(updated_call.call_id),
        status=updated_call.status,
        ended_at=updated_call.ended_at.isoformat() if updated_call.ended_at else "",
    )


@router.get("/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status_endpoint(
    call_id: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves status of a call session from PostgreSQL.
    """
    call_uuid = parse_call_uuid(call_id)

    call = await get_call(db, call_uuid)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    if not verify_call_ownership(current_user, str(call_uuid)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    is_stream_active = False
    try:
        from backend.app.websocket import active_stream_manager
        is_stream_active = active_stream_manager.is_active(str(call_uuid))
    except Exception:
        pass

    return CallStatusResponse(
        call_id=str(call.call_id),
        status=call.status,
        source=call.source,
        started_at=call.started_at.isoformat(),
        ended_at=call.ended_at.isoformat() if call.ended_at else None,
        is_stream_active=is_stream_active,
    )
