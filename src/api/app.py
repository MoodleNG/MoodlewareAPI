from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
from ..application.services.moodle_service import MoodleService
from ..application.utils import MoodleResponse, create_param_model

# Load configuration
config_path = Path(__file__).parent.parent.parent / "config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

# FastAPI app
app = FastAPI(
    title="MoodlewareAPI",
    description="Easily interact with Moodle API",
    version="0.0.1",
    docs_url="/",
    redoc_url="/redoc"
)

# Add CORS middleware for browser compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_endpoint_handler(endpoint_config, param_model):
    """Create endpoint handler function"""
    async def endpoint_handler(params):
        if endpoint_config["function"] == "auth":
            return await MoodleService.handle_auth(params)
        elif endpoint_config["function"] == "universal":
            return await MoodleService.handle_universal(params)
        else:
            return await MoodleService.handle_regular_endpoint(params, endpoint_config["function"], endpoint_config)
    
    # Set the parameter annotation
    endpoint_handler.__annotations__ = {"params": param_model, "return": MoodleResponse}
    return endpoint_handler

# Dynamically create endpoints
for endpoint_config in config["endpoints"]:
    param_model = create_param_model(endpoint_config)
    handler = create_endpoint_handler(endpoint_config, param_model)
    
    # Register the endpoint with FastAPI
    app.add_api_route(
        endpoint_config["path"],
        handler,
        methods=[endpoint_config["method"]],
        response_model=MoodleResponse,
        tags=endpoint_config["tags"],
        summary=endpoint_config["description"]
    )
