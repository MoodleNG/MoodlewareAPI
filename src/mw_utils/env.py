import os
import logging

LOGGER = logging.getLogger("moodleware.env")

def get_env_variable(var_name: str) -> str:
    """Return an environment variable or empty string if unset."""
    value = os.environ.get(var_name, "")
    if not value:
        LOGGER.debug("Env '%s' not set or empty", var_name)
    return value
