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

class MoodleResponse(BaseModel):
    success: bool
    data: Any
    function_name: str
    execution_time_ms: float
    timestamp: datetime

# Moodle client
class MoodleClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.ws_endpoint = f"{self.base_url}/webservice/rest/server.php"
    
    async def call_function(self, function_name: str, parameters: Dict[str, Any] = None):
        if parameters is None:
            parameters = {}
        
        data = {
            "wstoken": self.token,
            "wsfunction": function_name,
            "moodlewsrestformat": "json"
        }
        
        self._add_parameters(data, parameters)
        start_time = datetime.now()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.ws_endpoint, data=data)
                response.raise_for_status()
                
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds() * 1000
                
                result = response.json()
                
                if isinstance(result, dict) and "exception" in result:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Moodle error: {result.get('message', 'Unknown error')}"
                    )
                
                return {
                    "success": True,
                    "data": result,
                    "function_name": function_name,
                    "execution_time_ms": execution_time,
                    "timestamp": start_time
                }
                
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=503, detail=f"HTTP error: {e.response.status_code}")
            except httpx.RequestError:
                raise HTTPException(status_code=503, detail="Unable to connect to Moodle server")
    
    def _add_parameters(self, data: Dict[str, Any], parameters: Dict[str, Any], prefix: str = ""):
        for key, value in parameters.items():
            param_name = f"{prefix}[{key}]" if prefix else key
            
            if isinstance(value, dict):
                self._add_parameters(data, value, param_name)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._add_parameters(data, item, f"{param_name}[{i}]")
                    else:
                        data[f"{param_name}[{i}]"] = str(item)
            else:
                data[param_name] = str(value)

# Helper functions
def get_python_type(type_str: str):
    """Convert string type to Python type"""
    type_map = {
        "str": str,
        "int": int,
        "bool": bool,
        "list": List[str],
        "dict": Dict[str, Any]
    }
    return type_map.get(type_str, str)

def create_param_model(endpoint_config: Dict[str, Any]):
    """Dynamically create Pydantic model for endpoint parameters"""
    fields = {}
    
    # Always include moodle credentials unless it's auth endpoint
    if endpoint_config["function"] != "auth":
        fields["moodle_url"] = (str, Field(..., description="Moodle site URL"))
        fields["token"] = (str, Field(..., description="Moodle API token"))
    
    # Add endpoint-specific parameters
    for param in endpoint_config["params"]:
        python_type = get_python_type(param["type"])
        field_description = param.get("description", f"Parameter {param['name']}")
        
        if param["required"]:
            field_def = Field(..., description=field_description)
            fields[param["name"]] = (python_type, field_def)
        else:
            default_value = param.get("default")
            field_def = Field(default_value, description=field_description)
            fields[param["name"]] = (Optional[python_type], field_def)
    
    return create_model(f"{endpoint_config['name']}_params", **fields)

async def handle_auth(params):
    """Handle authentication endpoint"""
    login_url = f"{params.moodle_url}/login/token.php"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(login_url, data={
                "username": params.username,
                "password": params.password,
                "service": params.service
            })
            response.raise_for_status()
            
            data = response.json()
            if "token" not in data:
                raise HTTPException(status_code=401, detail=f"Authentication failed: {data.get('error', 'Unknown error')}")
            
            token = data["token"]
            
            # Get site info
            client_obj = MoodleClient(params.moodle_url, token)
            site_info_response = await client_obj.call_function("core_webservice_get_site_info")
            
            return {
                "success": True,
                "data": {
                    "token": token,
                    "moodle_url": params.moodle_url,
                    "site_info": site_info_response["data"]
                },
                "function_name": "authentication",
                "execution_time_ms": 0,
                "timestamp": datetime.now()
            }
            
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=401, detail="Failed to connect to Moodle server")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Unable to connect to Moodle server")

async def handle_universal(params):
    """Handle universal endpoint"""
    client = MoodleClient(params.moodle_url, params.token)
    return await client.call_function(params.function_name, params.parameters)

async def handle_regular_endpoint(params, function_name: str, endpoint_config: Dict[str, Any]):
    """Handle regular Moodle API endpoints"""
    client = MoodleClient(params.moodle_url, params.token)
    
    # Extract parameters (exclude moodle_url and token)
    moodle_params = {}
    for param in endpoint_config["params"]:
        if hasattr(params, param["name"]):
            value = getattr(params, param["name"])
            if value is not None:
                moodle_params[param["name"]] = value
    
    # Handle special parameter transformations
    if function_name == "core_course_get_contents":
        if "exclude_modules" in moodle_params or "exclude_contents" in moodle_params:
            options = []
            if moodle_params.get("exclude_modules"):
                options.append({"name": "excludemodules", "value": 1})
            if moodle_params.get("exclude_contents"):
                options.append({"name": "excludecontents", "value": 1})
            moodle_params = {"courseid": moodle_params["courseid"]}
            if options:
                moodle_params["options"] = options
    
    elif function_name == "core_calendar_get_calendar_events":
        if "courseid" in moodle_params and moodle_params["courseid"]:
            moodle_params = {"events": [{"courseid": moodle_params["courseid"]}]}
        else:
            moodle_params = {}
    
    return await client.call_function(function_name, moodle_params)

# Dynamically create endpoints
for endpoint_config in config["endpoints"]:
    param_model = create_param_model(endpoint_config)
    
    def create_endpoint_handler(config=endpoint_config, model=param_model):
        async def endpoint_handler(params):
            if config["function"] == "auth":
                return await handle_auth(params)
            elif config["function"] == "universal":
                return await handle_universal(params)
            else:
                return await handle_regular_endpoint(params, config["function"], config)
        
        # Set the parameter annotation
        endpoint_handler.__annotations__ = {"params": model, "return": MoodleResponse}
        return endpoint_handler
    
    # Create the endpoint
    handler = create_endpoint_handler()
    
    # Register the endpoint with FastAPI
    app.add_api_route(
        endpoint_config["path"],
        handler,
        methods=[endpoint_config["method"]],
        response_model=MoodleResponse,
        tags=endpoint_config["tags"],
        summary=endpoint_config["description"]
    )
