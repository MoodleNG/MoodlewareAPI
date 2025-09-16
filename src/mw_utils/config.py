import json


def load_config(file_path: str) -> dict:
    """Load JSON config file or raise a clear error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise RuntimeError(f"Config not found: {file_path}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in config: {file_path}") from e
