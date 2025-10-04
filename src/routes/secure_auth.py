import logging
from typing import Optional
from fastapi import APIRouter, Response, Request, HTTPException, Cookie
from pydantic import BaseModel, Field
import httpx
from ..mw_utils.session import (
    create_session,
    get_session,
    delete_session,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
)
from ..mw_utils.env import get_env_variable
from ..mw_utils.http_client import DEFAULT_HEADERS

logger = logging.getLogger("moodleware.secure_auth")
router = APIRouter(prefix="/api/secure", tags=["Secure Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str
    service: str = "moodle_mobile_app"
    moodle_url: Optional[str] = None


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    username: Optional[str] = None


def _normalize_moodle_url(url: str) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return f"https://{url}"
    return url.rstrip("/")





@router.post("/login", response_model=LoginResponse)
async def secure_login(login_data: LoginRequest, response: Response):
    moodle_url = _normalize_moodle_url(
        login_data.moodle_url or get_env_variable("MOODLE_URL") or "https://moodle.example.com"
    )
    token_url = f"{moodle_url}/login/token.php"
    
    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS) as client:
            token_response = await client.post(
                token_url,
                data={
                    "username": login_data.username,
                    "password": login_data.password,
                    "service": login_data.service,
                }
            )
            
            token_response.raise_for_status()
            token_data = token_response.json()
            
            if "error" in token_data or "errorcode" in token_data:
                error_msg = token_data.get("error", "Authentication failed")
                logger.warning(f"Moodle auth failed: {error_msg}")
                return LoginResponse(success=False, message=error_msg)
            
            moodle_token = token_data.get("token")
            if not moodle_token:
                return LoginResponse(success=False, message="No token received from Moodle")
            
            session_id = create_session(moodle_token=moodle_token, moodle_url=moodle_url)
            
            is_production = get_env_variable("ENVIRONMENT") == "production"
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_id,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                secure=is_production,
                samesite="lax",
                path="/",
            )
            
            logger.info(f"Successful login for {login_data.username}")
            
            return LoginResponse(
                success=True,
                message="Login successful",
                user_id=token_data.get("userid"),
                username=login_data.username
            )
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Moodle HTTP error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Error communicating with Moodle"
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during login"
        )


@router.post("/logout")
async def secure_logout(response: Response, session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)):
    if session_cookie:
        delete_session(session_cookie)
    
    is_production = get_env_variable("ENVIRONMENT") == "production"
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=is_production,
        samesite="lax"
    )
    
    logger.info("User logged out")
    
    return {"success": True, "message": "Logged out successfully"}


@router.get("/check")
async def check_session(session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)):
    if not session_cookie:
        return {"authenticated": False}
    
    session = get_session(session_cookie)
    if not session:
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "moodle_url": session.moodle_url,
        "session_age": session.last_accessed - session.created_at
    }
