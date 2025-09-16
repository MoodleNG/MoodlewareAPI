"""Utilities package split from the former monolithic utils.py.

Modules:
- env: environment helpers
- config: config loader
- params: query/body param encoding helpers
- auth: token resolution helpers
- http_client: shared HTTP client settings
- handlers: dynamic FastAPI handler factory
"""

from .env import get_env_variable
from .config import load_config
from .handlers import create_handler

__all__ = [
    "get_env_variable",
    "load_config",
    "create_handler",
]
