from pydantic import BaseModel, Field, create_model
from typing import Dict, Any, List, Optional, Union
from datetime import datetime


class MoodleResponse(BaseModel):
    success: bool
    data: Any
    function_name: str
    execution_time_ms: float
    timestamp: datetime


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
