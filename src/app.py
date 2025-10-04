import os
import logging
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Security, Response
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from .mw_utils import get_env_variable, load_config, create_handler

load_dotenv()

# Configure logging level (default to INFO)
_log_level_name = (get_env_variable("LOG_LEVEL") or "info").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(level=_log_level)
logger = logging.getLogger("moodleware")

app = FastAPI(
    title="MoodlewareAPI",
    description="A FastAPI application to wrap Moodle API functions into individual endpoints.",
    version="0.1.0",
    docs_url="/",
    redoc_url=None
)

# CORS configuration from env
_allow_origins_env = (get_env_variable("ALLOW_ORIGINS") or "").strip()
if _allow_origins_env == "" or _allow_origins_env == "*":
    _allow_origins = ["*"]
    _allow_credentials = False  # '*' cannot be used with credentials per CORS spec
else:
    _allow_origins = [o.strip() for o in _allow_origins_env.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next: Callable):
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response

# Optional HTTP Bearer security for Swagger Authorize
http_bearer = HTTPBearer(auto_error=False)

# Load configuration from organized structure
config_dir = os.path.join(os.path.dirname(__file__), "config")
logger.info(f"Loading config from: {config_dir}")
config = load_config(config_dir)
logger.info(f"Loaded {len(config)} endpoint(s)")

for endpoint_path, functions in config.items():
    logger.debug(f"Processing endpoint: {endpoint_path}")
    for function in functions:
        logger.debug(f"Processing function: {function['function']} at path {function['path']}")
        deps = [Security(http_bearer)] if function["path"] != "/auth" else None
        base_handler = create_handler(function, endpoint_path)
        endpoint_callable = base_handler

        app.add_api_route(
            path=function["path"],
            endpoint=endpoint_callable,
            methods=[function["method"].upper()],
            tags=function["tags"],
            summary=function["description"],
            responses=function.get("responses"),
            dependencies=deps,
        )

# Health check
@app.post("/healthz", tags=["meta"])
async def healthz():
    return {"status": "ok"}