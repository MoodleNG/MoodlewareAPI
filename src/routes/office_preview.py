"""
Office Preview One-Time Token Endpoint

Generates one-time use tokens for Office Live Viewer to access files.
Solves the problem where Microsoft servers can't access authenticated POST endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import httpx
import secrets
import logging
from typing import Optional

from ..dependencies.auth import get_current_session
from ..mw_utils.session import SessionData, get_redis

logger = logging.getLogger("moodleware")

router = APIRouter(prefix="/office", tags=["office-preview"])

# One-time token prefix in Redis
OT_TOKEN_PREFIX = "ot_token:"
OT_TOKEN_EXPIRY = 60  # 60 seconds TTL for one-time tokens


class GenerateTokenRequest(BaseModel):
    """Request body for generating a one-time token"""
    file_path: str  # e.g., "/webservice/pluginfile.php/123/mod_resource/content/1/document.docx"


class GenerateTokenResponse(BaseModel):
    """Response containing the one-time token and file URL"""
    token: str
    file_url: str
    expires_in: int  # seconds


@router.post("/generate-token", response_model=GenerateTokenResponse)
async def generate_one_time_token(
    request: GenerateTokenRequest,
    session: SessionData = Depends(get_current_session)
):
    """
    Generate a one-time token for accessing a file via Office Live Viewer.
    
    This endpoint:
    1. Validates the user's session
    2. Generates a secure one-time token
    3. Stores the token in Redis with file path and Moodle credentials
    4. Returns the token and public file URL for Office Live Viewer
    
    The token expires after 60 seconds or after first use.
    """
    # Generate cryptographically secure random token
    one_time_token = secrets.token_urlsafe(32)
    
    # Store token data in Redis with expiry
    try:
        redis_client = get_redis()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    token_key = f"{OT_TOKEN_PREFIX}{one_time_token}"
    token_data = {
        "file_path": request.file_path,
        "moodle_url": session.moodle_url,
        "moodle_token": session.moodle_token,
        "session_id": session.session_id,
    }
    
    try:
        # Store as hash with automatic expiry
        await redis_client.hset(token_key, mapping=token_data)
        await redis_client.expire(token_key, OT_TOKEN_EXPIRY)
        
        logger.info(f"Generated one-time token for session {session.session_id[:8]}..., file: {request.file_path}")
    except Exception as e:
        logger.error(f"Failed to store one-time token in Redis: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate token")
    
    # Construct public file URL with one-time token
    # This URL will be accessible without authentication
    file_url = f"/office/file?token={one_time_token}"
    
    return GenerateTokenResponse(
        token=one_time_token,
        file_url=file_url,
        expires_in=OT_TOKEN_EXPIRY
    )


@router.get("/file")
async def get_file_with_one_time_token(
    token: str = Query(..., description="One-time access token")
):
    """
    Retrieve a file using a one-time token.
    
    This endpoint:
    1. Validates the one-time token
    2. Fetches the file from Moodle using stored credentials
    3. Deletes the token after use (single use)
    4. Returns the file to the requesting service (e.g., Office Live Viewer)
    
    The token is deleted immediately after use to prevent replay attacks.
    """
    try:
        redis_client = get_redis()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    token_key = f"{OT_TOKEN_PREFIX}{token}"
    
    try:
        # Retrieve token data
        token_data = await redis_client.hgetall(token_key)
        
        if not token_data:
            raise HTTPException(status_code=404, detail="Token not found or expired")
        
        # Extract file information
        file_path = token_data.get("file_path")
        moodle_url = token_data.get("moodle_url")
        moodle_token = token_data.get("moodle_token")
        session_id = token_data.get("session_id")
        
        if not all([file_path, moodle_url, moodle_token]):
            raise HTTPException(status_code=500, detail="Invalid token data")
        
        # Delete token immediately (single use)
        await redis_client.delete(token_key)
        logger.info(f"One-time token used by session {session_id[:8] if session_id else 'unknown'}..., file: {file_path}")
        
        # Fetch file from Moodle
        moodle_url = moodle_url.rstrip('/')
        if not file_path.startswith('/'):
            file_path = f'/{file_path}'
        
        # Ensure we use webservice/pluginfile.php for token-based access
        if '/pluginfile.php' in file_path and '/webservice/pluginfile.php' not in file_path:
            file_path = file_path.replace('/pluginfile.php', '/webservice/pluginfile.php')
        
        file_url = f"{moodle_url}{file_path}"
        
        # Fetch the file
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(file_url, params={"token": moodle_token})
            response.raise_for_status()
            
            # Return file with appropriate headers
            from fastapi.responses import Response
            return Response(
                content=response.content,
                media_type=response.headers.get("Content-Type", "application/octet-stream"),
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",  # Don't cache one-time tokens
                    "X-Content-Type-Options": "nosniff",
                    "Content-Disposition": response.headers.get("Content-Disposition", ""),
                }
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch file from Moodle: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch file from Moodle"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Moodle: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to Moodle"
        )
    except Exception as e:
        logger.error(f"Error processing one-time token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process token")
