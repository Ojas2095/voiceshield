import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.db.models import EvidenceLog
from backend.app.services.calls import get_call
from backend.app.services.evidence_chain import verify_chain
from backend.app.middleware import apply_rate_limit

router = APIRouter(prefix="/api/calls", tags=["evidence"])


class WindowDetails(BaseModel):
    start_ms: int
    end_ms: int


class EvidenceEntryResponse(BaseModel):
    entry_id: int
    timestamp: str
    window: WindowDetails
    payload: Dict[str, Any]
    entry_hash: str
    prev_hash: str


class EvidenceChainResponse(BaseModel):
    call_id: str
    chain_valid: bool
    entries: List[EvidenceEntryResponse]


def parse_call_uuid(call_id: str) -> uuid.UUID:
    """
    Validates call_id as UUID string.
    Raises HTTP 400 if malformed.
    """
    try:
        return uuid.UUID(str(call_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid call_id format. Must be a valid UUID."
        )


@router.get(
    "/{call_id}/evidence",
    response_model=EvidenceChainResponse,
    dependencies=[Depends(apply_rate_limit)],
)
async def get_call_evidence_endpoint(
    call_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches the complete SHA-256 evidence log for a call and verifies cryptographic integrity.
    """
    call_uuid = parse_call_uuid(call_id)

    # 1. Validate call exists
    call = await get_call(db, call_uuid)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )

    # TODO (Kots Auth Integration): Plug in authorization/ownership check here once auth layer is finalized.
    # e.g., current_user: str = Depends(get_current_user)
    # if not verify_call_ownership(current_user, str(call_uuid)):
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # 2. Fetch all evidence_log rows ordered by entry_id asc
    stmt = (
        select(EvidenceLog)
        .where(EvidenceLog.call_id == call_uuid)
        .order_by(EvidenceLog.entry_id.asc())
    )
    result = await db.execute(stmt)
    entries = list(result.scalars().all())

    # 3. Cryptographically verify the evidence hash-chain
    chain_valid = verify_chain(entries)

    # 4. Format entries for response
    formatted_entries = []
    for entry in entries:
        payload = entry.payload if isinstance(entry.payload, dict) else {}
        start_ms = payload.get("window_start_ms", 0)
        end_ms = payload.get("window_end_ms", 0)
        
        formatted_entries.append(
            EvidenceEntryResponse(
                entry_id=entry.entry_id,
                timestamp=entry.created_at.isoformat() if entry.created_at else "",
                window=WindowDetails(start_ms=start_ms, end_ms=end_ms),
                payload=payload,
                entry_hash=entry.entry_hash,
                prev_hash=entry.prev_hash,
            )
        )

    return EvidenceChainResponse(
        call_id=str(call_uuid),
        chain_valid=chain_valid,
        entries=formatted_entries,
    )
