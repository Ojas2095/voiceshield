"""
Global FastAPI dependencies helper module.
"""

# Re-export security dependencies for convenience
from backend.app.security.dependencies import get_current_user, verify_call_ownership

__all__ = ["get_current_user", "verify_call_ownership"]
