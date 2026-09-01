from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
from typing import Dict, Tuple
from fastapi import HTTPException, status


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying strict security headers to every HTTP response and removing version server headers.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Allow Swagger UI CDNs for /docs, /redoc, /openapi.json while maintaining strict CSP elsewhere
        path = request.url.path
        if path in ("/docs", "/redoc", "/openapi.json"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "frame-ancestors 'none';"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        
        # Remove framework/version leakage
        if "Server" in response.headers:
            del response.headers["Server"]
            
        return response


class InMemoryRateLimiter:
    """
    Token-bucket/sliding counter rate limiter for API endpoints.
    """
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60.0
        # Client IP -> list of timestamps
        self.history: Dict[str, list[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        if client_ip not in self.history:
            self.history[client_ip] = []
            
        timestamps = [t for t in self.history[client_ip] if now - t < self.window_seconds]
        self.history[client_ip] = timestamps

        if len(timestamps) >= self.requests_per_minute:
            return False
            
        self.history[client_ip].append(now)
        return True


rate_limiter = InMemoryRateLimiter(requests_per_minute=30)


async def apply_rate_limit(request: Request):
    """
    FastAPI dependency for rate limiting sensitive endpoints.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
