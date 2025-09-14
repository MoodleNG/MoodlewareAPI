import os
import json
from fastapi import Query, HTTPException, Response
from typing import Optional
import httpx
from urllib.parse import urlencode


def get_env_variable(var_name: str) -> str:
    """Return an environment variable or empty string if unset."""
    value = os.environ.get(var_name, "")
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


# Helper utilities to prepare parameters for Moodle REST (supports arrays and nested structures)
def _parse_list_value(raw_val):
    """Accepts a value for a 'list' parameter and returns a Python list.
    Accepts JSON string (preferred), comma-separated string, or already a list.
    """
    if raw_val is None:
        return []
    # Already a list
    if isinstance(raw_val, list):
        return raw_val
    # If value comes as bool/int/float, wrap into list
    if isinstance(raw_val, (bool, int, float)):
        return [raw_val]
    # Try parse JSON
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if s == "":
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            # Fallback: comma-separated
            if "," in s:
                return [part.strip() for part in s.split(",") if part.strip() != ""]
            # Single scalar value in string -> list of one
            return [s]
    # Fallback
    return [raw_val]


def _encode_param(params: dict, name: str, value, declared_type: str):
    """Encodes a single parameter into the params dict.
    - bool -> 1/0
    - float -> keep float
    - list -> name[0]=, name[1]= OR name[0][key]= for list of dicts
    - dict -> name[key]=value
    - other -> as is
    """
    # Normalize declared_type
    dtype = (declared_type or "str").lower()

    # Booleans -> 1/0
    if dtype == "bool":
        if isinstance(value, str):
            v = value.strip().lower()
            value = 1 if v in {"1", "true", "on", "yes"} else 0
        else:
            value = 1 if bool(value) else 0
        params[name] = value
        return

    # Float mapping
    if dtype in {"float", "double"}:
        try:
            params[name] = float(value)
        except Exception:
            params[name] = value
        return

    # Int mapping
    if dtype == "int":
        try:
            params[name] = int(value)
        except Exception:
            params[name] = value
        return

    # List mapping (supports list of scalars or list of dicts)
    if dtype == "list":
        items = _parse_list_value(value)
        for idx, item in enumerate(items):
            if isinstance(item, dict):
                for k, v in item.items():
                    # Convert nested bools to 1/0, keep numbers/strings
                    if isinstance(v, bool):
                        v = 1 if v else 0
                    params[f"{name}[{idx}][{k}]"] = v
            else:
                params[f"{name}[{idx}]"] = item
        return

    # Dict mapping
    if isinstance(value, dict):
        for k, v in value.items():
            params[f"{name}[{k}]"] = v
        return

    # Default (string or other scalar)
    params[name] = value


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

        # Build params with support for complex types
        params = {}
        for param in query_params:
            pname = param["name"]
            ptype = param.get("type", "str")
            if pname in kwargs and kwargs[pname] is not None:
                _encode_param(params, pname, kwargs[pname], ptype)

        # Token handling
        if "wstoken" in kwargs and kwargs["wstoken"] is not None:
            params["wstoken"] = kwargs["wstoken"]

        # For core REST endpoint include wsfunction & format
        if ep_path.endswith("/webservice/rest/server.php"):
            params.setdefault("wsfunction", function_config.get("function"))
            params.setdefault("moodlewsrestformat", "json")

        from urllib.parse import urlencode as _urlencode
        direct_url = f"{url}?{_urlencode(params, doseq=True)}" if params else url
        response.headers["X-Moodle-Direct-URL"] = direct_url
        response.headers["X-Moodle-Direct-Method"] = method

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True, headers={"Accept": "application/json, text/plain;q=0.9, */*;q=0.8"}) as client:
                if method == "GET":
                    resp = await client.get(url, params=params)
                elif method == "POST":
                    # Moodle expects form-encoded for POST
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

    # Build dynamic signature for OpenAPI/Docs
    import inspect
    sig_params = [
        inspect.Parameter(
            "response",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Response
        )
    ]

    # moodle_url is only needed if env var not set
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

    # Map config 'type' to Python types for docs only
    def _py_type(tname: str):
        t = (tname or "str").lower()
        if t == "int":
            return int
        if t in {"float", "double"}:
            return float
        if t == "bool":
            return bool
        # For lists and complex we accept string (JSON or CSV)
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
                    default=Query(..., description=param["description"]) 
                )
            )
        else:
            default_value = param.get("default", None)
            sig_params.append(
                inspect.Parameter(
                    pname,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=Optional[ptype],
                    default=Query(default_value, description=param["description"]) 
                )
            )

    new_sig = inspect.Signature(sig_params)
    # Avoid static type checker complaints by using setattr
    setattr(handler, "__signature__", new_sig)

    return handler