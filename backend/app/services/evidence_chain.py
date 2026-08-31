import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import EvidenceLog

GENESIS_HASH: str = "0" * 64


def canonical(payload: dict) -> bytes:
    """
    Produces deterministic byte representation of payload dictionary
    using sorted keys and no whitespace separators.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def next_hash(prev_hash: str, payload: dict) -> str:
    """
    Calculates SHA-256 hash chaining previous hash and canonical payload.
    """
    return hashlib.sha256(prev_hash.encode("utf-8") + canonical(payload)).hexdigest()


async def append_evidence(
    db: AsyncSession,
    call_id: Union[str, uuid.UUID],
    detection_id: Optional[int],
    payload: dict,
) -> EvidenceLog:
    """
    Appends a new evidence entry to the call's hash-chain.
    Fetches the latest entry for the call to link prev_hash,
    computes next entry_hash, and adds to DB session.
    """
    if isinstance(call_id, str):
        call_id = uuid.UUID(call_id)

    # Fetch latest evidence_log row for this call
    stmt = (
        select(EvidenceLog)
        .where(EvidenceLog.call_id == call_id)
        .order_by(EvidenceLog.entry_id.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest_entry = result.scalar_one_or_none()

    prev_hash = latest_entry.entry_hash if latest_entry else GENESIS_HASH
    entry_hash = next_hash(prev_hash, payload)

    log_entry = EvidenceLog(
        call_id=call_id,
        detection_id=detection_id,
        payload=payload,
        entry_hash=entry_hash,
        prev_hash=prev_hash,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    return log_entry


def verify_chain(entries: List[Union[EvidenceLog, Dict[str, Any]]]) -> bool:
    """
    Verifies cryptographic integrity of an ordered sequence of evidence log entries.
    Walks the chain checking:
    1. prev_hash matches preceding entry's entry_hash (or GENESIS_HASH for entry 0).
    2. entry_hash matches SHA-256(prev_hash + canonical(payload)).
    Returns True if valid, False if tampered or broken.
    """
    if not entries:
        return True

    for i, entry in enumerate(entries):
        if hasattr(entry, "prev_hash"):
            prev_h = entry.prev_hash
            entry_h = entry.entry_hash
            payload_data = entry.payload
        else:
            prev_h = entry.get("prev_hash")
            entry_h = entry.get("entry_hash")
            payload_data = entry.get("payload")

        # 1. Verify prev_hash linkage
        if i == 0:
            expected_prev = GENESIS_HASH
        else:
            prev_entry = entries[i - 1]
            expected_prev = prev_entry.entry_hash if hasattr(prev_entry, "entry_hash") else prev_entry.get("entry_hash")

        if prev_h != expected_prev:
            return False

        # 2. Verify SHA-256 hash match against canonical payload
        computed_h = next_hash(expected_prev, payload_data)
        if entry_h != computed_h:
            return False

    return True
