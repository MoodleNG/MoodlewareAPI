from fastapi import Request


async def resolve_token_from_request(request: Request) -> str:
    """Resolve token from Authorization header (Bearer) or ?wstoken= query.

    Returns empty string if not found.
    """
    auth = request.headers.get("Authorization", "").strip()
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return (request.query_params.get("wstoken") or "").strip()
