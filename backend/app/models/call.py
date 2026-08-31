from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict
import uuid
from pydantic import BaseModel, Field, field_validator


class CallSource(str, Enum):
    MIC = "mic"
    PHONE_SIM = "phone_sim"
    REPLAY = "replay"


class CallStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


class CallStartRequest(BaseModel):
    source: CallSource


class CallStartResponse(BaseModel):
    call_id: str
    started_at: str


class CallStopResponse(BaseModel):
    call_id: str
    status: CallStatus
    ended_at: str


class CallStatusResponse(BaseModel):
    call_id: str
    status: CallStatus
    source: CallSource
    started_at: str
    ended_at: Optional[str] = None
    is_stream_active: bool


# TODO (Akshat Integration): Reconcile with Akshat's PostgreSQL SQLAlchemy Call model once merged.
# In-memory database store for Call records until DB migration is merged.
class CallRecord:
    def __init__(self, call_id: str, user_id: str, source: CallSource):
        self.call_id = call_id
        self.user_id = user_id
        self.source = source
        self.status = CallStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None


_CALL_STORE: Dict[str, CallRecord] = {}


def create_call_record(call_id: str, user_id: str, source: CallSource) -> CallRecord:
    record = CallRecord(call_id=call_id, user_id=user_id, source=source)
    _CALL_STORE[call_id] = record
    return record


def get_call_record(call_id: str) -> Optional[CallRecord]:
    return _CALL_STORE.get(call_id)


def update_call_ended(call_id: str) -> Optional[CallRecord]:
    record = _CALL_STORE.get(call_id)
    if record:
        record.status = CallStatus.ENDED
        record.ended_at = datetime.now(timezone.utc)
    return record
