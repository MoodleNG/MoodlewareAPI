import os
import json
from pathlib import Path
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from .utils import get_env_variable, load_config, create_handler

# Load environment variables from .env file
load_dotenv()


# FastAPI app
app = FastAPI(
    title="MoodlewareAPI",
    description="A FastAPI application to wrap Moodle API functions into individual endpoints.",
    version="0.1.0",
    docs_url="/",
    redoc_url=None
)

# Add CORS middleware for browser compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config("config.json")

# Dynamically create endpoints
for endpoint_path, functions in config.items():
    print(f"Processing endpoint: {endpoint_path}")
    for function in functions:
        print(f"Processing function: {function['function']} at path {function['path']}")
        
        # Register the endpoint with FastAPI
        app.add_api_route(
            path=function["path"],
            endpoint=create_handler(function, endpoint_path),
            methods=[function["method"].upper()],
            # response_model={WIP},
            tags=function["tags"],
            summary=function["description"],
            responses=function.get("responses")
        )