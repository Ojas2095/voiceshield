"""
Evidence log endpoint.

GET /api/calls/{call_id}/evidence
  → full hash-chain with chain_valid flag (powers the "Verify Integrity" button)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.hash_chain import verify_chain
from app.models import Call, EvidenceLog
from app.schemas import EvidenceEntry, EvidenceResponse
from app.signing import public_key_hex, verify_signature

router = APIRouter(prefix="/api/calls", tags=["evidence"])


@router.get("/{call_id}/evidence", response_model=EvidenceResponse)
async def get_evidence(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> EvidenceResponse:
    """
    Fetch the full SHA-256 hash-chain for a call and verify its integrity.
    chain_valid: true means no entry has been tampered with.
    """
    # Check if the call actually exists
    call_result = await db.execute(select(Call).where(Call.call_id == call_id))
    if not call_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

    result = await db.execute(
        select(EvidenceLog)
        .where(EvidenceLog.call_id == call_id)
        .order_by(asc(EvidenceLog.entry_id))
    )
    rows = result.scalars().all()

    if not rows:
        return EvidenceResponse(
            call_id=call_id,
            chain_valid=True,
            signatures_valid=True,
            public_key=public_key_hex(),
            entry_count=0,
            entries=[],
        )

    # Build the list of dicts that verify_chain expects
    chain_entries = [
        {
            "prev_hash": row.prev_hash,
            "entry_hash": row.entry_hash,
            "payload": row.payload,
        }
        for row in rows
    ]
    is_valid = verify_chain(chain_entries)

    # Ed25519 signature check — every signed row must verify against its entry_hash.
    signatures_valid = all(
        row.signature is not None and verify_signature(row.entry_hash, row.signature)
        for row in rows
    )

    entries = [
        EvidenceEntry(
            entry_id=row.entry_id,
            call_id=row.call_id,
            detection_id=row.detection_id,
            payload=row.payload,
            entry_hash=row.entry_hash,
            prev_hash=row.prev_hash,
            signature=row.signature,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return EvidenceResponse(
        call_id=call_id,
        chain_valid=is_valid,
        signatures_valid=signatures_valid,
        public_key=public_key_hex(),
        entry_count=len(entries),
        entries=entries,
    )
