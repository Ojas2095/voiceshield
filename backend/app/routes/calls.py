"""Compatibility bridge forwarding backend.app.routes.calls to backend.app.routers.calls."""
from backend.app.routers.calls import (
    router,
    CallStartRequest,
    CallStartResponse,
    CallStopResponse,
    CallStatusResponse,
    CallSourceEnum as CallSource,
    CallStatusEnum as CallStatus,
    parse_call_uuid,
)

__all__ = [
    "router",
    "CallStartRequest",
    "CallStartResponse",
    "CallStopResponse",
    "CallStatusResponse",
    "CallSource",
    "CallStatus",
    "parse_call_uuid",
]
