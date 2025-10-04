"""
Session authentication dependency for FastAPI routes.

Use this to protect endpoints that require authentication.
"""

from typing import Optional
from fastapi import Cookie, HTTPException, Depends
from ..mw_utils.session import get_session, SESSION_COOKIE_NAME, SessionData


async def get_current_session(
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)
) -> SessionData:
    """
    Dependency that validates session and returns session data.
    Raises 401 if session is invalid or missing.
    
    Usage:
        @app.get("/protected")
        async def protected_route(session: SessionData = Depends(get_current_session)):
            # session.moodle_token is available here
            return {"token": session.moodle_token}
    """
    if not session_cookie:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    
    session = get_session(session_cookie)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )
    
    return session


async def get_optional_session(
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)
) -> Optional[SessionData]:
    """
    Dependency that returns session if valid, None otherwise.
    Does not raise exception - useful for optional authentication.
    
    Usage:
        @app.get("/public")
        async def public_route(session: Optional[SessionData] = Depends(get_optional_session)):
            if session:
                # User is authenticated
                pass
    """
    if not session_cookie:
        return None
    
    return get_session(session_cookie)
