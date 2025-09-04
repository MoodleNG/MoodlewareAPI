import os
import json
from fastapi import Query, HTTPException, Response
from typing import Optional
import httpx
from urllib.parse import urlencode

def get_env_variable(var_name: str) -> str:
    """Return an environment variable or empty string if unset."""
    value = os.environ.get(var_name)
    if not value:
        print(f"Environment variable '{var_name}' not set or empty, please provide moodle_url parameters in the requests.")
    return value


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
    query_params = function_config.get("query_params", [])
    method = function_config.get("method", "GET").upper()

    async def handler(response: Response, **kwargs):
        base_url = get_env_variable("MOODLE_URL") or kwargs.get("moodle_url")
        if not base_url:
            raise HTTPException(status_code=400, detail="Moodle URL not provided. Set MOODLE_URL env var or pass moodle_url as query param.")

        if not base_url.lower().startswith(("http://", "https://")):
            base_url = f"https://{base_url}"

        ep_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        url = f"{base_url.rstrip('/')}{ep_path}"

        params = {}
        for param in query_params:
            param_name = param["name"]
            if param_name in kwargs and kwargs[param_name] is not None:
                params[param_name] = kwargs[param_name]

        if "wstoken" in kwargs and kwargs["wstoken"] is not None:
            params["wstoken"] = kwargs["wstoken"]

        if ep_path.endswith("/webservice/rest/server.php"):
            params.setdefault("wsfunction", function_config.get("function"))
            params.setdefault("moodlewsrestformat", "json")

        from urllib.parse import urlencode as _urlencode
        direct_url = f"{url}?{_urlencode(params, doseq=True)}" if params else url
        response.headers["X-Moodle-Direct-URL"] = direct_url
        response.headers["X-Moodle-Direct-Method"] = method

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True, headers={"Accept": "application/json, text/plain;q=0.9, */*;q=0.8"}) as client:
                if method == "GET":
                    resp = await client.get(url, params=params)
                elif method == "POST":
                    resp = await client.post(url, data=params)
                else:
                    resp = await client.request(method, url, params=params if method in {"DELETE", "HEAD"} else None, data=None if method in {"DELETE", "HEAD"} else params)

                resp.raise_for_status()

                try:
                    return resp.json()
                except ValueError:
                    return resp.text
        except httpx.HTTPStatusError as e:
            detail = None
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error contacting Moodle at {url}: {str(e)}")

    import inspect
    sig_params = [
        inspect.Parameter(
            "response",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Response
        )
    ]

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
            sig_params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=param_type,
                    default=Query(..., description=param["description"]) 
                )
            )
        else:
            default_value = param.get("default", None)
            sig_params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=Optional[param_type],
                    default=Query(default_value, description=param["description"]) 
                )
            )

    new_sig = inspect.Signature(sig_params)
    handler.__signature__ = new_sig

    return handler