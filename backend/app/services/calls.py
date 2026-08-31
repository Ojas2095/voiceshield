import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Call

VALID_SOURCES = {"mic", "phone_sim", "replay"}
VALID_STATUSES = {"active", "stopped"}


async def create_call(
    db: AsyncSession,
    source: str,
    call_id: Optional[uuid.UUID] = None,
) -> Call:
    """
    Creates a new call record in the database.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"Invalid call source '{source}'. Must be one of {VALID_SOURCES}")

    call = Call(
        call_id=call_id or uuid.uuid4(),
        source=source,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)
    return call


async def get_call(db: AsyncSession, call_id: uuid.UUID) -> Optional[Call]:
    """
    Fetches a call record by UUID primary key.
    """
    result = await db.execute(select(Call).where(Call.call_id == call_id))
    return result.scalar_one_or_none()


async def update_call_status(
    db: AsyncSession,
    call_id: uuid.UUID,
    status: str,
) -> Optional[Call]:
    """
    Updates the status of an existing call record.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid call status '{status}'. Must be one of {VALID_STATUSES}")

    call = await get_call(db, call_id)
    if not call:
        return None

    call.status = status
    await db.commit()
    await db.refresh(call)
    return call


async def end_call(db: AsyncSession, call_id: uuid.UUID) -> Optional[Call]:
    """
    Ends a call session by setting status='stopped' and setting ended_at timestamp.
    """
    call = await get_call(db, call_id)
    if not call:
        return None

    call.status = "stopped"
    call.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(call)
    return call
