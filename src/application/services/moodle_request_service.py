from typing import Dict, Any, Optional
import httpx
from datetime import datetime
from fastapi import HTTPException


class MoodleRequestService:
    """Low-level HTTP client for making requests to Moodle API"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.ws_endpoint = f"{self.base_url}/webservice/rest/server.php"
    
    async def call_function(self, function_name: str, parameters: Optional[Dict[str, Any]] = None):
        """Make a request to Moodle webservice API"""
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
        """Recursively add parameters to request data with proper Moodle formatting"""
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

    @staticmethod
    async def authenticate(moodle_url: str, username: str, password: str, service: str = "moodle_mobile_app"):
        """Authenticate with Moodle and get token"""
        login_url = f"{moodle_url}/login/token.php"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(login_url, data={
                    "username": username,
                    "password": password,
                    "service": service
                })
                response.raise_for_status()
                
                data = response.json()
                if "token" not in data:
                    raise HTTPException(
                        status_code=401, 
                        detail=f"Authentication failed: {data.get('error', 'Unknown error')}"
                    )
                
                return data["token"]
                
            except httpx.HTTPStatusError:
                raise HTTPException(status_code=401, detail="Failed to connect to Moodle server")
            except httpx.RequestError:
                raise HTTPException(status_code=503, detail="Unable to connect to Moodle server")