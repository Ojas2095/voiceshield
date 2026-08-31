from typing import Optional, Dict
from fastapi import Depends, HTTPException, status, Query, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.app.security.jwt import decode_access_token

security_scheme = HTTPBearer(auto_error=False)

# In-memory registry tracking call_id -> owner identity (user_id)
# TODO (Akshat Integration): Reconcile with PostgreSQL calls table ownership column when merged.
_CALL_OWNERSHIP: Dict[str, str] = {}


def register_call_ownership(call_id: str, user_id: str) -> None:
    """Track that user_id owns call_id."""
    _CALL_OWNERSHIP[call_id] = user_id


def remove_call_ownership(call_id: str) -> None:
    """Remove call_id ownership tracking."""
    _CALL_OWNERSHIP.pop(call_id, None)


def get_call_owner(call_id: str) -> Optional[str]:
    """Retrieve owner of call_id."""
    return _CALL_OWNERSHIP.get(call_id)


def verify_call_ownership(user_id: str, call_id: str) -> bool:
    """
    Verify whether user_id owns call_id.
    """
    owner = get_call_owner(call_id)
    if owner is None:
        # If not tracked in memory, check DB stub
        # TODO (Akshat Integration): query database table for call ownership
        return False
    return owner == user_id


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> str:
    """
    FastAPI dependency validating Bearer JWT on protected HTTP routes.
    Returns user_id (sub) or raises 401.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return str(payload["sub"])


def validate_ws_token(token: Optional[str]) -> Optional[str]:
    """
    Validates JWT token passed via WebSocket query parameter (?token=...).
    Returns user_id (sub) if valid, None if invalid or expired.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    return str(payload["sub"])
