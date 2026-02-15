from slowapi import Limiter
from slowapi.util import get_remote_address
from .env import get_env_variable

# Shared limiter instance – attached to app.state in app.py
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Configurable login rate limit; override via LOGIN_RATE_LIMIT env var
LOGIN_RATE_LIMIT: str = get_env_variable("LOGIN_RATE_LIMIT") or "10/minute"
