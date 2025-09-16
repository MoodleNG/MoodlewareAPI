import os
import json
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Body, Depends, Security
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .utils import get_env_variable, load_config, create_handler

load_dotenv()

app = FastAPI(
    title="MoodlewareAPI",
    description="A FastAPI application to wrap Moodle API functions into individual endpoints.",
    version="0.1.0",
    docs_url="/",
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional HTTP Bearer security for Swagger Authorize
http_bearer = HTTPBearer(auto_error=False)

config = load_config("config.json")

for endpoint_path, functions in config.items():
    print(f"Processing endpoint: {endpoint_path}")
    for function in functions:
        print(f"Processing function: {function['function']} at path {function['path']}")
        # Attach bearer scheme to all but the open /auth endpoint so Swagger propagates the token
        deps = [Security(http_bearer)] if function["path"] != "/auth" else None
        app.add_api_route(
            path=function["path"],
            endpoint=create_handler(function, endpoint_path),
            methods=[function["method"].upper()],
            tags=function["tags"],
            summary=function["description"],
            responses=function.get("responses"),
            dependencies=deps,
        )