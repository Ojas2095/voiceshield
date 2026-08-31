from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from datetime import timedelta

from backend.app.config import settings
from backend.app.security.jwt import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(credentials: TokenRequest):
    """
    Authenticate demo client credentials and issue a signed short-lived JWT token.
    """
    if (
        credentials.client_id != settings.DEMO_CLIENT_ID
        or credentials.client_secret != settings.DEMO_CLIENT_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        data={"sub": credentials.client_id},
        expires_delta=timedelta(minutes=expires_minutes)
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_minutes * 60
    )
