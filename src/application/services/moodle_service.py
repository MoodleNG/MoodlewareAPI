from typing import Dict, Any
from datetime import datetime
from .moodle_request_service import MoodleRequestService


class MoodleService:
    """High-level business logic for Moodle API operations"""
    
    @staticmethod
    async def handle_auth(params):
        """Handle authentication endpoint"""
        token = await MoodleRequestService.authenticate(
            params.moodle_url, 
            params.username, 
            params.password, 
            params.service
        )
        
        # Get site info
        client = MoodleRequestService(params.moodle_url, token)
        site_info_response = await client.call_function("core_webservice_get_site_info")
        
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

    @staticmethod
    async def handle_universal(params):
        """Handle universal endpoint"""
        client = MoodleRequestService(params.moodle_url, params.token)
        return await client.call_function(params.function_name, params.parameters)

    @staticmethod
    async def handle_regular_endpoint(params, function_name: str, endpoint_config: Dict[str, Any]):
        """Handle regular Moodle API endpoints"""
        client = MoodleRequestService(params.moodle_url, params.token)
        
        # Extract parameters (exclude moodle_url and token)
        moodle_params = {}
        for param in endpoint_config["params"]:
            if hasattr(params, param["name"]):
                value = getattr(params, param["name"])
                if value is not None:
                    moodle_params[param["name"]] = value
        
        # Handle special parameter transformations
        moodle_params = MoodleService._transform_parameters(function_name, moodle_params)
        
        return await client.call_function(function_name, moodle_params)

    @staticmethod
    def _transform_parameters(function_name: str, moodle_params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform parameters for specific Moodle functions"""
        if function_name == "core_course_get_contents":
            if "exclude_modules" in moodle_params or "exclude_contents" in moodle_params:
                options = []
                if moodle_params.get("exclude_modules"):
                    options.append({"name": "excludemodules", "value": 1})
                if moodle_params.get("exclude_contents"):
                    options.append({"name": "excludecontents", "value": 1})
                
                result = {"courseid": moodle_params["courseid"]}
                if options:
                    result["options"] = options
                return result
        
        elif function_name == "core_calendar_get_calendar_events":
            if "courseid" in moodle_params and moodle_params["courseid"]:
                return {"events": [{"courseid": moodle_params["courseid"]}]}
            else:
                return {}
        
        return moodle_params