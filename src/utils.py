import os
import json
from pydantic import BaseModel, Field
from fastapi import Query, HTTPException, Response
from typing import Optional
import httpx
from urllib.parse import urlencode

# Environment Variable Retrieval
def get_env_variable(var_name: str) -> str:
    """Retrieves an environment variable"""
    value = os.environ.get(var_name)
    if not value:
        print(f"Environment variable '{var_name}' not set or empty, please provide moodle_url parameters in the requests.")
    return value


# Load configuration
def load_config(file_path: str) -> dict:
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON for {file_path}.")
        exit(1)


def create_handler(function_config, endpoint_path: str):
    """Create a handler function for the Moodle function with dynamic parameters and perform the actual request."""
    # Get query parameters from config
    query_params = function_config.get("query_params", [])
    method = function_config.get("method", "GET").upper()

    async def handler(response: Response, **kwargs):
        # Resolve Moodle base URL: env var takes precedence, else require query param when not set
        base_url = get_env_variable("MOODLE_URL") or kwargs.get("moodle_url")
        if not base_url:
            raise HTTPException(status_code=400, detail="Moodle URL not provided. Set MOODLE_URL env var or pass moodle_url as query param.")

        # Ensure URL has a scheme to avoid implicit redirects (default to https)
        if not base_url.lower().startswith(("http://", "https://")):
            base_url = f"https://{base_url}"

        # Normalize URL join
        ep_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        url = f"{base_url.rstrip('/')}{ep_path}"

        # Extract the actual parameter values (only those declared in config)
        params = {}
        for param in query_params:
            param_name = param["name"]
            if param_name in kwargs and kwargs[param_name] is not None:
                params[param_name] = kwargs[param_name]

        # If caller provided a token (for REST endpoints), include it even if not declared in config
        if "wstoken" in kwargs and kwargs["wstoken"] is not None:
            params["wstoken"] = kwargs["wstoken"]

        # For REST server calls, ensure wsfunction is set to the actual function name
        if ep_path.endswith("/webservice/rest/server.php"):
            # Do not override if user explicitly provided one
            params.setdefault("wsfunction", function_config.get("function"))
            # Ensure JSON responses by default
            params.setdefault("moodlewsrestformat", "json")

        # Expose the exact direct Moodle URL as a response header
        direct_url = f"{url}?{urlencode(params, doseq=True)}" if params else url
        response.headers["X-Moodle-Direct-URL"] = direct_url
        response.headers["X-Moodle-Direct-Method"] = method

        # Perform request to Moodle
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True, headers={"Accept": "application/json, text/plain;q=0.9, */*;q=0.8"}) as client:
                if method == "GET":
                    resp = await client.get(url, params=params)
                elif method == "POST":
                    # Moodle commonly expects form-encoded data
                    resp = await client.post(url, data=params)
                else:
                    resp = await client.request(method, url, params=params if method in {"DELETE", "HEAD"} else None, data=None if method in {"DELETE", "HEAD"} else params)

                # Raise for non-2xx to surface proper status downstream
                resp.raise_for_status()

                # Try to return JSON, fallback to text
                try:
                    return resp.json()
                except ValueError:
                    return resp.text
        except httpx.HTTPStatusError as e:
            # Try to include server-provided error body
            detail = None
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error contacting Moodle at {url}: {str(e)}")

    # Dynamically add parameter annotations to the handler
    import inspect
    sig_params = [
        inspect.Parameter(
            "response",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Response
        )
    ]

    # Add Moodle URL parameter if not set in environment
    if not get_env_variable("MOODLE_URL"):
        sig_params.append(
            inspect.Parameter(
                "moodle_url",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=str,
                default=Query(..., description="URL of the Moodle instance, e.g., 'https://moodle.example.com'.")
            )
        )

    param_names = {p["name"] if isinstance(p, dict) else p for p in query_params}
    if not {"username", "password"}.issubset(param_names):
        sig_params.append(
            inspect.Parameter(
                "wstoken",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=str,
                default=Query(..., description="Your Moodle Token, obtained from /auth")
            )
        )

    for param in query_params:
        param_name = param["name"]
        param_type = str if param["type"] == "str" else int if param["type"] == "int" else str

        if param["required"]:
            # Required parameter
            sig_params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=param_type,
                    default=Query(..., description=param["description"]) 
                )
            )
        else:
            # Optional parameter with default
            default_value = param.get("default", None)
            sig_params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=Optional[param_type],
                    default=Query(default_value, description=param["description"]) 
                )
            )

    # Create new signature and apply it to the handler
    new_sig = inspect.Signature(sig_params)
    handler.__signature__ = new_sig

    return handler