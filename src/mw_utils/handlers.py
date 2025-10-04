import logging
from typing import Any, Dict, List, Optional
from fastapi import Query, Body, HTTPException, Response, Request
from pydantic import BaseModel, Field, create_model
import httpx
from .env import get_env_variable
from .params import encode_param
from .auth import resolve_token_from_request
from .http_client import DEFAULT_HEADERS

LOGGER = logging.getLogger("moodleware.handlers")


def _normalize_base_url(base_url: str) -> str:
    """Normalize a Moodle base URL: ensure it has http/https (default https)."""
    if not base_url.lower().startswith(("http://", "https://")):
        return f"https://{base_url}"
    return base_url


def _is_auth_endpoint(ep_path: str) -> bool:
    """Detect whether the endpoint path targets Moodle's token endpoint."""
    return ep_path.endswith("/login/token.php")


# Markers considered as 'unset' for MOODLE_URL; requires moodle_url query param
_def_unset_markers = {"", "*"}

def _get_env_moodle_url() -> str:
    """Read MOODLE_URL from env; treat '' or '*' as unset and return ''."""
    val = (get_env_variable("MOODLE_URL") or "").strip()
    return "" if val in _def_unset_markers else val


def _create_request_model(query_params: List[Dict[str, Any]], require_moodle_url: bool, function_name: str) -> type[BaseModel]:
    """Create a Pydantic model for the request body based on query_params config."""
    
    def _py_type(tname: str):
        """Map config type strings to Python types."""
        t = (tname or "str").lower()
        if t == "int":
            return int
        if t in {"float", "double"}:
            return float
        if t == "bool":
            return bool
        if t == "list":
            return List[Any]
        return str
    
    fields = {}
    
    # Add moodle_url if required
    if require_moodle_url:
        fields["moodle_url"] = (
            str,
            Field(..., description="URL of the Moodle instance, e.g., 'https://moodle.example.com'.")
        )
    
    # Add fields from query_params
    for param in query_params:
        pname = param["name"]
        ptype = _py_type(param.get("type", "str"))
        pdesc = param.get("description", "")
        
        if param.get("required", False):
            # Required field
            fields[pname] = (ptype, Field(..., description=pdesc))
        else:
            # Optional field with default
            default_value = param.get("default", None)
            fields[pname] = (Optional[ptype], Field(default=default_value, description=pdesc))
    
    # Create a dynamic Pydantic model
    model_name = f"{function_name.replace('_', ' ').title().replace(' ', '')}Request"
    return create_model(model_name, **fields)


def _build_handler_signature(request_model: type[BaseModel]):
    """Build a FastAPI handler signature with a typed Pydantic body model."""
    import inspect

    sig_params: List[inspect.Parameter] = [
        inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
        inspect.Parameter("response", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Response),
    ]

    # Add body parameter with the Pydantic model type
    sig_params.append(
        inspect.Parameter(
            "body",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=request_model,
            default=Body(...),
        )
    )

    return inspect.Signature(sig_params)


def create_handler(function_config: Dict[str, Any], endpoint_path: str):
    """Factory that creates an async FastAPI route handler proxying to Moodle.

    Uses MOODLE_URL from env (unless '*' or empty), otherwise requires a
    moodle_url query param. Automatically adds wstoken for non-auth endpoints
    and sets wsfunction/moodlewsrestformat for REST server endpoints.
    """
    query_params: List[Dict[str, Any]] = function_config.get("query_params", [])
    method = function_config.get("method", "GET").upper()
    function_name = function_config.get("function", "unknown")
    
    # Create the Pydantic model for this endpoint
    require_moodle_url = not _get_env_moodle_url()
    request_model = _create_request_model(query_params, require_moodle_url, function_name)

    async def handler(request: Request, response: Response, body: BaseModel):
        """Proxy request to the Moodle instance and return JSON/text response."""
        # Convert Pydantic model to dict
        body_dict = body.model_dump()
        
        env_base = _get_env_moodle_url()
        base_url = env_base or body_dict.get("moodle_url")
        if not base_url:
            raise HTTPException(status_code=400, detail="Moodle URL not provided. Set MOODLE_URL env var or pass moodle_url in request body.")

        base_url = _normalize_base_url(base_url)
        ep_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        url = f"{base_url.rstrip('/')}" + ep_path

        params: Dict[str, Any] = {}
        for param in query_params:
            pname = param["name"]
            ptype = param.get("type", "str")
            send_if_empty = param.get("send_if_empty", False)
            default_value = param.get("default", None)
            
            # Get value from body, or use default if not provided
            value = body_dict.get(pname, default_value)
            
            if value is not None and value != "":
                encode_param(params, pname, value, ptype)
            elif send_if_empty:
                # Always send, even if empty
                encode_param(params, pname, "", ptype)

        if not _is_auth_endpoint(ep_path):
            token = await resolve_token_from_request(request)
            if token:
                params["wstoken"] = token

        if ep_path.endswith("/webservice/rest/server.php"):
            params.setdefault("wsfunction", function_config.get("function"))
            params.setdefault("moodlewsrestformat", "json")

        from urllib.parse import urlencode as _urlencode
        direct_url = f"{url}?{_urlencode(params, doseq=True)}" if params else url
        response.headers["X-Moodle-Direct-URL"] = direct_url
        response.headers["X-Moodle-Direct-Method"] = "POST"

        try:
            async with httpx.AsyncClient(follow_redirects=True, headers=DEFAULT_HEADERS) as client:

                resp = await client.post(url, data=params)

                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    return resp.text
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error contacting Moodle at {url}: {str(e)}")

    handler.__signature__ = _build_handler_signature(request_model)  # type: ignore[attr-defined]

    return handler
