import os
import logging
import uuid
import asyncio
from typing import Callable
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Security, Response
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from redis.asyncio import Redis
from .mw_utils import get_env_variable, load_config, create_handler
from .mw_utils.session import cleanup_expired_sessions, SESSION_MAX_AGE, init_redis, REDIS_URL
from .routes.secure_auth import router as secure_auth_router
from .routes.files import router as files_router

load_dotenv()

_log_level_name = (get_env_variable("LOG_LEVEL") or "info").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(level=_log_level)
logger = logging.getLogger("moodleware")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis connection
    redis_client = Redis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
    )
    
    try:
        # Test Redis connection
        await redis_client.ping()
        logger.info(f"Redis connected successfully: {REDIS_URL}")
        init_redis(redis_client)
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        await redis_client.aclose()
        raise
    
    # Redis handles session expiration automatically via SETEX
    # No cleanup task needed anymore
    logger.info(f"Session storage initialized (Redis with automatic expiration)")
    
    yield
    
    # Close Redis connection
    await redis_client.aclose()
    logger.info("Redis connection closed")

app = FastAPI(
    title="MoodlewareAPI",
    description="A FastAPI application to wrap Moodle API functions into individual endpoints.",
    version="0.1.0",
    docs_url="/",
    redoc_url=None,
    lifespan=lifespan
)

# CORS configuration from env
_allow_origins_env = (get_env_variable("ALLOW_ORIGINS") or "").strip()

# Custom CORS handling: If "*", dynamically return requesting origin to allow credentials
if _allow_origins_env == "" or _allow_origins_env == "*":
    # Allow all origins by reflecting the request origin
    @app.middleware("http")
    async def dynamic_cors_middleware(request: Request, call_next):
        response = await call_next(request)
        origin = request.headers.get("origin")
        
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response
    
    logger.info("CORS: Allowing all origins with credentials (dynamic reflection)")
else:
    # Specific origins configured
    _allow_origins = [o.strip() for o in _allow_origins_env.split(",") if o.strip()]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS: Allowing specific origins: {_allow_origins}")

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

# Register secure authentication routes
app.include_router(secure_auth_router)

# Register file proxy routes
app.include_router(files_router)

# Health check
@app.post("/healthz", tags=["meta"])
async def healthz():
    return {"status": "ok"}