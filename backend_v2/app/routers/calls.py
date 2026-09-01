"""
REST endpoints for call lifecycle management.

POST /api/calls/start          — begin a new call session
POST /api/calls/{call_id}/stop — end a call session
GET  /api/calls/{call_id}/status — current call status
POST /api/calls/{call_id}/hold   — trigger mock transaction hold
GET  /api/calls                  — paginated call history
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Call, Detection, TransactionHold
from app.schemas import (
    CallStatusResponse,
    HoldResponse,
    StartCallRequest,
    StartCallResponse,
)

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.post("/start", response_model=StartCallResponse, status_code=status.HTTP_201_CREATED)
async def start_call(
    body: StartCallRequest,
    db: AsyncSession = Depends(get_session),
) -> StartCallResponse:
    """Create a new call session and return its UUID."""
    call = Call(source=body.source)
    db.add(call)
    await db.flush()
    await db.refresh(call)
    return StartCallResponse(
        call_id=call.call_id,
        started_at=call.started_at,
        status=call.status,
    )


@router.post("/{call_id}/stop", response_model=CallStatusResponse)
async def stop_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> CallStatusResponse:
    """Mark a call as ended."""
    call = await _get_call_or_404(db, call_id)
    if call.status == "ended":
        raise HTTPException(status_code=400, detail="Call already ended")
    call.ended_at = datetime.now(timezone.utc)
    if call.status != "held":
        call.status = "ended"
    await db.flush()
    return _call_to_schema(call)


@router.get("/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> CallStatusResponse:
    """Return the current status of a call (for reconnects/refresh)."""
    call = await _get_call_or_404(db, call_id)
    return _call_to_schema(call)


@router.post("/{call_id}/hold", response_model=HoldResponse, status_code=status.HTTP_201_CREATED)
async def trigger_hold(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> HoldResponse:
    """
    Trigger a mock transaction hold for a call.
    Picks the most-recent flagged detection as the trigger.
    """
    call = await _get_call_or_404(db, call_id)

    # Find the most recent flagged detection
    result = await db.execute(
        select(Detection)
        .where(Detection.call_id == call_id, Detection.is_flagged.is_(True))
        .order_by(desc(Detection.detection_id))
        .limit(1)
    )
    detection: Detection | None = result.scalar_one_or_none()

    hold = TransactionHold(
        call_id=call_id,
        triggered_by=detection.detection_id if detection else None,
        mock_reference=f"HOLD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{call_id!s:.8}",
    )
    db.add(hold)
    call.status = "held"
    await db.commit()

    # Re-query to get the DB-assigned hold_id (works on both SQLite and Postgres)
    result2 = await db.execute(
        select(TransactionHold)
        .where(TransactionHold.call_id == call_id)
        .order_by(desc(TransactionHold.hold_id))
        .limit(1)
    )
    hold = result2.scalar_one()

    return HoldResponse(
        hold_id=hold.hold_id,
        call_id=hold.call_id,
        triggered_at=hold.triggered_at,
        mock_reference=hold.mock_reference or "",
        triggered_by_detection_id=hold.triggered_by,
    )


@router.get("", response_model=list[CallStatusResponse])
async def list_calls(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
) -> list[CallStatusResponse]:
    """Paginated call history, most recent first."""
    result = await db.execute(
        select(Call).order_by(desc(Call.started_at)).limit(limit).offset(offset)
    )
    calls = result.scalars().all()
    return [_call_to_schema(c) for c in calls]


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_call_or_404(db: AsyncSession, call_id: uuid.UUID) -> Call:
    result = await db.execute(select(Call).where(Call.call_id == call_id))
    call: Call | None = result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return call


def _call_to_schema(call: Call) -> CallStatusResponse:
    return CallStatusResponse(
        call_id=call.call_id,
        started_at=call.started_at,
        ended_at=call.ended_at,
        source=call.source,
        status=call.status,
    )
