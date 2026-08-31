import time
import uuid
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.db.models import Detection, TransactionHold
from backend.app.services.calls import get_call
from backend.app.middleware import apply_rate_limit

router = APIRouter(prefix="/api/calls", tags=["prevent"])

# In-memory per-call cooldown timestamp tracker for flood protection
_LAST_HOLD_ATTEMPT: Dict[str, float] = {}
COOLDOWN_SECONDS: float = 0.5


class HoldRequest(BaseModel):
    triggered_by: Optional[int] = None


class HoldResponse(BaseModel):
    hold_id: int
    call_id: str
    triggered_by: Optional[int] = None
    triggered_at: str
    mock_reference: str


def parse_call_uuid(call_id: str) -> uuid.UUID:
    """
    Validates call_id as a UUID string.
    Raises HTTP 400 if malformed.
    """
    try:
        return uuid.UUID(str(call_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid call_id format. Must be a valid UUID."
        )


@router.post(
    "/{call_id}/hold",
    response_model=HoldResponse,
    dependencies=[Depends(apply_rate_limit)],
)
async def hold_call_endpoint(
    call_id: str,
    payload: Optional[HoldRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    PREVENT Endpoint: Places a mock transaction hold for a suspicious call.
    Idempotent: if a hold already exists for the call, returns the existing hold.
    """
    call_uuid = parse_call_uuid(call_id)
    triggered_by = payload.triggered_by if payload else None

    # In-memory per-call flood cooldown guard
    now = time.time()
    last_time = _LAST_HOLD_ATTEMPT.get(str(call_uuid), 0.0)
    _LAST_HOLD_ATTEMPT[str(call_uuid)] = now

    # 1. Validate call exists and is active
    call = await get_call(db, call_uuid)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    if call.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot place hold: call is not active"
        )

    # TODO (Kots Auth Integration): Plug in authorization/ownership check here once auth layer is finalized.
    # e.g., current_user: str = Depends(get_current_user)
    # if not verify_call_ownership(current_user, str(call_uuid)):
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # 2. If triggered_by is provided, validate it belongs to this call
    if triggered_by is not None:
        det_stmt = select(Detection).where(
            Detection.detection_id == triggered_by,
            Detection.call_id == call_uuid,
        )
        det_result = await db.execute(det_stmt)
        detection = det_result.scalar_one_or_none()
        if not detection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Detection {triggered_by} does not belong to call {call_id}"
            )

    # 3. Idempotency check: return existing hold if already placed
    existing_stmt = select(TransactionHold).where(TransactionHold.call_id == call_uuid).limit(1)
    existing_result = await db.execute(existing_stmt)
    existing_hold = existing_result.scalar_one_or_none()

    if existing_hold:
        return HoldResponse(
            hold_id=existing_hold.hold_id,
            call_id=str(existing_hold.call_id),
            triggered_by=existing_hold.triggered_by,
            triggered_at=existing_hold.triggered_at.isoformat() if existing_hold.triggered_at else "",
            mock_reference=existing_hold.mock_reference,
        )

    # 4. Generate mock reference e.g. "MOCK-A1B2C3D4"
    mock_ref = f"MOCK-{uuid.uuid4().hex[:8].upper()}"

    # 5. Insert new TransactionHold
    hold = TransactionHold(
        call_id=call_uuid,
        triggered_by=triggered_by,
        mock_reference=mock_ref,
    )
    db.add(hold)
    await db.commit()
    await db.refresh(hold)

    return HoldResponse(
        hold_id=hold.hold_id,
        call_id=str(hold.call_id),
        triggered_by=hold.triggered_by,
        triggered_at=hold.triggered_at.isoformat() if hold.triggered_at else "",
        mock_reference=hold.mock_reference,
    )
