import logging
from typing import Any, Dict, List
from fastapi import Query, HTTPException, Response, Request
import httpx
from .env import get_env_variable
from .params import encode_param
from .auth import resolve_token_from_request
from .http_client import DEFAULT_HEADERS

LOGGER = logging.getLogger("moodleware.handlers")


def _normalize_base_url(base_url: str) -> str:
    if not base_url.lower().startswith(("http://", "https://")):
        return f"https://{base_url}"
    return base_url


def _is_auth_endpoint(ep_path: str) -> bool:
    return ep_path.endswith("/login/token.php")


def _build_handler_signature(query_params: List[Dict[str, Any]], require_moodle_url: bool):
    import inspect

    sig_params: List[inspect.Parameter] = [
        inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
        inspect.Parameter("response", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Response),
    ]

    if require_moodle_url:
        sig_params.append(
            inspect.Parameter(
                "moodle_url",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=str,
                default=Query(..., description="URL of the Moodle instance, e.g., 'https://moodle.example.com'."),
            )
        )

    def _py_type(tname: str):
        t = (tname or "str").lower()
        if t == "int":
            return int
        if t in {"float", "double"}:
            return float
        if t == "bool":
            return bool
        return str

    for param in query_params:
        pname = param["name"]
        ptype = _py_type(param.get("type", "str"))
        if param["required"]:
            sig_params.append(
                inspect.Parameter(
                    pname,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=ptype,
                    default=Query(..., description=param["description"]),
                )
            )
        else:
            default_value = param.get("default", None)
            sig_params.append(
                inspect.Parameter(
                    pname,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=Any,  # Optional type in docs
                    default=Query(default_value, description=param["description"]),
                )
            )

    return inspect.Signature(sig_params)


def create_handler(function_config: Dict[str, Any], endpoint_path: str):
    query_params: List[Dict[str, Any]] = function_config.get("query_params", [])
    method = function_config.get("method", "GET").upper()

    async def handler(request: Request, response: Response, **kwargs):
        base_url = get_env_variable("MOODLE_URL") or kwargs.get("moodle_url")
        if not base_url:
            raise HTTPException(status_code=400, detail="Moodle URL not provided. Set MOODLE_URL env var or pass moodle_url as query param.")

        base_url = _normalize_base_url(base_url)
        ep_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        url = f"{base_url.rstrip('/')}{ep_path}"

        params: Dict[str, Any] = {}
        for param in query_params:
            pname = param["name"]
            ptype = param.get("type", "str")
            if pname in kwargs and kwargs[pname] is not None:
                encode_param(params, pname, kwargs[pname], ptype)

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
        response.headers["X-Moodle-Direct-Method"] = method

        try:
            async with httpx.AsyncClient(follow_redirects=True, headers=DEFAULT_HEADERS) as client:
                if method == "GET":
                    resp = await client.get(url, params=params)
                elif method == "POST":
                    resp = await client.post(url, data=params)
                else:
                    resp = await client.request(
                        method,
                        url,
                        params=params if method in {"DELETE", "HEAD"} else None,
                        data=None if method in {"DELETE", "HEAD"} else params,
                    )

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

    require_moodle_url = not get_env_variable("MOODLE_URL")
    handler.__signature__ = _build_handler_signature(query_params, require_moodle_url)  # type: ignore[attr-defined]

    return handler
