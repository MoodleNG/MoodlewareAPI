import json
from pathlib import Path
from typing import Dict, List, Any


def load_config(config_dir: str = "config") -> Dict[str, List[Dict[str, Any]]]:
    """Load config from organized folder structure.
    
    Args:
        config_dir: Path to the config directory containing organized endpoint folders
        
    Returns:
        Dictionary mapping endpoint paths to their function configurations:
        {
            "/endpoint/path": [
                {
                    "path": "/api_path",
                    "method": "GET", 
                    "function": "function_name",
                    "description": "...",
                    "tags": ["Tag"],
                    "query_params": [...],
                    "responses": {...}
                }
            ]
        }
    """
    config_path = Path(config_dir)
    
    if not config_path.exists():
        raise RuntimeError(f"Config directory not found: {config_dir}")
    
    result = {}
    
    # Process each endpoint directory
    endpoint_dirs = list(config_path.iterdir())
    endpoint_dirs = [d for d in endpoint_dirs if d.is_dir()]
    
    # Sort endpoint directories, but prioritize token.php (auth) endpoint first
    def endpoint_sort_key(endpoint_dir):
        # Force token.php endpoint to come first (priority 0), others use priority 1
        if "token" in endpoint_dir.name.lower():
            return (0, endpoint_dir.name.lower())
        return (1, endpoint_dir.name.lower())
    
    endpoint_dirs.sort(key=endpoint_sort_key)
    
    for endpoint_dir in endpoint_dirs:
            
        # Convert folder name back to endpoint path
        # _login_token-php -> /login/token.php
        # _webservice_rest_server-php -> /webservice/rest/server.php
        endpoint_path = _folder_name_to_endpoint_path(endpoint_dir.name)
        
        endpoint_functions = []
        
        # Process each tag directory within the endpoint (sorted alphabetically)
        tag_dirs = sorted([d for d in endpoint_dir.iterdir() if d.is_dir()], key=lambda x: x.name.lower())
        for tag_dir in tag_dirs:
            tag_name = tag_dir.name
            
            # Process each function JSON file within the tag directory (sorted alphabetically)
            function_files = sorted(tag_dir.glob("*.json"), key=lambda x: x.name.lower())
            for function_file in function_files:
                function_name = function_file.stem  # filename without .json extension
                
                try:
                    with open(function_file, 'r', encoding='utf-8') as f:
                        function_config = json.load(f)
                    
                    # Reconstruct the full function config
                    full_config = {
                        "path": _generate_api_path(function_name, endpoint_path),
                        "function": function_name,
                        "tags": [tag_name],
                        **function_config  # This includes method, description, query_params, responses
                    }
                    
                    endpoint_functions.append(full_config)
                    
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    raise RuntimeError(f"Error loading function config {function_file}: {e}")
        
        if endpoint_functions:
            result[endpoint_path] = endpoint_functions
    
    return result


def _folder_name_to_endpoint_path(folder_name: str) -> str:
    """Convert folder name back to endpoint path.
    
    Examples:
        _login_token-php -> /login/token.php
        _webservice_rest_server-php -> /webservice/rest/server.php
    """
    # Remove leading underscore
    path = folder_name[1:] if folder_name.startswith('_') else folder_name
    
    # Replace underscores with slashes
    path = path.replace('_', '/')
    
    # Replace dashes with dots (for file extensions)
    path = path.replace('-', '.')
    
    # Add leading slash
    return f"/{path}"


def _generate_api_path(function_name: str, endpoint_path: str) -> str:
    """Generate API path for a function.
    
    For auth functions, use /auth
    For other functions, use the function name as path
    """
    if function_name == "auth":
        return "/auth"
    
    return f"/{function_name}"
