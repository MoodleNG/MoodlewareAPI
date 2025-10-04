"""
File Proxy Endpoint

Securely proxies file requests to Moodle with session authentication.
Replaces the insecure practice of appending tokens to URLs.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
import httpx
from typing import AsyncIterator, Dict, Optional
import mimetypes

from ..dependencies.auth import get_current_session
from ..mw_utils.session import SessionData

router = APIRouter(prefix="/files", tags=["files"])

# Persistent HTTP client for connection pooling and HTTP/2
_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create persistent HTTP client with connection pooling"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            http2=True,  # Enable HTTP/2 for multiplexing
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,
            )
        )
    return _http_client


def guess_content_type(path: str, moodle_content_type: Optional[str] = None) -> str:
    """Guess content type from file extension or Moodle header"""
    if moodle_content_type and moodle_content_type != "application/octet-stream":
        return moodle_content_type
    
    # Guess from file extension
    content_type, _ = mimetypes.guess_type(path)
    return content_type or "application/octet-stream"


async def fetch_file(url: str, moodle_token: str, client: httpx.AsyncClient):
    """Fetch file from Moodle and return response data"""
    response = await client.get(url, params={"token": moodle_token})
    response.raise_for_status()
    
    # Extract useful headers from Moodle response
    headers = {
        "Content-Type": response.headers.get("Content-Type", "application/octet-stream"),
        "Content-Length": str(len(response.content)),
        "Last-Modified": response.headers.get("Last-Modified", ""),
        "ETag": response.headers.get("ETag", ""),
    }
    
    return response.content, headers


@router.get("/{path:path}")
async def proxy_file(
    path: str,
    session: SessionData = Depends(get_current_session)
):
    """
    Proxy file requests to Moodle with session authentication
    
    Accepts file paths like:
    - /files/webservice/pluginfile.php/123/mod_resource/content/1/document.pdf
    - /files/pluginfile.php/123/mod_resource/content/1/image.jpg
    
    The backend appends the Moodle token securely from the session.
    """
    # Ensure path starts with pluginfile.php (with or without webservice/)
    if not path.endswith(".php") and "/pluginfile.php" not in path:
        # Add pluginfile.php if not present
        if not path.startswith("pluginfile.php") and not path.startswith("webservice/pluginfile.php"):
            if "/webservice/" not in path:
                path = f"webservice/pluginfile.php/{path}"
    
    # Construct full Moodle file URL
    moodle_url = session.moodle_url.rstrip('/')
    if not path.startswith('/'):
        path = f'/{path}'
    
    # Ensure we use webservice/pluginfile.php for token-based access
    if '/pluginfile.php' in path and '/webservice/pluginfile.php' not in path:
        path = path.replace('/pluginfile.php', '/webservice/pluginfile.php')
    
    file_url = f"{moodle_url}{path}"
    
    try:
        # Get persistent HTTP client for connection pooling
        client = await get_http_client()
        
        # Fetch the file from Moodle with authentication
        file_content, moodle_headers = await fetch_file(
            file_url, 
            session.moodle_token,
            client
        )
        
        # Guess proper content type
        content_type = guess_content_type(path, moodle_headers.get("Content-Type"))
        
        # Build response headers
        response_headers = {
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "X-Content-Type-Options": "nosniff",
        }
        
        # Add Moodle headers if present
        if moodle_headers.get("Content-Length"):
            response_headers["Content-Length"] = moodle_headers["Content-Length"]
        if moodle_headers.get("Last-Modified"):
            response_headers["Last-Modified"] = moodle_headers["Last-Modified"]
        if moodle_headers.get("ETag"):
            response_headers["ETag"] = moodle_headers["ETag"]
        
        return Response(
            content=file_content,
            media_type=content_type,
            headers=response_headers
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch file from Moodle: {e.response.status_code}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to Moodle: {str(e)}"
        )
